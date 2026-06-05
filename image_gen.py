"""
Image generator — premium 1080x1350 (4:5) branded cards for Instagram + Facebook.
Vishleshak Market Brief theme (deep purple → navy). Poppins typography (bundled in /fonts).

Saves JPEG to static/posts/. Instagram requires JPEG; PNG is auto-converted.
"""
import os
import re
import base64
import textwrap

import requests

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")

# ── Canvas (4:5 portrait — best for IG feed) ──
W, H = 1080, 1350
POSTS_DIR = os.path.join("static", "posts")
_HERE = os.path.dirname(os.path.abspath(__file__))

# ── Palette ──
BG_TOP = (38, 12, 82)        # deep purple
BG_BOTTOM = (12, 18, 44)     # dark navy
WHITE = (244, 246, 252)
MUTED = (165, 174, 200)
FAINT = (120, 128, 160)
ACCENT = (167, 139, 250)     # light purple
ACCENT2 = (124, 92, 246)     # purple
GREEN = (34, 211, 138)
RED = (248, 92, 102)
CHIP_BG = (255, 255, 255, 28)
DIVIDER = (255, 255, 255, 38)
FOOTER_BG = (8, 9, 20)

# ── Fonts (bundled Poppins, fallback to DejaVu/default) ──
_FONT_DIR = os.path.join(_HERE, "fonts")
_FALLBACKS = {
    "bold": ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/segoeuib.ttf"],
    "semibold": ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/segoeuib.ttf"],
    "medium": ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/segoeui.ttf"],
    "regular": ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/segoeui.ttf"],
}
_POPPINS = {
    "bold": "Poppins-Bold.ttf",
    "semibold": "Poppins-SemiBold.ttf",
    "medium": "Poppins-Medium.ttf",
    "regular": "Poppins-Regular.ttf",
}
_font_cache = {}


def _font(size, weight="regular"):
    key = (size, weight)
    if key in _font_cache:
        return _font_cache[key]
    candidates = [os.path.join(_FONT_DIR, _POPPINS[weight])] + _FALLBACKS[weight]
    for p in candidates:
        if os.path.exists(p):
            try:
                f = ImageFont.truetype(p, size)
                _font_cache[key] = f
                return f
            except Exception:
                continue
    f = ImageFont.load_default()
    _font_cache[key] = f
    return f


# ── imgbb upload (Meta fetches it reliably) ──
def upload_to_imgbb(image_path):
    if not IMGBB_API_KEY:
        return None
    try:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        resp = requests.post("https://api.imgbb.com/1/upload",
                             data={"key": IMGBB_API_KEY, "image": b64}, timeout=30).json()
        if resp.get("success"):
            return resp["data"]["url"]
        print(f"imgbb upload failed: {resp}")
    except Exception as e:
        print(f"imgbb error: {e}")
    return None


# ── line classification for premium rendering ──
EMOJI_STRIP = ["📊", "📋", "📌", "🏭", "👀", "🌍", "🌅", "🌄", "💛", "⚪", "📰",
               "🏆", "⭐", "💡", "🔥", "✅", "❌", "⚠️", "️", "🎯"]


def _classify(line):
    """Return (kind, clean_text, color). kind in {header, up, down, plain}."""
    s = line
    color = WHITE
    kind = "plain"
    stripped = s.strip()

    if stripped.startswith(("📈", "🟢", "+")):
        kind, color = "up", GREEN
    elif stripped.startswith(("📉", "🔴", "-")):
        kind, color = "down", RED

    s = s.replace("📈", "").replace("📉", "").replace("🟢", "").replace("🔴", "")
    for e in EMOJI_STRIP:
        s = s.replace(e, "")
    s = s.strip()

    # Section header: short ALL-CAPS label (e.g. GAINERS, LOSERS, TOP HEADLINES, NIFTY KEY LEVELS)
    if kind == "plain" and s and s.upper() == s and len(s) <= 26 and not any(c.isdigit() for c in s[:2]):
        if any(ch.isalpha() for ch in s):
            kind = "header"
    return kind, s, color


def _gradient_bg():
    img = Image.new("RGB", (W, H), BG_TOP)
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
        d.line([(0, y), (W, y)], fill=(r, g, b))
    return img


PILL_BG = (58, 42, 112)      # solid chip purple
HEADER_LINE = (70, 60, 120)


def _draw_triangle(d, x, y, size, up, color):
    """Draw a filled up/down triangle marker (Poppins lacks ▲▼ glyphs)."""
    if up:
        pts = [(x, y + size), (x + size, y + size), (x + size / 2, y)]
    else:
        pts = [(x, y), (x + size, y), (x + size / 2, y + size)]
    d.polygon(pts, fill=color)


def _draw_arrow(d, x, y, length, color, thick=4):
    """Draw a small right-pointing arrow (Poppins lacks → glyph)."""
    cy = y
    d.line([(x, cy), (x + length, cy)], fill=color, width=thick)
    h = 9
    d.polygon([(x + length, cy - h), (x + length + 14, cy), (x + length, cy + h)], fill=color)


# ── Blue/gold "list card" theme (matches the Top-10 sample) ──
LC_BG_TOP = (38, 92, 205)      # royal blue
LC_BG_BOTTOM = (22, 150, 150)  # teal
LC_GOLD = (248, 226, 150)      # pale gold (title)
LC_NUM = (245, 205, 95)        # number gold
LC_ROW = (20, 58, 150)         # row fill
LC_BORDER = (96, 150, 225)     # row border
LC_DESC = (255, 255, 255)      # description text — PURE WHITE for maximum clarity
LC_TOPBAR = (247, 197, 47)     # gold top bar
LC_FOOTER = (8, 12, 34)
LC_GREEN = (76, 224, 140)      # bright green for gainers
LC_RED = (255, 100, 110)       # bright red for losers
LC_CYAN = (100, 220, 255)      # bright cyan for insights/secondary


def _fit_text(d, text, font, maxw):
    """Trim text to fit maxw pixels (adds … if trimmed)."""
    if d.textlength(text, font=font) <= maxw:
        return text
    while text and d.textlength(text + "…", font=font) > maxw:
        text = text[:-1]
    return text.rstrip(" ,;:-") + "…"


def _lc_gradient():
    img = Image.new("RGB", (W, H), LC_BG_TOP)
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        r = int(LC_BG_TOP[0] + (LC_BG_BOTTOM[0] - LC_BG_TOP[0]) * t)
        g = int(LC_BG_TOP[1] + (LC_BG_BOTTOM[1] - LC_BG_TOP[1]) * t)
        b = int(LC_BG_TOP[2] + (LC_BG_BOTTOM[2] - LC_BG_TOP[2]) * t)
        d.line([(0, y), (W, y)], fill=(r, g, b))
    return img


def generate_list_card(tag, title1, title2, subtitle, items, filename, brand_note="", banner=""):
    """
    Premium numbered-list card (matches the Top-10 watchlist sample).
      tag       - small pill label (e.g. "9 AM PRE-MARKET")
      title1    - first title line (white)
      title2    - second title line (gold)
      subtitle  - one-line descriptor
      items     - list of (title, description, color_hint) tuples (color_hint optional: "green"/"red"/None)
      banner    - optional top banner text (e.g. "Global: Dow +0.5% | Crude $92")
    """
    if not PIL_AVAILABLE:
        return None
    os.makedirs(POSTS_DIR, exist_ok=True)
    img = _lc_gradient()
    d = ImageDraw.Draw(img)
    PAD = 64

    # Top gold bar
    d.rectangle([0, 0, W, 14], fill=LC_TOPBAR)

    # Tag pill (white, blue text)
    tf = _font(28, "bold")
    tag = tag.upper()
    tw = d.textlength(tag, font=tf)
    d.rounded_rectangle([PAD, 70, PAD + tw + 56, 126], radius=28, fill=WHITE)
    d.text((PAD + 28, 82), tag, font=tf, fill=(30, 64, 175))

    # Two-tone title
    d.text((PAD - 4, 150), title1, font=_font(118, "bold"), fill=WHITE)
    d.text((PAD - 4, 272), title2, font=_font(96, "bold"), fill=LC_GOLD)

    # Subtitle
    y_pos = 388
    d.text((PAD, y_pos), subtitle, font=_font(31, "regular"), fill=LC_DESC)

    # Optional banner (global snapshot, etc.) — bright white BOLD text
    if banner:
        y_pos += 60
        d.text((PAD, y_pos), banner, font=_font(24, "bold"), fill=WHITE)

    # Numbered rows
    items = items[:10]
    top = y_pos + 56 if banner else 444
    bottom = H - 150
    row_h = (bottom - top) // max(len(items), 1) - 8
    row_h = min(row_h, 92)
    y = top
    num_font = _font(34, "bold")
    it_font = _font(29, "bold")
    de_font = _font(22, "bold")  # BOLD for crystal-clear readability
    for i, item_data in enumerate(items, 1):
        # Handle both 2-tuple (title, desc) and 3-tuple (title, desc, color)
        if len(item_data) == 3:
            it_title, it_desc, color_hint = item_data
        else:
            it_title, it_desc = item_data
            color_hint = None

        # Color logic: bright green for gainers, bright red for losers
        desc_color = LC_DESC  # default: bright white
        if color_hint == "green":
            desc_color = LC_GREEN  # bright green
        elif color_hint == "red":
            desc_color = LC_RED  # bright red

        d.rounded_rectangle([PAD, y, W - PAD, y + row_h], radius=14,
                            fill=LC_ROW, outline=LC_BORDER, width=2)
        d.text((PAD + 24, y + row_h / 2 - 18), f"{i:02d}", font=num_font, fill=LC_NUM)
        tx = PAD + 110
        maxw = (W - PAD) - tx - 24
        d.text((tx, y + 12), _fit_text(d, it_title, it_font, maxw), font=it_font, fill=WHITE)
        if it_desc:
            d.text((tx, y + 48), _fit_text(d, it_desc, de_font, maxw), font=de_font, fill=desc_color)
        y += row_h + 8

    # Footer band
    fy = H - 132
    d.rectangle([0, fy, W, H], fill=LC_FOOTER)
    d.text((PAD, fy + 28), "Vishleshak Market Brief", font=_font(34, "bold"), fill=WHITE)
    d.text((PAD, fy + 78), brand_note or "AI-powered daily market intelligence  •  Educational only",
           font=_font(21, "regular"), fill=MUTED)

    if filename.lower().endswith(".png"):
        filename = filename[:-4] + ".jpg"
    path = os.path.join(POSTS_DIR, filename)
    img.save(path, "JPEG", quality=94)
    return path


def generate_post_image(title, time_label, body_lines, filename):
    """Create a premium branded card. Returns saved path or None."""
    if not PIL_AVAILABLE:
        print("Pillow not available — cannot generate image")
        return None

    os.makedirs(POSTS_DIR, exist_ok=True)
    img = _gradient_bg()
    d = ImageDraw.Draw(img)
    PAD = 72

    # ── Header: logo chip + brand ──
    d.rounded_rectangle([PAD, 64, PAD + 104, 168], radius=26, fill=ACCENT2)
    lw = d.textlength("V", font=_font(64, "bold"))
    d.text((PAD + 52 - lw / 2, 78), "V", font=_font(64, "bold"), fill=WHITE)
    d.text((PAD + 130, 78), "Vishleshak Market Brief", font=_font(38, "bold"), fill=WHITE)
    d.text((PAD + 132, 130), "AI-powered daily market intelligence", font=_font(22, "regular"), fill=MUTED)

    # ── Date / time pill ──
    pill_font = _font(25, "semibold")
    tw = d.textlength(time_label.upper(), font=pill_font)
    d.rounded_rectangle([PAD, 208, PAD + tw + 52, 258], radius=25, fill=PILL_BG)
    d.text((PAD + 26, 218), time_label.upper(), font=pill_font, fill=ACCENT)

    # ── Title ──
    y = 296
    for line in textwrap.wrap(title, width=22):
        d.text((PAD, y), line, font=_font(68, "bold"), fill=WHITE)
        y += 84
    y += 8
    d.rounded_rectangle([PAD, y, PAD + 116, y + 8], radius=4, fill=ACCENT)  # accent underline
    y += 48

    # ── Body ──
    for raw in body_lines:
        if y > H - 205:
            break
        kind, text, color = _classify(raw)
        if not text:
            y += 18
            continue
        if kind == "header":
            y += 12
            d.rounded_rectangle([PAD, y + 6, PAD + 8, y + 40], radius=4, fill=ACCENT)
            d.text((PAD + 26, y), text.title(), font=_font(33, "semibold"), fill=ACCENT)
            y += 56
        elif kind in ("up", "down"):
            # drawn triangle marker + value, color-coded
            _draw_triangle(d, PAD, y + 12, 24, kind == "up", color)
            for i, wrapped in enumerate(textwrap.wrap(text, width=32) or [""]):
                d.text((PAD + 46, y), wrapped, font=_font(36, "medium"), fill=color)
                y += 50
            y += 10
        else:
            # Numbered news headlines render smaller so the FULL text fits (no truncation).
            is_news = bool(re.match(r"^\d+\.\s", text))
            fsize, lh, ww = (29, 40, 46) if is_news else (34, 48, 36)
            for wrapped in textwrap.wrap(text, width=ww) or [""]:
                d.text((PAD, y), wrapped, font=_font(fsize, "medium"), fill=WHITE)
                y += lh
            y += 8 if is_news else 10

    # ── Footer band ──
    fy = H - 150
    d.rectangle([0, fy, W, H], fill=FOOTER_BG)
    d.rectangle([0, fy, W, fy + 4], fill=ACCENT2)  # accent top edge
    ff = _font(31, "semibold")
    d.text((PAD, fy + 36), "Full brief", font=ff, fill=ACCENT)
    fbw = d.textlength("Full brief", font=ff)
    _draw_arrow(d, PAD + fbw + 22, fy + 53, 26, ACCENT)
    d.text((PAD + fbw + 80, fy + 36), "vishleshak.in/news", font=ff, fill=ACCENT)
    d.text((PAD, fy + 88), "@vishleshak.market.brief   •   Educational only, not investment advice",
           font=_font(20, "regular"), fill=MUTED)

    # ── Save (JPEG for Instagram) ──
    if filename.lower().endswith(".png"):
        filename = filename[:-4] + ".jpg"
    path = os.path.join(POSTS_DIR, filename)
    img.save(path, "JPEG", quality=94)
    return path
