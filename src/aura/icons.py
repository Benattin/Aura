from __future__ import annotations

from PIL import Image, ImageDraw

from aura.config import ICON_ICO, ICON_PNG

_BG = (5, 5, 5, 255)
_GOLD = (212, 175, 55, 255)
_GOLD_DIM = (138, 112, 32, 220)


def ensure_icons() -> Path:
    ICON_PNG.parent.mkdir(parents=True, exist_ok=True)
    if ICON_ICO.exists() and ICON_PNG.exists():
        return ICON_ICO
    img = _globe(256)
    img.save(ICON_PNG)
    img.save(
        ICON_ICO,
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    return ICON_ICO


def _globe(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), _BG)
    d = ImageDraw.Draw(img)
    pad = size * 0.14
    box = (pad, pad, size - pad, size - pad)
    d.ellipse(box, outline=_GOLD, width=max(3, size // 28))
    cx = cy = size / 2
    r = (size - 2 * pad) / 2
    for i in range(1, 4):
        dx = r * (i / 4) * 0.85
        d.ellipse((cx - dx, pad, cx + dx, size - pad), outline=_GOLD_DIM, width=max(1, size // 64))
    for i in range(1, 4):
        y = pad + (size - 2 * pad) * i / 4
        d.arc(box, 0, 360, fill=_GOLD_DIM, width=max(1, size // 64))
        d.line((pad + 4, y, size - pad - 4, y), fill=_GOLD_DIM, width=max(1, size // 80))
    return img
