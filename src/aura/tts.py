from __future__ import annotations
import logging
import queue
import re
import threading
import time
from typing import Callable

import numpy as np

from aura.config import ROOT

log = logging.getLogger("aura.tts")
_SENT = re.compile(r"(.+?[.!?…]+)(?:\s+|$)")
VOICE = ROOT / "assets" / "voices" / "pt_BR-faber-medium.onnx"
OnClip = Callable[[str, float], None]
_OUT_RATE = 44100
_GAP = int(_OUT_RATE * 0.06)


def take_sentences(buf: str) -> tuple[list[str], str]:
    out: list[str] = []
    while True:
        m = _SENT.match(buf)
        if not m:
            break
        piece = m.group(1).strip()
        rest = buf[m.end() :]
        if len(piece) < 8 and rest:
            break
        out.append(piece)
        buf = rest
    return out, buf


def take_utterances(buf: str, *, flush: bool = False) -> tuple[list[str], str]:
    done, rest = take_sentences(buf)
    if done:
        return done, rest
    if flush:
        t = rest.strip()
        return ([t] if t else []), ""
    return [], rest


def _pick_voice_id(engine) -> str | None:
    voices = engine.getProperty("voices") or []
    best, best_score = None, -1
    for v in voices:
        name = f"{getattr(v, 'name', '')} {getattr(v, 'id', '')}".lower()
        score = 0
        if "brazil" in name or "brasil" in name or "pt-br" in name:
            score += 12
        if "portug" in name:
            score += 8
        if "maria" in name:
            score += 4
        if "neural" in name:
            score += 6
        if score > best_score:
            best_score, best = score, v.id
    return best if best_score > 0 else None


def _resample(samples: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    if src_rate == dst_rate or samples.size == 0:
        return samples
    duration = samples.size / float(src_rate)
    out_n = max(1, int(round(duration * dst_rate)))
    t_src = np.linspace(0.0, duration, samples.size, endpoint=False)
    t_dst = np.linspace(0.0, duration, out_n, endpoint=False)
    return np.interp(t_dst, t_src, samples).astype(np.float32)


class _StreamPlayer:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending = np.zeros(0, dtype=np.float32)
        self._idle = threading.Event()
        self._idle.set()
        self._stream = None

    def _on_audio(self, outdata, frames, _time, _status) -> None:
        with self._lock:
            n = min(frames, self._pending.size)
            if n > 0:
                outdata[:n, 0] = self._pending[:n]
                if n < frames:
                    outdata[n:, 0] = 0.0
                self._pending = self._pending[n:]
            else:
                outdata.fill(0.0)
            if self._pending.size == 0:
                self._idle.set()

    def _ensure(self) -> None:
        import sounddevice as sd

        if self._stream is not None:
            try:
                if self._stream.active:
                    return
            except Exception:
                pass
            self._close()
        self._stream = sd.OutputStream(
            samplerate=_OUT_RATE,
            channels=1,
            dtype="float32",
            blocksize=2048,
            latency="high",
            callback=self._on_audio,
        )
        self._stream.start()

    def write(self, samples: np.ndarray, src_rate: int) -> None:
        flat = np.asarray(samples, dtype=np.float32).reshape(-1)
        if flat.size == 0:
            return
        if src_rate != _OUT_RATE:
            flat = _resample(flat, src_rate, _OUT_RATE)
        with self._lock:
            if self._pending.size > 0:
                gap = np.zeros(_GAP, dtype=np.float32)
                self._pending = np.concatenate([self._pending, gap, flat])
            else:
                self._pending = flat.copy()
            self._idle.clear()
        self._ensure()

    def wait_idle(self, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while not self._idle.is_set():
            if time.monotonic() >= deadline:
                return
            time.sleep(0.02)

    def clear(self) -> None:
        with self._lock:
            self._pending = np.zeros(0, dtype=np.float32)
            self._idle.set()
        self._close()

    def _close(self) -> None:
        if self._stream is None:
            return
        try:
            self._stream.abort()
        except Exception:
            pass
        try:
            self._stream.stop()
        except Exception:
            pass
        try:
            self._stream.close()
        except Exception:
            pass
        self._stream = None


class Speech:
    def __init__(self, *, enabled: bool = True, rate: int = 200) -> None:
        self.enabled = enabled
        self.rate = rate
        self._on_clip: OnClip | None = None
        self._texts: queue.Queue[str] = queue.Queue()
        self._clips: queue.Queue[tuple[str, np.ndarray, int]] = queue.Queue(maxsize=32)
        self._player = _StreamPlayer()
        self._engine = None
        self._piper = None
        self._ready = threading.Event()
        self._cancel = threading.Event()
        if enabled:
            threading.Thread(target=self._synth_loop, daemon=True, name="aura-tts-synth").start()
            threading.Thread(target=self._play_loop, daemon=True, name="aura-tts-play").start()

    def set_on_clip(self, fn: OnClip | None) -> None:
        self._on_clip = fn

    def available(self) -> bool:
        return self.enabled

    def enqueue(self, text: str) -> None:
        t = " ".join(text.split())
        if self.enabled and t and t not in {".", "..."}:
            self._cancel.clear()
            self._texts.put(t)

    def drain(self, timeout: float = 120.0) -> None:
        self._texts.join()
        self._clips.join()
        self._player.wait_idle(timeout)

    def stop(self) -> None:
        self._cancel.set()
        self._player.clear()
        for q in (self._texts, self._clips):
            while True:
                try:
                    q.get_nowait()
                    q.task_done()
                except queue.Empty:
                    break
        if self._engine is not None:
            try:
                self._engine.stop()
            except Exception:
                pass

    def warmup(self) -> None:
        self._ready.wait(timeout=20)
        try:
            self._player.write(np.zeros(256, dtype=np.float32), _OUT_RATE)
            self._player.wait_idle(2.0)
        except Exception:
            log.exception("warmup de áudio falhou")

    def _synth_loop(self) -> None:
        from piper.config import SynthesisConfig

        self._piper = _load_piper()
        if self._piper is None:
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.setProperty("rate", self.rate)
                voice = _pick_voice_id(engine)
                if voice:
                    engine.setProperty("voice", voice)
                self._engine = engine
            except Exception:
                pass
        else:
            _warm_piper(self._piper)
        self._ready.set()
        cfg = SynthesisConfig(length_scale=0.86, noise_scale=0.38)
        while True:
            text = self._texts.get()
            try:
                if self._cancel.is_set():
                    continue
                if self._piper is None:
                    continue
                parts: list[np.ndarray] = []
                out_rate = 22050
                for chunk in self._piper.synthesize(text, syn_config=cfg):
                    if self._cancel.is_set():
                        break
                    audio = np.asarray(chunk.audio_float_array, dtype=np.float32).reshape(-1)
                    if audio.size:
                        parts.append(audio)
                        out_rate = chunk.sample_rate
                if parts:
                    self._put_clip(text, np.concatenate(parts), out_rate)
            finally:
                self._texts.task_done()

    def _put_clip(self, text: str, audio: np.ndarray, rate: int) -> None:
        if self._cancel.is_set():
            return
        for _ in range(60):
            if self._cancel.is_set():
                return
            try:
                self._clips.put((text, audio, rate), timeout=0.3)
                return
            except queue.Full:
                time.sleep(0.05)

    def _play_loop(self) -> None:
        while True:
            text, audio, rate = self._clips.get()
            try:
                if self._cancel.is_set():
                    continue
                duration = float(audio.size) / float(rate or 22050)
                if self._piper is None and self._engine is not None:
                    est = max(len(text.split()) * 0.32, 0.6)
                    if self._on_clip:
                        self._on_clip(text, est)
                    self._engine.say(text)
                    self._engine.runAndWait()
                    continue
                if text and self._on_clip:
                    self._on_clip(text, duration)
                self._player.write(audio, rate)
            except Exception:
                log.exception("falha na reprodução TTS")
            finally:
                self._clips.task_done()


def _load_piper():
    if not VOICE.exists():
        return None
    try:
        from piper import PiperVoice
        try:
            return PiperVoice.load(str(VOICE), use_cuda=False)
        except TypeError:
            return PiperVoice.load(str(VOICE))
    except Exception:
        return None


def _warm_piper(voice) -> None:
    try:
        from piper.config import SynthesisConfig
        cfg = SynthesisConfig(length_scale=0.86, noise_scale=0.38)
        for _ in voice.synthesize("Oi.", syn_config=cfg):
            break
    except Exception:
        pass
