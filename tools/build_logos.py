"""Builds logos/*.png (corner logo presets) from tools/via_source.jpg at 6x resolution."""
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

HERE = Path(__file__).parent
OUT = HERE.parent / "logos"
SCALE = 6
YELLOW, RED, CREAM, DARK = "#FFC72C", "#D52B1E", "#F1E6C8", "#1E2A20"
PRESETS = {  # id: (stripes colour, wordmark colour or None, leaf?)
    "via_yellow": (YELLOW, None, False),
    "via_yellow_full": (YELLOW, "#FFFFFF", True),  # VIA guidelines 2023: on dark backgrounds the name is white
    "via_cream": (CREAM, None, False),
    "via_dark": (DARK, None, False),
    "via_dark_full": (DARK, DARK, False),
}


def masks():
    im = np.asarray(Image.open(HERE / "via_source.jpg").convert("RGB")).astype(int)
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    return {
        "stripes": (r > 200) & (g > 150) & (b < 120) & (r - b > 120),
        "leaf": (r > 180) & (g < 90) & (b < 90),
        "text": (r < 90) & (g < 90) & (b < 90),
    }


def upscale(mask):
    img = Image.fromarray((mask * 255).astype("uint8"), "L")
    big = img.resize((img.width * SCALE, img.height * SCALE), Image.LANCZOS).filter(ImageFilter.GaussianBlur(SCALE * 0.6))
    return np.asarray(big.point(lambda v: 255 if v > 127 else 0)).astype(float) / 255


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    m = {k: upscale(v) for k, v in masks().items()}
    for name, (stripe_c, text_c, leaf) in PRESETS.items():
        layers = [("stripes", stripe_c)] + ([("leaf", RED)] if leaf else []) + ([("text", text_c)] if text_c else [])
        h, w = m["stripes"].shape
        rgba = np.zeros((h, w, 4))
        for key, colour in layers:
            rgb = np.array([int(colour[i:i + 2], 16) for i in (1, 3, 5)]) / 255
            a = m[key][..., None]
            rgba[..., :3] = rgba[..., :3] * (1 - a) + rgb * a
            rgba[..., 3:] = np.maximum(rgba[..., 3:], a)
        img = Image.fromarray((rgba * 255).astype("uint8"), "RGBA")
        img.crop(img.getbbox()).save(OUT / f"{name}.png", optimize=True)
        print(name, img.getbbox())


if __name__ == "__main__":
    build()
