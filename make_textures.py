"""
Draws PNG textures for build_endurace.py (needs Pillow, system python3):
  bryton_screen.png - Bryton Rider S510 data page (Traditional Chinese)
  bryton_logo.png   - bryton logo under the screen
  enve_logo.png     - ENVE rim sticker (official logo, cropped)
  tyre_print.png    - Schwalbe Pro One Evo sidewall print

Run:  python3 make_textures.py
"""
import os
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.dirname(os.path.abspath(__file__))
PX = 20                                   # pixels per mm
SCREEN_W, SCREEN_H = 43 * PX, 58 * PX     # 43 x 58 mm active area

CJK = "/System/Library/Fonts/Hiragino Sans GB.ttc"
DIGITS = "/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf"
ROUNDED = "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf"

BG = (232, 234, 246)
INK = (12, 12, 14)
LINE = (150, 60, 80)
ROSE = (200, 146, 126)

def cjk(size):
    try:
        return ImageFont.truetype(CJK, size, index=1)     # W6 weight
    except OSError:
        return ImageFont.truetype(CJK, size, index=0)

def centered(d, cx, y, text, font):
    w = d.textlength(text, font=font)
    d.text((cx - w / 2, y), text, font=font, fill=INK)

def unit_vertical(d, x, y_bottom, unit, font):
    """Stack unit letters vertically at the right edge, ending at y_bottom (like the S510)."""
    h = font.size * 0.95
    for i, ch in enumerate(unit):
        d.text((x, y_bottom - (len(unit) - i) * h), ch, font=font, fill=INK)

def field(d, box, label, value, unit, value_size):
    x0, y0, x1, y1 = box
    cx = (x0 + x1) / 2
    centered(d, cx, y0 + 6, label, cjk(54))
    centered(d, cx, y0 + 70, value, ImageFont.truetype(DIGITS, value_size))
    if unit:
        unit_vertical(d, x1 - 34, y1 - 8, unit, ImageFont.truetype(DIGITS, 40))

def screen():
    im = Image.new("RGB", (SCREEN_W, SCREEN_H), BG)
    d = ImageDraw.Draw(im)
    W, H = SCREEN_W, SCREEN_H
    rows = [int(H * f) for f in (0, 0.205, 0.405, 0.6, 0.8, 1.0)]
    mid = int(W * 0.505)
    # made-up mid-ride numbers
    field(d, (0, rows[0], W, rows[1]), "3秒功率", "215", "W", 170)
    field(d, (0, rows[1], W, rows[2]), "心率", "142", "bpm", 170)
    field(d, (0, rows[2], mid, rows[3]), "速度", "31.4", "kmh", 150)
    field(d, (mid, rows[2], W, rows[3]), "距離", "42.6", "km", 150)
    field(d, (0, rows[3], mid, rows[4]), "總升高度", "386", "m", 150)
    field(d, (mid, rows[3], W, rows[4]), "大盤", "1/2", "", 150)
    field(d, (0, rows[4], mid, rows[5]), "騎乘時間", "1:24:37", "", 140)
    field(d, (mid, rows[4], W, rows[5]), "終點距離", "18.3", "km", 150)
    for y in rows[1:-1]:
        d.line([(0, y), (W, y)], fill=LINE, width=3)
    d.line([(mid, rows[2]), (mid, H)], fill=LINE, width=3)
    # recording indicator
    d.ellipse((20, 20, 96, 96), fill=(205, 80, 170))
    d.polygon([(46, 38), (46, 78), (80, 58)], fill=(255, 255, 255))
    im.save(os.path.join(OUT, "bryton_screen.png"))

def logo():
    im = Image.new("RGBA", (30 * PX, 7 * PX), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    s = 7 * PX
    # icon: rounded "b" badge
    d.rounded_rectangle((4, 8, s - 12, s - 4), radius=34, outline=ROSE, width=14)
    d.rectangle((4, 8, 30, s // 2), fill=ROSE)
    d.ellipse((s * 0.33, s * 0.45, s * 0.43, s * 0.55), fill=ROSE)
    d.ellipse((s * 0.55, s * 0.45, s * 0.65, s * 0.55), fill=ROSE)
    d.text((s + 8, 2), "bryton", font=ImageFont.truetype(ROUNDED, 118), fill=ROSE)
    im.save(os.path.join(OUT, "bryton_logo.png"))

def enve():
    """ENVE rim sticker from the official logo (enve.com header PNG), cropped to the artwork."""
    src = os.path.join(OUT, "enve_logo_official.png")
    im = Image.open(src).convert("RGBA")
    alpha = im.split()[3]
    box = alpha.getbbox()
    pad = 4
    box = (box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad)
    logo = Image.new("RGBA", im.size, (255, 255, 255, 0))
    logo.putalpha(alpha)                                  # pure white, keep the official alpha
    logo = logo.crop(box)
    logo.save(os.path.join(OUT, "enve_logo.png"))
    print(f"enve_logo.png {logo.size[0]}x{logo.size[1]} (aspect {logo.size[0] / logo.size[1]:.3f})")

def tyre_print():
    """Schwalbe Pro One Evo sidewall strip (260 x 8 mm): SCHWALBE | bar block with red bar | PRO ONE | small print."""
    PXMM, W, H = 12, 260, 8
    im = Image.new("RGBA", (W * PXMM, H * PXMM), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    grey, red = (205, 205, 208, 255), (215, 35, 35, 255)
    big = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Black.ttf", int(6.6 * PXMM))
    small = ImageFont.truetype(DIGITS, int(3.6 * PXMM))
    x = 2 * PXMM
    def text(t, font, y, col=grey):
        nonlocal x
        d.text((x, y), t, font=font, fill=col)
        x += d.textlength(t, font=font)
    text("SCHWALBE", big, -0.6 * PXMM)
    x += 4 * PXMM
    for k in range(5):                                       # bar block
        d.rectangle((x, 1.2 * PXMM, x + 1.1 * PXMM, 6.8 * PXMM), fill=grey)
        x += 2.0 * PXMM
    d.rectangle((x, 1.2 * PXMM, x + 6 * PXMM, 6.8 * PXMM), fill=red)
    x += 8 * PXMM
    text("PRO ONE", big, -0.6 * PXMM)
    x += 6 * PXMM
    text("EVOLUTION LINE  \u00b7  ADDIX RACE  \u00b7  TLE  \u00b7  32-622", small, 2.0 * PXMM)
    box = im.split()[3].getbbox()
    im = im.crop((0, 0, box[2] + 2 * PXMM, H * PXMM))     # trim unused length, keep full height
    im.save(os.path.join(OUT, "tyre_print.png"))
    print(f"tyre_print.png aspect {im.size[0] / im.size[1]:.3f}")

if __name__ == "__main__":
    screen()
    logo()
    enve()
    tyre_print()
    print("wrote bryton_screen.png, bryton_logo.png, enve_logo.png, tyre_print.png")
