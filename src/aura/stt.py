from __future__ import annotations
import logging

import numpy as np

log = logging.getLogger("aura.stt")
_MODEL = None
_INPUT: int | None = None
_RATE = 16000
_SECONDS = 7.0
_MODEL_NAME = "base"
_PROMPT = "Aura, assistente pessoal. Português do Brasil."


def _pick_input_device() -> int | None:
    import sounddevice as sd

    skip = ("webcam", "hdmi", "output", "stereo mix", "mixagem", "line in", "entrada")
    prefer = ("microfone", "mic", "realtek", "headset", "jbl", "fone")
    best: tuple[int, int, str] | None = None
    for i, dev in enumerate(sd.query_devices()):
        if dev.get("max_input_channels", 0) <= 0:
            continue
        name = dev["name"]
        low = name.lower()
        if any(s in low for s in skip):
            continue
        score = sum(4 for p in prefer if p in low)
        if best is None or score > best[0]:
            best = (score, i, name)
    if best is None:
        return None
    log.info("microfone: %s", best[2])
    return best[1]


def _input_device() -> int | None:
    global _INPUT
    if _INPUT is None:
        _INPUT = _pick_input_device()
    return _INPUT


def warmup() -> None:
    _whisper()


def listen(*, seconds: float = _SECONDS) -> str:
    import sounddevice as sd

    dev = _input_device()
    frames = int(seconds * _RATE)
    kwargs: dict = {"samplerate": _RATE, "channels": 1, "dtype": "float32"}
    if dev is not None:
        kwargs["device"] = dev
    audio = sd.rec(frames, **kwargs)
    sd.wait()
    samples = np.squeeze(audio).astype(np.float32)
    peak = float(np.max(np.abs(samples))) if samples.size else 0.0
    if peak < 0.006:
        return ""
    samples = samples * (0.92 / peak)
    model = _whisper()
    segments, _info = model.transcribe(
        samples,
        language="pt",
        task="transcribe",
        vad_filter=False,
        beam_size=3,
        temperature=0.0,
        initial_prompt=_PROMPT,
        condition_on_previous_text=False,
    )
    text = " ".join(s.text.strip() for s in segments).strip()
    if text:
        log.info("ouvi: %s", text)
    return text


def _whisper():
    global _MODEL
    if _MODEL is None:
        from faster_whisper import WhisperModel

        from aura.config import data_dir

        cache = data_dir() / "whisper"
        cache.mkdir(parents=True, exist_ok=True)
        log.info("carregando whisper %s", _MODEL_NAME)
        _MODEL = WhisperModel(_MODEL_NAME, device="cpu", compute_type="int8", download_root=str(cache))
    return _MODEL
