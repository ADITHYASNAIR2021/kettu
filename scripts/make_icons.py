"""Draws Kettu's app icons (an ear made of sound arcs) into web/public/icons.

Run once: python scripts/make_icons.py   (needs Pillow: pip install pillow)
"""

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "web" / "public" / "icons"
LATERITE = (181, 69, 43)
PAPER = (246, 239, 228)
TURMERIC = (226, 163, 59)


def draw(size: int, maskable: bool) -> Image.Image:
    scale = 4  # supersample for smooth arcs
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if maskable:
        d.rectangle([0, 0, s, s], fill=LATERITE)
        inset = 0.20
    else:
        d.rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.23), fill=LATERITE)
        inset = 0.14
    box = s * (1 - 2 * inset)
    ox = oy = s * inset
    cx, cy = ox + box * 0.60, oy + box * 0.5
    stroke = int(box * 0.085)
    # three sound arcs arriving from the left at a listener (the dot): "heard"
    for i, r in enumerate([0.16, 0.31, 0.46]):
        rad = box * r
        color = TURMERIC if i == 0 else PAPER
        d.arc([cx - rad, cy - rad, cx + rad, cy + rad], start=125, end=235, fill=color, width=stroke)
    dot = box * 0.075
    d.ellipse([cx - dot + box * 0.12, cy - dot, cx + dot + box * 0.12, cy + dot], fill=TURMERIC)
    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for size in (192, 512):
        draw(size, maskable=False).save(OUT / f"icon-{size}.png")
        draw(size, maskable=True).save(OUT / f"maskable-{size}.png")
    draw(180, maskable=True).convert("RGB").save(OUT / "apple-touch-icon.png")
    print("icons written to", OUT)


if __name__ == "__main__":
    main()
