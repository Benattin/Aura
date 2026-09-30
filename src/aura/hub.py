from __future__ import annotations
import asyncio
import base64
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable

from aura.config import Settings, system_prompt
from aura.llm import LlmError, OllamaClient
from aura.session import Session
from aura.state import LABELS, AuraState, StateMachine, TransitionError
from aura.skills import dispatch
from aura.stt import listen
from aura.tts import Speech, take_sentences, take_utterances
from aura.memory import Memory, wants_forget
from aura.files import (
    deliver_text,
    deliver_bytes,
    from_attachment,
    from_attachment_b64,
    read_for_help,
    remove_named_file,
    solve_prompt,
    wants_code,
    wants_deliver,
    wants_file_help,
    wants_remove_file,
)
from aura.readers import ReadResult, BINARY_EXT, deliver_filename, image_prompt, pdf_page_prompt
from aura.docedit import handle_doc_image_edit, insert_from_b64, wants_doc_image_edit
from aura.life import clip_prompt, get_clipboard, handle as life_handle, wants_clip_help
from aura.vision import grab_jpeg_b64, restore_aura, screen_prompt, wants_screen
from aura.workspace import apply_workspace, active_project, parse_request, wants_workspace, workspace_dir, WORKSPACE_PROMPT
from aura.briefing import compact_context, try_local_command
from aura.digest import build_digest, offline_digest
from aura.triage import heuristic_triage, triage_batch

log = logging.getLogger("aura")

Emit = Callable[[dict[str, Any]], Awaitable[None]]


class Hub:
    def __init__(self, settings: Settings, emit: Emit) -> None:
        self.settings = settings
        self.emit = emit
        self.machine = StateMachine()
        self.memory = Memory()
        self.session = Session(self.memory, followup_seconds=settings.followup_seconds)
        self.llm = OllamaClient(
            settings.ollama_host, settings.model,
            num_predict=settings.num_predict, num_ctx=settings.num_ctx,
        )
        self.speech = Speech(enabled=settings.tts_enabled, rate=settings.tts_rate)
        self.error_detail = ""
        self.pending_model = False
        self.pending_pull = ""
        self.partial = ""
        self.reply = ""
        self.mic_on = False
        self._chat_task: asyncio.Task[None] | None = None
        self._run_id = 0
        self._active_run = 0
        self._loop: asyncio.AbstractEventLoop | None = None
        self._speak_id = 0
        self._active_model = settings.model
        self._briefing_ctx: dict[str, Any] = {}

    def snapshot(self) -> dict[str, Any]:
        return {
            "type": "snapshot", "state": self.machine.state.value,
            "label": LABELS[self.machine.state], "model": self.settings.model,
            "activeModel": self._active_model,
            "codeModel": self.settings.code_model,
            "privacy": "local", "mic": self.mic_on, "tts": self.speech.available(),
            "error": self.error_detail, "partial": self.partial, "reply": self.reply,
            "pendingModel": self.pending_model, "pendingName": self.pending_pull or self.settings.model, "followup": self.session.in_followup(),
            "paused": self.machine.state is AuraState.PAUSED,
            "memoryCount": self.memory.count(),
            "history": self.memory.chats_index(),
            "chatId": self.session.id,
            "turns": self.session.turns(),
            "workspace": str(workspace_dir()),
            "workspaceProject": active_project(),
        }

    async def boot(self) -> None:
        self._loop = asyncio.get_running_loop()
        self.speech.set_on_clip(self._clip_from_thread)
        await self._go(AuraState.IDLE)
        restore_aura()
        asyncio.create_task(self.llm.warmup())
        if self.settings.code_model:
            asyncio.create_task(self.llm.warmup(self.settings.code_model))
        asyncio.create_task(asyncio.to_thread(self.speech.warmup))
        asyncio.create_task(self._warm_stt())
        asyncio.create_task(self._reminder_loop())

    async def _warm_stt(self) -> None:
        from aura.stt import warmup

        await asyncio.to_thread(warmup)

    async def handle(self, msg: dict[str, Any]) -> None:
        kind = msg.get("type")
        if kind == "chat":
            asyncio.create_task(self.chat(str(msg.get("text") or "")))
        elif kind == "pause":
            await self.pause()
        elif kind == "resume":
            await self.resume()
        elif kind == "stop":
            await self.stop_speech()
        elif kind == "ptt":
            asyncio.create_task(self.ptt())
        elif kind == "file":
            name = str(msg.get("name") or "arquivo.txt")
            ext = Path(name).suffix.lower()
            if msg.get("data"):
                await self.attach_binary(name, str(msg.get("data") or ""), str(msg.get("ask") or ""))
            elif ext in BINARY_EXT:
                await self._speak_result(
                    f"Senhor, {Path(name).name} precisa do upload novo. Feche a AURA, abra de novo e use o botão Arquivo."
                )
            else:
                await self.attach_file(name, str(msg.get("text") or ""), str(msg.get("ask") or ""))
        elif kind == "history_new":
            self.session.new()
            self.reply = ""
            await self._broadcast()
        elif kind == "history_open":
            cid = str(msg.get("id") or "")
            if cid:
                self.session.open(cid)
                self.reply = ""
                await self._broadcast()
        elif kind == "confirm_pull":
            await self.pull_model()
        elif kind == "deny_pull":
            self.pending_model = False
            self.pending_pull = ""
            await self._broadcast()
        elif kind == "briefing_context":
            self._briefing_ctx = msg.get("ctx") if isinstance(msg.get("ctx"), dict) else {}
        elif kind == "triage_emails":
            asyncio.create_task(self._triage_emails(msg.get("emails") or []))
        elif kind == "digest":
            asyncio.create_task(self._run_digest(msg.get("pkg") if isinstance(msg.get("pkg"), dict) else {}))

    async def chat(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        if Session.is_stop(text):
            await self.stop_speech()
            return
        await self._spawn(self._run_chat(text))

    async def attach_file(self, name: str, content: str, ask: str) -> None:
        ask = ask.strip() or "Leia este arquivo, explique e resolva o que estiver errado."
        await self._spawn(self._run_attach(name, content, ask))

    async def attach_binary(self, name: str, data_b64: str, ask: str) -> None:
        ask = ask.strip() or "Analise este arquivo e responda ao pedido do senhor."
        await self._spawn(self._run_attach_binary(name, data_b64, ask))

    async def process_upload(self, name: str, data_b64: str, ask: str) -> None:
        """Upload HTTP: aguarda leitura completa do arquivo antes de devolver o snapshot."""
        if self.machine.state is AuraState.PAUSED:
            return
        self._bump_run()
        if self._chat_task and not self._chat_task.done():
            self.speech.stop()
            self._chat_task.cancel()
        self._chat_task = asyncio.create_task(self._run_attach_binary(name, data_b64, ask))
        await self._chat_task

    def _bump_run(self) -> int:
        self._run_id += 1
        return self._run_id

    async def _spawn(self, coro) -> None:
        if self.machine.state is AuraState.PAUSED:
            return
        self._bump_run()
        if self._chat_task and not self._chat_task.done():
            self.speech.stop()
            self._chat_task.cancel()
        self._chat_task = asyncio.create_task(coro)

    async def _task_done(self, run_id: int) -> None:
        self.partial = ""
        if run_id != self._run_id:
            return
        if self.machine.state is AuraState.THINKING:
            await self._go(AuraState.IDLE)

    async def _run_chat(self, text: str) -> None:
        run_id = self._run_id
        self._active_run = run_id
        last = self.reply
        if not last.strip():
            for msg in reversed(self.session.messages):
                if msg.get("role") == "assistant":
                    last = msg.get("content") or ""
                    break
        self.partial = text
        self.reply = ""
        self.session.add_user(text)
        self.memory.observe(text)
        await self._go(AuraState.THINKING)
        await self.emit({"type": "user", "text": text})
        try:
            if wants_forget(text):
                await self._speak_result("Pronto, senhor. Apaguei o que tinha aprendido sobre o senhor.")
                return
            if wants_remove_file(text):
                ok, msg = await asyncio.to_thread(remove_named_file, text)
                await self._speak_result(msg)
                return
            if wants_doc_image_edit(text):
                ok, msg = await asyncio.to_thread(handle_doc_image_edit, text)
                await self._speak_result(msg)
                return
            if wants_deliver(text):
                await self._deliver_chat(text)
                return
            if wants_workspace(text):
                await self._workspace_chat(text)
                return
            if wants_screen(text):
                await self._screen_chat(text)
                return
            if wants_file_help(text):
                await self._file_chat(text)
                return
            if wants_clip_help(text):
                await self._clip_chat(text)
                return
            life = await asyncio.to_thread(life_handle, text, self.memory, last_reply=last)
            if life:
                await self._speak_result(life)
                return
            local = try_local_command(text, self._briefing_ctx)
            if local == "__digest__":
                await self._run_digest(self._briefing_ctx.get("digestPkg") or {})
                return
            if local == "__refresh__":
                await self.emit({"type": "briefing_refresh"})
                await self._speak_result("Atualizando e-mails e notícias, senhor.")
                return
            if local:
                await self._speak_result(local)
                return
            skill = await asyncio.to_thread(dispatch, text)
            if skill:
                await self._speak_result(skill)
                return
            if wants_code(text):
                await self._code_chat(text)
                return
            if needs_reasoning(text):
                await self._reason_chat(text)
                return
            await self._narrate(
                self.llm.chat(
                    self.session.llm_messages(self._prompt(), max_ctx=self._ctx()),
                    **self._chat_opts(),
                )
            )
        except LlmError as exc:
            self.error_detail = str(exc)
            self.pending_model = exc.needs_model
            self.pending_pull = exc.model or self.settings.model
            self.reply = str(exc)
            await self._go(AuraState.ERROR)
            await asyncio.sleep(0.4)
        except asyncio.CancelledError:
            raise
        finally:
            await self._task_done(run_id)

    async def _flush_delta(self, piece: str) -> None:
        if not piece or self._run_id != self._active_run:
            return
        self.reply += piece
        await self.emit({"type": "assistant_delta", "text": piece})
        if self.machine.state is AuraState.THINKING:
            self.machine.go(AuraState.SPEAKING)

    async def _narrate(self, stream) -> None:
        run_id = self._active_run
        chunks: list[str] = []
        buf = ""
        async for delta in stream:
            if run_id != self._run_id:
                return
            chunks.append(delta)
            buf += delta
            await self._flush_delta(delta)
            spoken, buf = take_sentences(buf)
            for piece in spoken:
                self.speech.enqueue(piece)
        leftover, _ = take_utterances(buf, flush=True)
        for piece in leftover:
            self.speech.enqueue(piece)
        full = "".join(chunks).strip()
        if run_id != self._run_id:
            return
        if not full:
            full = "Não consegui gerar uma resposta, senhor."
            await self._flush_delta(full)
            self.speech.enqueue(full)
        self.session.add_assistant(full)
        asyncio.create_task(self._await_speech(run_id))

    async def _await_speech(self, run_id: int | None = None) -> None:
        rid = run_id if run_id is not None else self._active_run
        await asyncio.to_thread(self.speech.drain, 45.0)
        if rid != self._run_id:
            return
        if self.machine.state is AuraState.SPEAKING:
            await self._go(AuraState.IDLE)

    async def _screen_chat(self, text: str) -> None:
        vision = self.settings.vision_model
        if not await self.llm.has_model(vision, refresh=True):
            raise LlmError(
                f"Senhor, para ver a tela preciso do modelo local {vision}. Posso baixá-lo se o senhor confirmar.",
                needs_model=True,
                model=vision,
            )
        try:
            jpeg = await asyncio.to_thread(grab_jpeg_b64)
        except Exception as exc:
            restore_aura()
            await self._speak_result(f"Não consegui capturar a tela, senhor. {exc}")
            return
        restore_aura()
        await self._narrate(
            self.llm.vision(screen_prompt(text), jpeg, model=vision, num_predict=-1)
        )

    async def _file_chat(self, text: str) -> None:
        result = await asyncio.to_thread(read_for_help, text)
        await self._answer_read(result, text)

    async def _answer_read(self, result: ReadResult, user_text: str) -> None:
        log.info("ler %s kind=%s text=%d pages=%d", result.path.name, result.kind, len(result.text), len(result.pages_b64))
        # PDF com texto: caminho rápido (sem moondream)
        if result.kind == "pdf_mixed" and result.text and len(result.text.strip()) >= 80:
            result = ReadResult(
                path=result.path,
                text=result.text,
                kind="document",
                note=result.note or "PDF",
            )
        if result.kind in ("pdf_scan", "pdf_mixed") and result.pages_b64:
            pages = result.pages_b64[:3]
            self.error_detail = f"Lendo imagens do PDF ({len(pages)} pág.)…"
            await self._broadcast()
            await self._pdf_scan_chat(user_text, result.path.name, pages, result.text)
            self.error_detail = ""
            return
        if result.kind == "image" and result.image_b64:
            await self._image_file_chat(user_text, result.path.name, result.image_b64)
            return
        if result.text:
            self.error_detail = f"Analisando {result.path.name}…"
            await self._broadcast()
            gen = await self._doc_gen() if result.kind == "document" else await self._code_gen()
            doc_extra = (
                "\nModo leitura de documento: o texto do arquivo já está na mensagem do usuário. "
                "Responda com base nele. Nunca diga que não tem acesso ao arquivo."
            ) if result.kind == "document" else ""
            messages = [
                {"role": "system", "content": self._prompt() + doc_extra},
                {"role": "user", "content": solve_prompt(user_text, result.path, result.text, kind=result.kind)},
            ]
            await self._narrate(self.llm.chat(messages, **gen))
            self.error_detail = ""
            return
        await self._speak_result(result.note or "Não consegui ler o arquivo, senhor.")

    async def _pdf_scan_chat(self, text: str, name: str, pages: list[str], prefilled: str = "") -> None:
        vision = self.settings.vision_model
        if not await self.llm.has_model(vision, refresh=True):
            raise LlmError(
                f"Senhor, para ler PDF com imagens preciso do modelo {vision}. Posso baixá-lo se o senhor confirmar.",
                needs_model=True,
                model=vision,
            )
        total = len(pages)

        async def _one_page(i: int, page_b64: str) -> str:
            chunks: list[str] = []
            async for delta in self.llm.vision(
                pdf_page_prompt(text, name, i, total), page_b64, model=vision, num_predict=-1
            ):
                chunks.append(delta)
            return f"--- Página {i} ---\n{''.join(chunks).strip()}"

        parts: list[str] = []
        if prefilled.strip():
            parts.append(f"[Texto extraído]\n{prefilled.strip()}")
        self.error_detail = f"Analisando {total} página(s) do PDF…"
        await self._broadcast()
        page_results = await asyncio.gather(*[_one_page(n, page_b64) for n, page_b64 in enumerate(pages, 1)])
        parts.extend(page_results)
        combined = "\n\n".join(parts).strip()
        if len(combined) > 400:
            messages = [
                {"role": "system", "content": self._prompt()},
                {
                    "role": "user",
                    "content": f"Pedido: {text}\n\nConteúdo do PDF {name}:\n{combined[:18_000]}",
                },
            ]
            await self._narrate(self.llm.chat(messages, **await self._doc_gen()))
        else:
            await self._speak_result(combined or "Não consegui ler o PDF, senhor.")

    async def _image_file_chat(self, text: str, name: str, image_b64: str) -> None:
        vision = self.settings.vision_model
        if not await self.llm.has_model(vision, refresh=True):
            raise LlmError(
                f"Senhor, para ver imagens preciso do modelo {vision}. Posso baixá-lo se o senhor confirmar.",
                needs_model=True,
                model=vision,
            )
        await self._narrate(
            self.llm.vision(image_prompt(text, name), image_b64, model=vision, num_predict=-1)
        )

    async def _deliver_chat(self, text: str) -> None:
        fname = deliver_filename(text)
        prompt = (
            self._prompt()
            + "\nGere APENAS o conteúdo final do arquivo pedido, sem explicação fora do conteúdo."
        )
        messages = [{"role": "system", "content": prompt}, {"role": "user", "content": text}]
        chunks: list[str] = []
        async for delta in self.llm.chat(messages, **await self._code_gen()):
            chunks.append(delta)
            await self._flush_delta(delta)
        full = "".join(chunks).strip()
        if not full:
            await self._speak_result("Não gerei conteúdo para salvar, senhor.")
            return
        path = await asyncio.to_thread(deliver_text, fname, full)
        msg = f"Pronto, senhor. Arquivo salvo em {path}"
        self.session.add_assistant(msg)
        await self._speak_result(msg)

    async def _workspace_chat(self, text: str) -> None:
        req = parse_request(text)
        if req and req.list_only:
            ok, msg = await asyncio.to_thread(apply_workspace, text, "")
            await self._speak_result(msg)
            await self._broadcast()
            return
        if req and req.folder_only:
            ok, msg = await asyncio.to_thread(apply_workspace, text, "")
            await self._speak_result(msg)
            await self._broadcast()
            return
        prompt = self._prompt() + WORKSPACE_PROMPT
        messages = [{"role": "system", "content": prompt}, {"role": "user", "content": text}]
        chunks: list[str] = []
        async for delta in self.llm.chat(messages, **await self._code_gen()):
            if self._run_id != self._active_run:
                return
            chunks.append(delta)
            await self._flush_delta(delta)
        full = "".join(chunks).strip()
        ok, msg = await asyncio.to_thread(apply_workspace, text, full)
        if ok:
            self.session.add_assistant(msg)
            await self._speak_result(msg)
        else:
            await self._speak_result(msg)
        await self._broadcast()

    async def _code_chat(self, text: str) -> None:
        prompt = self._prompt()
        opts = await self._code_gen()
        if needs_reasoning(text):
            await self._reason_chat(text, prompt_extra="", opts=opts)
            return
        await self._narrate(
            self.llm.chat(self.session.llm_messages(prompt, max_ctx=self._ctx()), **opts)
        )

    def _chat_opts(self) -> dict:
        self._active_model = self.settings.model
        return {"num_predict": self.settings.num_predict, "num_ctx": self.settings.num_ctx}

    def _reason_opts(self) -> dict:
        self._active_model = self.settings.model
        return {
            "num_predict": self.settings.reason_num_predict,
            "num_ctx": self.settings.reason_num_ctx,
            "temperature": 0.18,
        }

    async def _reason_chat(self, text: str, *, prompt_extra: str = "", opts: dict | None = None) -> None:
        run_id = self._active_run
        gen = opts or self._reason_opts()
        self.partial = "Analisando o pedido..."
        await self._broadcast()
        analysis_msgs = [
            {"role": "system", "content": self._prompt() + prompt_extra + REASONING_ANALYSIS},
            {"role": "user", "content": text},
        ]
        analysis: list[str] = []
        async for delta in self.llm.chat(analysis_msgs, **gen):
            if run_id != self._run_id:
                return
            analysis.append(delta)
        if run_id != self._run_id:
            return
        self.partial = text
        self.reply = ""
        answer_msgs = [
            {"role": "system", "content": self._prompt() + prompt_extra},
            {"role": "user", "content": text},
            {"role": "assistant", "content": "(análise interna)\n" + "".join(analysis).strip()},
            {"role": "user", "content": REASONING_ANSWER},
        ]
        await self._narrate(self.llm.chat(answer_msgs, **gen))

    async def _code_gen(self) -> dict:
        model = self.settings.code_model
        base = {
            "num_predict": self.settings.num_predict,
            "num_ctx": self.settings.num_ctx,
            "temperature": 0.12,
        }
        if model and await self.llm.has_model(model, refresh=True):
            self._active_model = model
            return {"model": model, **base}
        self._active_model = self.settings.model
        return base

    async def _doc_gen(self) -> dict:
        self._active_model = self.settings.model
        return {
            "num_predict": self.settings.reason_num_predict,
            "num_ctx": self.settings.reason_num_ctx,
            "temperature": 0.12,
        }

    def _ctx(self) -> int:
        return self.settings.num_ctx if self.settings.num_ctx > 0 else 8192

    async def _run_attach(self, name: str, content: str, ask: str) -> None:
        run_id = self._run_id
        self._active_run = run_id
        label = f"{ask} [{Path(name).name}]"
        self.partial = label
        self.reply = ""
        self.session.add_user(label)
        self.memory.observe(ask)
        await self._go(AuraState.THINKING)
        await self.emit({"type": "user", "text": label})
        try:
            result = await asyncio.to_thread(from_attachment, name, content)
            await self._answer_read(result, ask)
        except LlmError as exc:
            self.error_detail = str(exc)
            self.pending_model = exc.needs_model
            self.pending_pull = exc.model or self.settings.model
            self.reply = str(exc)
            await self._go(AuraState.ERROR)
            await asyncio.sleep(0.4)
        except Exception as exc:
            log.exception("falha no anexo %s", name)
            await self._speak_result(f"Não consegui processar {Path(name).name}, senhor. {exc}")
        except asyncio.CancelledError:
            raise
        finally:
            await self._task_done(run_id)

    async def _run_attach_binary(self, name: str, data_b64: str, ask: str) -> None:
        run_id = self._run_id
        self._active_run = run_id
        label = f"{ask} [{Path(name).name}]"
        self.partial = label
        self.reply = ""
        self.session.add_user(label)
        self.memory.observe(ask)
        await self._go(AuraState.THINKING)
        await self.emit({"type": "user", "text": label})
        try:
            result = await asyncio.to_thread(from_attachment_b64, name, data_b64)
            if wants_doc_image_edit(ask):
                ok, msg = await asyncio.to_thread(insert_from_b64, ask, name, data_b64)
                await self._speak_result(msg)
                return
            if wants_deliver(ask) and result.kind == "image" and result.image_b64:
                raw = base64.b64decode(result.image_b64)
                path = await asyncio.to_thread(deliver_bytes, name, raw)
                await self._speak_result(f"Imagem salva em {path}, senhor.")
                return
            await self._answer_read(result, ask)
        except LlmError as exc:
            self.error_detail = str(exc)
            self.pending_model = exc.needs_model
            self.pending_pull = exc.model or self.settings.model
            self.reply = str(exc)
            await self._go(AuraState.ERROR)
            await asyncio.sleep(0.4)
        except Exception as exc:
            log.exception("falha no anexo binário %s", name)
            await self._speak_result(f"Não consegui processar {Path(name).name}, senhor. {exc}")
        except asyncio.CancelledError:
            raise
        finally:
            await self._task_done(run_id)

    async def _clip_chat(self, text: str) -> None:
        clip = await asyncio.to_thread(get_clipboard)
        if not clip.strip():
            await self._speak_result("A área de transferência está vazia, senhor.")
            return
        messages = [
            {"role": "system", "content": self._prompt()},
            {"role": "user", "content": clip_prompt(text, clip[:24_000])},
        ]
        gen = await self._code_gen() if wants_code(text) else self._chat_opts()
        await self._narrate(self.llm.chat(messages, **gen))

    async def _reminder_loop(self) -> None:
        while True:
            await asyncio.sleep(12)
            if self.machine.state is not AuraState.IDLE:
                continue
            due = self.memory.pop_due()
            if not due:
                continue
            msg = "Lembrete, senhor. " + " ".join(r.get("text", "") for r in due)
            self.reply = ""
            await self._speak_result(msg)

    def _prompt(self) -> str:
        base = system_prompt(self.settings, self.memory.render())
        extra = compact_context(self._briefing_ctx)
        briefing = (
            "\nVocê tem acesso a agenda, e-mails triados e notícias do senhor. "
            "Comandos: minha agenda, próximo compromisso, meus e-mails, notícias, bom dia."
        )
        if extra:
            return base + "\n" + extra + briefing
        return base + briefing

    async def _triage_emails(self, emails: list) -> None:
        if not emails:
            await self.emit({"type": "triage_result", "items": []})
            return
        try:
            items = await triage_batch(self.llm, emails)
        except Exception:
            items = heuristic_triage(emails)
        await self.emit({"type": "triage_result", "items": items})

    async def _run_digest(self, pkg: dict[str, Any]) -> None:
        await self._go(AuraState.THINKING)
        self.partial = "Montando seu briefing…"
        await self._broadcast()
        try:
            text = await build_digest(self.llm, pkg, short=True)
        except Exception:
            text = offline_digest(pkg)
        self.session.add_assistant(text)
        await self._speak_result(text)
        await self.emit({"type": "digest_ready", "text": text})
        await self._broadcast()

    async def _speak_result(self, text: str) -> None:
        if self._run_id != self._active_run:
            return
        self.session.add_assistant(text)
        self.reply = text
        await self.emit({"type": "assistant_delta", "text": text})
        if self.machine.state is AuraState.THINKING:
            await self._go(AuraState.SPEAKING)
        self.speech.enqueue(text)
        asyncio.create_task(self._await_speech(self._active_run))

    def _clip_from_thread(self, text: str, duration: float) -> None:
        if self._loop is None or self.machine.state is AuraState.SPEAKING:
            return
        self._loop.call_soon_threadsafe(self._mark_speaking)

    def _mark_speaking(self) -> None:
        if self.machine.state is AuraState.THINKING:
            self.machine.go(AuraState.SPEAKING)

    async def pause(self) -> None:
        await self.stop_speech()
        self.mic_on = False
        await self._go(AuraState.PAUSED)

    async def resume(self) -> None:
        if self.machine.state is AuraState.PAUSED:
            await self._go(AuraState.IDLE)

    async def stop_speech(self) -> None:
        self._speak_id += 1
        self.speech.stop()
        if self.machine.state is AuraState.SPEAKING:
            await self._go(AuraState.IDLE)

    async def ptt(self) -> None:
        if self.machine.state is AuraState.PAUSED:
            return
        self.mic_on = True
        self.error_detail = "Ouvindo… fale agora."
        await self._go(AuraState.LISTENING)
        try:
            text = await asyncio.to_thread(listen)
        except Exception as exc:
            self.error_detail = f"Microfone falhou: {exc}"
            self.mic_on = False
            await self._go(AuraState.IDLE)
            return
        self.mic_on = False
        if not text:
            self.error_detail = "Não ouvi nada, senhor. Fale perto do microfone do PC (não da webcam)."
            await self._go(AuraState.IDLE)
            return
        self.error_detail = f"Ouvi: «{text}»"
        await self.emit({"type": "heard", "text": text})
        await self._broadcast()
        await asyncio.sleep(0.15)
        self.error_detail = ""
        await self.chat(text)

    async def pull_model(self) -> None:
        name = self.pending_pull or self.settings.model
        self.pending_model = False
        self.pending_pull = ""
        await self._go(AuraState.THINKING)
        try:
            async for status in self.llm.pull(name):
                self.reply = f"Baixando {name}: {status}"
                await self._broadcast()
            self.error_detail = ""
            self.reply = f"Modelo {name} pronto, senhor."
            await self._go(AuraState.IDLE)
        except LlmError as exc:
            self.error_detail = str(exc)
            await self._go(AuraState.ERROR)

    async def _go(self, target: AuraState) -> None:
        try:
            self.machine.go(target)
        except TransitionError:
            if target is AuraState.IDLE:
                self.machine.state = AuraState.IDLE
            else:
                return
        if target is AuraState.IDLE:
            self.mic_on = False
        await self._broadcast()

    async def _broadcast(self) -> None:
        await self.emit(self.snapshot())
