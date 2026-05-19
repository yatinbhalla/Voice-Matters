"""Generate placeholder PWA icons: teal square with white centered mic glyph.
Bhavesh will replace these with proper brand icons in Sprint C.
Run: python web/icons/_gen_icons.py
"""
from PIL import Image, ImageDraw
from pathlib import Path

TEAL = (42, 157, 181, 255)  # #2A9DB5
WHITE = (255, 255, 255, 255)
OUT_DIR = Path(__file__).parent


def draw_mic(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), TEAL)
    d = ImageDraw.Draw(img)
    cx = size / 2
    # Capsule body of the mic
    body_w = size * 0.28
    body_h = size * 0.40
    body_top = size * 0.18
    body_box = (cx - body_w / 2, body_top, cx + body_w / 2, body_top + body_h)
    d.rounded_rectangle(body_box, radius=int(body_w / 2), fill=WHITE)
    # U-shaped stand (arc)
    arc_pad = size * 0.18
    arc_box = (arc_pad, size * 0.30, size - arc_pad, size * 0.78)
    arc_width = max(2, int(size * 0.045))
    d.arc(arc_box, start=20, end=160, fill=WHITE, width=arc_width)
    # Vertical stem
    stem_top = size * 0.66
    stem_bot = size * 0.80
    d.rounded_rectangle(
        (cx - arc_width / 2, stem_top, cx + arc_width / 2, stem_bot),
        radius=arc_width // 2,
        fill=WHITE,
    )
    # Base bar
    base_w = size * 0.22
    base_h = size * 0.035
    d.rounded_rectangle(
        (cx - base_w / 2, stem_bot, cx + base_w / 2, stem_bot + base_h),
        radius=int(base_h / 2),
        fill=WHITE,
    )
    return img


for s in (192, 512):
    draw_mic(s).save(OUT_DIR / f"icon-{s}.png", "PNG")
    print(f"wrote icon-{s}.png")
