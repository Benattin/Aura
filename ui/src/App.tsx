import { ChangeEvent, FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";
import Globe from "./Globe";
import CommandCenter from "./components/CommandCenter";

type ChatItem = { id: string; title: string };
type Turn = { role: "user" | "aura"; text: string };

type Snap = {
  type: string;
  state: string;
  label: string;
  model: string;
  activeModel?: string;
  codeModel?: string;
  privacy: string;
  mic: boolean;
  tts: boolean;
  error: string;
  partial: string;
  reply: string;
  pendingModel: boolean;
  pendingName?: string;
  followup: boolean;
  paused: boolean;
  memoryCount?: number;
  text?: string;
  history?: ChatItem[];
  chatId?: string;
  turns?: Turn[];
  workspace?: string;
  workspaceProject?: string;
};

const empty: Snap = {
  type: "snapshot", state: "initializing", label: "Inicializando", model: "—",
  privacy: "local", mic: false, tts: false, error: "", partial: "", reply: "",
  pendingModel: false, followup: false, paused: false, memoryCount: 0,
  history: [], chatId: "",
};

function modelLabel(snap: Snap) {
  const m = snap.activeModel || snap.model;
  if (!m || m === "—") return "—";
  return m.split(":")[0].replace("qwen2.5-coder", "coder");
}

const BINARY_EXT = /\.(pdf|docx?|xlsx?|pptx?|png|jpe?g|gif|webp|bmp|jfif)$/i;

const QUICK = [
  { label: "Bom dia", text: "bom dia" },
  { label: "Agenda", text: "minha agenda" },
  { label: "Projeto", text: "crie um projeto demo na aura com main.py em python" },
  { label: "Resumo", text: "resumo do dia" },
  { label: "Ajuda", text: "ajuda" },
  { label: "Arquivo", action: "file" as const },
];

export default function App() {
  const [snap, setSnap] = useState<Snap>(empty);
  const [draft, setDraft] = useState("");
  const [log, setLog] = useState<Turn[]>([]);
  const [histOpen, setHistOpen] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const feedRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const fileRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws`);
    wsRef.current = ws;
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data) as Snap;
      if (msg.type === "user" && msg.text) {
        setSnap((s) => ({ ...s, reply: "", partial: msg.text! }));
      }
      if (msg.type === "assistant_delta" && msg.text) {
        setSnap((s) => ({
          ...s,
          reply: s.reply + msg.text,
          state: "speaking",
          label: "Falando",
        }));
      }
      if (msg.type === "digest_ready" && (msg as { text?: string }).text) {
        setLog((prev) => [...prev, { role: "aura", text: (msg as { text: string }).text }]);
      }
      if (msg.type === "briefing_refresh") {
        window.dispatchEvent(new Event("aura-refresh"));
      }
      if (msg.type === "snapshot") {
        setSnap((prev) => ({
          ...msg,
          reply:
            msg.partial && msg.partial !== prev.partial
              ? msg.reply || ""
              : (msg.state === "speaking" || msg.state === "thinking") &&
                prev.reply.length > (msg.reply?.length || 0)
                ? prev.reply
                : msg.reply || "",
        }));
        if (msg.turns) setLog(msg.turns);
      }
    };
    return () => ws.close();
  }, []);

  useEffect(() => {
    feedRef.current?.scrollTo({
      top: feedRef.current.scrollHeight,
      behavior: snap.state === "speaking" || snap.state === "thinking" ? "auto" : "smooth",
    });
  }, [log, snap.reply, snap.state]);

  const send = (payload: object) => {
    wsRef.current?.readyState === WebSocket.OPEN && wsRef.current.send(JSON.stringify(payload));
  };

  const onPickFile = async (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    const ask = draft.trim() || "Analise este arquivo: resuma o conteúdo e responda ao pedido.";
    setDraft("");
    setSnap((s) => ({
      ...s,
      reply: "",
      partial: `${ask} [${f.name}]`,
      error: "Enviando e analisando arquivo…",
      state: "thinking",
      label: "Analisando",
    }));
    if (BINARY_EXT.test(f.name)) {
      const fd = new FormData();
      fd.append("file", f);
      fd.append("ask", ask);
      const ctrl = new AbortController();
      const timer = window.setTimeout(() => ctrl.abort(), 180_000);
      try {
        const res = await fetch("/api/upload", { method: "POST", body: fd, signal: ctrl.signal });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const msg = (await res.json()) as Snap & { ok?: boolean };
        if (msg.turns) setLog(msg.turns);
        setSnap((s) => ({ ...s, ...msg, reply: msg.reply || "", error: msg.error || "" }));
        if (msg.ok === false) {
          setSnap((s) => ({ ...s, error: msg.error || "Falha ao processar o arquivo." }));
        }
      } catch (err) {
        const timeout = err instanceof DOMException && err.name === "AbortError";
        setSnap((s) => ({
          ...s,
          state: "idle",
          label: "Em espera",
          error: timeout
            ? "O arquivo demorou demais. Tente um PDF menor ou aguarde o modelo carregar."
            : "Falha ao enviar o arquivo. Reinicie a AURA e use o botão Arquivo.",
        }));
      } finally {
        window.clearTimeout(timer);
      }
      return;
    }
    const buf = await f.arrayBuffer();
    send({ type: "file", name: f.name, text: new TextDecoder().decode(buf), ask });
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    const text = draft.trim();
    if (!text) return;
    setDraft("");
    setLog((prev) => [...prev, { role: "user", text }]);
    setSnap((s) => ({
      ...s,
      reply: "",
      partial: text,
      error: "",
      state: "thinking",
      label: "Pensando",
    }));
    send({ type: "chat", text });
    inputRef.current?.focus();
  };

  const onKey = (e: KeyboardEvent) => {
    if (e.key === "Escape") {
      setHistOpen(false);
      send({ type: "stop" });
    }
  };

  const live = snap.state === "thinking" || snap.state === "speaking" || snap.state === "listening";
  const busy = snap.paused ? "Pausada" : live ? snap.label : "Em espera";
  const last = log[log.length - 1];
  const showLive = live && !(last?.role === "aura" && last.text === snap.reply);
  const showPartial = live && snap.partial && snap.state === "thinking";

  return (
    <div className={`app ${snap.state}`} onKeyDown={onKey}>
      <aside className="visual-pane">
        <header className="visual-top">
          <div className="visual-brand">
            <span className="logo" aria-hidden="true">A</span>
            <div>
              <span className="visual-title">AURA</span>
              <span className="visual-sub">Interface neural · processamento local</span>
            </div>
          </div>
          <div className={`status-chip ${snap.state}`}>
            <span className="status-dot" />
            {busy}
          </div>
        </header>

        <div className="visual-stage">
          <Globe state={snap.state} />
          <div className="visual-status">{busy}</div>
        </div>

        <footer className="visual-foot">
          <div className="metric">
            <span className="metric-label">Modelo</span>
            <span className="metric-value">{modelLabel(snap)}</span>
          </div>
          <div className="metric">
            <span className="metric-label">Privacidade</span>
            <span className="metric-value">Local</span>
          </div>
          <div className="metric">
            <span className="metric-label">Voz</span>
            <span className="metric-value">{snap.tts ? "Ativa" : "Off"}</span>
          </div>
          <div className="metric" title={snap.workspace || ""}>
            <span className="metric-label">Projeto</span>
            <span className="metric-value">{snap.workspaceProject || "—"}</span>
          </div>
        </footer>
      </aside>

      <main className="workspace">
        <header className="workspace-head">
          <div>
            <h1>Conversa</h1>
            <p>Comandos por texto, voz ou arquivo</p>
          </div>
          <button
            type="button"
            className={`btn-icon ${histOpen ? "on" : ""}`}
            onClick={() => setHistOpen((v) => !v)}
            aria-label="Histórico"
          >
            Histórico
          </button>
        </header>

        {histOpen && (
          <section className="history-panel">
            <div className="history-head">
              <span>Sessões anteriores</span>
              <button type="button" className="btn-text" onClick={() => setHistOpen(false)}>Fechar</button>
            </div>
            <button
              type="button"
              className="history-new"
              onClick={() => {
                send({ type: "history_new" });
                setHistOpen(false);
              }}
            >
              Nova conversa
            </button>
            <div className="history-list">
              {(snap.history || []).map((c) => (
                <button
                  type="button"
                  key={c.id}
                  className={c.id === snap.chatId ? "on" : ""}
                  onClick={() => {
                    send({ type: "history_open", id: c.id });
                    setHistOpen(false);
                  }}
                >
                  {c.title}
                </button>
              ))}
            </div>
          </section>
        )}

        <section className="feed" ref={feedRef}>
          <CommandCenter send={send} />
          {log.length === 0 && !live && (
            <div className="empty">
              <h2>Como posso ajudar?</h2>
              <p>Use os atalhos abaixo ou escreva sua solicitação.</p>
              <div className="quick-grid">
                {QUICK.map((q) => (
                  <button
                    key={q.label}
                    type="button"
                    className={q.action === "file" ? "primary" : ""}
                    onClick={() =>
                      q.action === "file"
                        ? fileRef.current?.click()
                        : send({ type: "chat", text: q.text! })
                    }
                  >
                    <span className="quick-label">{q.label}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
          {log.map((m, i) => (
            <article key={i} className={`bubble ${m.role}`}>
              <header>{m.role === "user" ? "Você" : "AURA"}</header>
              <p>{m.text}</p>
            </article>
          ))}
          {showPartial && (
            <article className="bubble user pending">
              <header>Você</header>
              <p>{snap.partial}</p>
            </article>
          )}
          {showLive && (
            <article className="bubble aura live">
              <header>AURA</header>
              <p>{snap.reply || (snap.state === "listening" ? "Ouvindo…" : "…")}</p>
            </article>
          )}
        </section>

        {snap.error && (
          <p className={`notice ${live ? "info" : "error"}`}>{snap.error}</p>
        )}

        {snap.pendingModel && (
          <div className="notice card">
            <p>Baixar {snap.pendingName || snap.model} neste PC?</p>
            <div className="notice-actions">
              <button type="button" className="btn" onClick={() => send({ type: "confirm_pull" })}>Sim</button>
              <button type="button" className="btn ghost" onClick={() => send({ type: "deny_pull" })}>Não</button>
            </div>
          </div>
        )}

        <footer className="composer-area">
          <nav className="toolbar">
            <button type="button" className="tool" onClick={() => send({ type: "chat", text: "olha a tela" })}>Tela</button>
            <button type="button" className="tool" onClick={() => send({ type: "chat", text: "resumo do dia" })}>Resumo</button>
            <button type="button" className="tool" onClick={() => send({ type: "chat", text: "ajuda" })}>Ajuda</button>
            <button type="button" className="tool primary" onClick={() => fileRef.current?.click()}>Arquivo</button>
            <input ref={fileRef} className="pick" type="file" accept="*/*" onChange={onPickFile} />
          </nav>

          <form className="composer" onSubmit={onSubmit}>
            <input
              ref={inputRef}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Digite sua mensagem…"
              aria-label="Mensagem"
              autoFocus
              autoComplete="off"
              spellCheck={false}
            />
            <button type="submit" className="btn-send" disabled={!draft.trim()}>Enviar</button>
          </form>

          <div className="controls">
            <button
              type="button"
              className={`btn ${snap.mic ? "active" : ""}`}
              onClick={() => send({ type: "ptt" })}
            >
              Falar
            </button>
            <button type="button" className="btn" onClick={() => send({ type: snap.paused ? "resume" : "pause" })}>
              {snap.paused ? "Retomar" : "Pausar"}
            </button>
            <button type="button" className="btn danger" onClick={() => send({ type: "stop" })}>Parar</button>
          </div>
        </footer>
      </main>
    </div>
  );
}
