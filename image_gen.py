"""
Image generator — creates branded 1080x1080 Instagram post cards from text.
Vishleshak Market Brief theme (dark purple). Saves PNG to static/posts/.

Requires Pillow. Fonts: uses DejaVu (installed via Dockerfile apt fonts-dejavu-core),
with graceful fallback to PIL default if unavailable.
"""
import os
import base64
import textwrap
from datetime import datetime

import requests

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")


def upload_to_imgbb(image_path):
    """
    Upload a local image to imgbb and return a public URL that Meta reliably fetches.
    Returns the URL string, or None on failure / if no key set.
    """
    if not IMGBB_API_KEY:
        return None
    try:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        resp = requests.post(
            "https://api.imgbb.com/1/upload",
            data={"key": IMGBB_API_KEY, "image": b64},
            timeout=30,
        ).json()
        if resp.get("success"):
            return resp["data"]["url"]
        print(f"imgbb upload failed: {resp}")
        return None
    except Exception as e:
        print(f"imgbb error: {e}")
        return None

# Theme
BG_TOP = (45, 10, 110)       # deep purple
BG_BOTTOM = (26, 58, 122)    # blue
CARD = (19, 19, 31)
WHITE = (241, 245, 249)
MUTED = (180, 190, 210)
ACCENT = (167, 139, 250)     # light purple
GREEN = (16, 185, 129)
RED = (239, 68, 68)

W = H = 1080
POSTS_DIR = os.path.join("static", "posts")

FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
]
FONT_BOLD_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def _font(size, bold=False):
    paths = FONT_BOLD_PATHS + FONT_PATHS if bold else FONT_PATHS
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _sanitize_line(line):
    """
    Replace emojis (which the image font can't render → □) with clean glyphs,
    and return (clean_text, color). DejaVu renders ▲ ▼ ● fine.
    """
    s = line
    color = WHITE
    # Determine direction/color from leading marker
    if s.startswith(("📈", "🟢", "+")):
        color = GREEN
    elif s.startswith(("📉", "🔴", "-")):
        color = RED

    # Replace meaningful arrows with clean triangles
    s = s.replace("📈", "▲").replace("📉", "▼")
    s = s.replace("🟢", "▲").replace("🔴", "▼")

    # Strip decorative emojis that have no text meaning
    for e in ["📊", "📋", "📌", "🏭", "👀", "🌍", "🌅", "🌄", "💛", "⚪",
              "📰", "🏆", "⭐", "💡", "🔥", "✅", "❌", "⚠️", "️"]:
        s = s.replace(e, "")
    return s.strip(), color


def _gradient_bg():
    img = Image.new("RGB", (W, H), BG_TOP)
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))
    return img


def generate_post_image(title, time_label, body_lines, filename):
    """
    Create a branded post image.
      title       - main heading (e.g. "Pre-Market Watchlist")
      time_label  - small label (e.g. "9:00 AM • 4 June 2026")
      body_lines  - list of strings (each rendered as a line/bullet)
      filename    - output filename (saved under static/posts/)
    Returns the relative path, or None if PIL unavailable.
    """
    if not PIL_AVAILABLE:
        print("Pillow not available — cannot generate image")
        return None

    os.makedirs(POSTS_DIR, exist_ok=True)
    img = _gradient_bg()
    draw = ImageDraw.Draw(img)

    # Header: logo box + brand
    draw.rounded_rectangle([60, 60, 150, 150], radius=18, fill=ACCENT)
    draw.text((85, 78), "V", font=_font(60, bold=True), fill=WHITE)
    draw.text((170, 72), "Vishleshak Market Brief", font=_font(38, bold=True), fill=WHITE)
    draw.text((170, 120), "AI-powered daily market intelligence", font=_font(22), fill=MUTED)

    # Time label
    draw.text((60, 200), time_label.upper(), font=_font(26, bold=True), fill=ACCENT)

    # Title (wrapped)
    y = 250
    for line in textwrap.wrap(title, width=24):
        draw.text((60, y), line, font=_font(64, bold=True), fill=WHITE)
        y += 78
    y += 20

    # Divider
    draw.line([(60, y), (W - 60, y)], fill=(80, 70, 120), width=2)
    y += 40

    # Body lines
    body_font = _font(34)
    for raw in body_lines:
        clean, color = _sanitize_line(raw)
        for wrapped in textwrap.wrap(clean, width=42) or [""]:
            draw.text((60, y), wrapped, font=body_font, fill=color)
            y += 46
        y += 8
        if y > H - 160:
            break

    # Footer
    draw.rectangle([0, H - 110, W, H], fill=CARD)
    draw.text((60, H - 88), "Full brief → vishleshak.in/news", font=_font(30, bold=True), fill=ACCENT)
    draw.text((60, H - 48), "@vishleshak.market.brief  •  Educational only, not investment advice",
              font=_font(20), fill=MUTED)

    # Instagram Graph API requires JPEG (PNG is rejected)
    if filename.lower().endswith(".png"):
        filename = filename[:-4] + ".jpg"
    path = os.path.join(POSTS_DIR, filename)
    img.save(path, "JPEG", quality=92)
    return path
