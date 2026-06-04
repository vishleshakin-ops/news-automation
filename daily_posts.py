"""
daily_posts.py — generates and publishes the 5 daily social posts.

Priority: FACEBOOK (text posts, always reliable). Instagram is best-effort (needs image + linking).

All market data from Yahoo Finance (unlimited, no API key). News from NewsAPI.
Posts are templated from REAL data so they always send even if AI is unavailable.
An optional one-line AI "market pulse" (Haiku) is added where it helps, wrapped in try/except.

The 5 posts:
  1) 9:00 AM  Pre-Market Watchlist  — top news + index prior close + global cues
  2) 4:00 PM  Closing Summary       — closing NSE/BSE + day's finance news
  3) 4:15 PM  Top 5 Gainers/Losers  — real NSE movers
  4) 4:30 PM  Summary Sheet         — Nifty/Sensex/Gold/Silver/USD-INR vs prior day
  5) 6:00 PM  Tomorrow's Watchlist  — Nifty levels + stocks + sector to watch + global cues
"""
import os
from datetime import datetime
import pytz
import yfinance as yf

import news_source
import social
import image_gen

INDIA_TZ = pytz.timezone("Asia/Kolkata")
SITE_LINK = "https://vishleshak.in/news"

# Nifty 50 universe grouped by sector (for movers + sector analysis)
SECTORS = {
    "IT": ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM"],
    "Banking": ["HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "KOTAKBANK", "INDUSINDBK"],
    "Energy": ["RELIANCE", "ONGC", "NTPC", "POWERGRID", "COALINDIA"],
    "Auto": ["MARUTI", "BAJAJ-AUTO", "TATAMOTORS"],
    "FMCG": ["HINDUNILVR", "NESTLEIND", "ITC"],
    "Metals": ["TATASTEEL", "JSWSTEEL"],
    "Pharma": ["SUNPHARMA", "CIPLA"],
    "Finance": ["BAJFINANCE", "BAJAJFINSV"],
    "Telecom": ["BHARTIARTL"],
    "Consumption": ["TITAN", "ASIANPAINT"],
}
ALL_STOCKS = [s for stocks in SECTORS.values() for s in stocks]

GLOBAL = {"Dow": "^DJI", "S&P 500": "^GSPC", "Nasdaq": "^IXIC", "Crude": "CL=F"}
MACRO = {"Nifty": "^NSEI", "Sensex": "^BSESN", "Gold": "GC=F", "Silver": "SI=F", "USD/INR": "INR=X"}


# ----------------------------------------------------------------------------
# DATA HELPERS (Yahoo Finance — unlimited)
# ----------------------------------------------------------------------------
def _pct_change(symbols):
    """Return {symbol: {'price':float,'pct':float}} from last 2 daily closes."""
    out = {}
    try:
        data = yf.download(" ".join(symbols), period="3d", interval="1d",
                           group_by="ticker", progress=False)
        for s in symbols:
            try:
                closes = data[s]["Close"].dropna()
                if len(closes) >= 2:
                    prev, cur = float(closes.iloc[-2]), float(closes.iloc[-1])
                    out[s] = {"price": cur, "pct": ((cur - prev) / prev) * 100}
            except Exception:
                continue
    except Exception as e:
        print(f"_pct_change error: {e}")
    return out


def get_movers():
    """Real NSE top 5 gainers and losers."""
    data = _pct_change([f"{s}.NS" for s in ALL_STOCKS])
    rows = [{"symbol": k.replace(".NS", ""), **v} for k, v in data.items()]
    rows.sort(key=lambda x: x["pct"], reverse=True)
    return {"gainers": rows[:5], "losers": list(reversed(rows[-5:]))}


def get_sector_performance():
    """Average % change per sector → leader and laggard."""
    data = _pct_change([f"{s}.NS" for s in ALL_STOCKS])
    sector_avg = {}
    for sector, stocks in SECTORS.items():
        vals = [data[f"{s}.NS"]["pct"] for s in stocks if f"{s}.NS" in data]
        if vals:
            sector_avg[sector] = sum(vals) / len(vals)
    if not sector_avg:
        return None
    leader = max(sector_avg, key=sector_avg.get)
    laggard = min(sector_avg, key=sector_avg.get)
    return {"leader": (leader, sector_avg[leader]), "laggard": (laggard, sector_avg[laggard])}


def get_macro():
    return _pct_change(list(MACRO.values()))


def get_global():
    return _pct_change(list(GLOBAL.values()))


def _today_str():
    return datetime.now(INDIA_TZ).strftime("%-d %B %Y") if os.name != "nt" \
        else datetime.now(INDIA_TZ).strftime("%#d %B %Y")


def _fmt(v, prefix=""):
    return f"{prefix}{v:,.2f}"


def _arrow(pct):
    return "📈" if pct >= 0 else "📉"


# ----------------------------------------------------------------------------
# THE 5 POST GENERATORS  → each returns dict {title, time_label, fb_text, ig_lines}
# ----------------------------------------------------------------------------
def post_premarket():
    macro = get_macro()
    glob = get_global()
    headlines = news_source.get_top_headlines(limit=10, hours_back=18)

    nifty = macro.get("^NSEI", {})
    sensex = macro.get("^BSESN", {})
    inr = macro.get("INR=X", {})

    lines = [f"📊 VISHLESHAK MARKET BRIEF — {_today_str()}", "", "🌅 PRE-MARKET WATCHLIST", ""]
    if nifty:
        lines.append(f"Nifty prev close: {_fmt(nifty['price'])} ({nifty['pct']:+.2f}%)")
    if sensex:
        lines.append(f"Sensex prev close: {_fmt(sensex['price'])} ({sensex['pct']:+.2f}%)")
    if inr:
        lines.append(f"USD/INR: ₹{inr['price']:.2f}")
    crude = glob.get("CL=F", {})
    if crude:
        lines.append(f"Crude Oil: ${crude['price']:.2f} ({crude['pct']:+.2f}%)")
    lines.append("")
    lines.append("📰 TOP HEADLINES:")
    for i, h in enumerate(headlines[:10], 1):
        lines.append(f"{i}. {h['title']}")
    lines += ["", f"Full brief → {SITE_LINK}", "",
              "#Nifty #Sensex #StockMarket #PreMarket #Vishleshak"]
    fb_text = "\n".join(lines)
    ig_lines = ([f"Nifty: {_fmt(nifty['price'])} ({nifty['pct']:+.2f}%)"] if nifty else []) + \
               ([f"Sensex: {_fmt(sensex['price'])} ({sensex['pct']:+.2f}%)"] if sensex else []) + \
               [""] + [f"{i}. {h['title'][:60]}" for i, h in enumerate(headlines[:5], 1)]
    return {"title": "Pre-Market Watchlist", "time_label": f"9:00 AM • {_today_str()}",
            "fb_text": fb_text, "ig_lines": ig_lines}


def post_closing():
    macro = get_macro()
    headlines = news_source.get_top_headlines(limit=10, hours_back=8)
    nifty = macro.get("^NSEI", {})
    sensex = macro.get("^BSESN", {})

    lines = [f"📊 VISHLESHAK MARKET BRIEF — {_today_str()}", "", "🌄 CLOSING MARKET SUMMARY", ""]
    if nifty:
        lines.append(f"{_arrow(nifty['pct'])} Nifty 50: {_fmt(nifty['price'])} ({nifty['pct']:+.2f}%)")
    if sensex:
        lines.append(f"{_arrow(sensex['pct'])} Sensex: {_fmt(sensex['price'])} ({sensex['pct']:+.2f}%)")
    lines += ["", "📰 TODAY'S TOP FINANCE NEWS:"]
    for i, h in enumerate(headlines[:10], 1):
        lines.append(f"{i}. {h['title']}")
    lines += ["", f"Full brief → {SITE_LINK}", "",
              "#Nifty #Sensex #ClosingBell #StockMarket #Vishleshak"]
    fb_text = "\n".join(lines)
    ig_lines = ([f"{_arrow(nifty['pct'])} Nifty: {_fmt(nifty['price'])} ({nifty['pct']:+.2f}%)"] if nifty else []) + \
               ([f"{_arrow(sensex['pct'])} Sensex: {_fmt(sensex['price'])} ({sensex['pct']:+.2f}%)"] if sensex else []) + \
               [""] + [f"{i}. {h['title'][:60]}" for i, h in enumerate(headlines[:5], 1)]
    return {"title": "Closing Market Summary", "time_label": f"4:00 PM • {_today_str()}",
            "fb_text": fb_text, "ig_lines": ig_lines}


def post_movers():
    m = get_movers()
    lines = [f"📊 VISHLESHAK MARKET BRIEF — {_today_str()}", "", "🏆 TOP 5 GAINERS & LOSERS", "",
             "📈 GAINERS:"]
    for g in m["gainers"]:
        lines.append(f"  {g['symbol']}  +{g['pct']:.2f}%  (₹{g['price']:,.2f})")
    lines += ["", "📉 LOSERS:"]
    for l in m["losers"]:
        lines.append(f"  {l['symbol']}  {l['pct']:.2f}%  (₹{l['price']:,.2f})")
    lines += ["", f"Full brief → {SITE_LINK}", "",
              "#TopGainers #TopLosers #Nifty #StockMarket #Vishleshak"]
    fb_text = "\n".join(lines)
    ig_lines = ["📈 GAINERS"] + [f"+ {g['symbol']} +{g['pct']:.2f}%" for g in m["gainers"]] + \
               ["", "📉 LOSERS"] + [f"- {l['symbol']} {l['pct']:.2f}%" for l in m["losers"]]
    return {"title": "Top 5 Gainers & Losers", "time_label": f"4:15 PM • {_today_str()}",
            "fb_text": fb_text, "ig_lines": ig_lines}


def post_summary_sheet():
    macro = get_macro()
    label_map = [("Nifty 50", "^NSEI", ""), ("Sensex", "^BSESN", ""),
                 ("Gold", "GC=F", "$"), ("Silver", "SI=F", "$"), ("USD/INR", "INR=X", "₹")]
    lines = [f"📊 VISHLESHAK MARKET BRIEF — {_today_str()}", "", "📋 DAILY SUMMARY SHEET",
             "(vs prior day)", ""]
    ig_lines = []
    for name, sym, pfx in label_map:
        d = macro.get(sym)
        if d:
            row = f"{_arrow(d['pct'])} {name}: {pfx}{d['price']:,.2f}  ({d['pct']:+.2f}%)"
            lines.append(row)
            ig_lines.append(row)
    lines += ["", f"Full brief → {SITE_LINK}", "",
              "#MarketSummary #Gold #Silver #Nifty #Sensex #Vishleshak"]
    return {"title": "Daily Summary Sheet", "time_label": f"4:30 PM • {_today_str()}",
            "fb_text": "\n".join(lines), "ig_lines": ig_lines}


def post_tomorrow_watchlist():
    macro = get_macro()
    glob = get_global()
    movers = get_movers()
    sector = get_sector_performance()
    nifty = macro.get("^NSEI", {})

    lines = [f"📊 VISHLESHAK MARKET BRIEF — {_today_str()}", "", "📌 TOMORROW'S WATCHLIST", ""]
    if nifty:
        price = nifty["price"]
        support = round(price * 0.993, 0)
        resistance = round(price * 1.007, 0)
        lines += [f"📊 NIFTY KEY LEVELS", f"Close: {_fmt(price)}",
                  f"Support: {support:,.0f} | Resistance: {resistance:,.0f}", ""]
    if sector:
        lname, lpct = sector["leader"]
        gname, gpct = sector["laggard"]
        lines += ["🏭 SECTOR TO WATCH",
                  f"🟢 {lname} led today ({lpct:+.2f}%)",
                  f"🔴 {gname} lagged ({gpct:+.2f}%)", ""]
    if movers["gainers"]:
        lines.append("👀 STOCKS TO WATCH")
        for g in movers["gainers"][:3]:
            lines.append(f"📈 {g['symbol']} (+{g['pct']:.2f}% today)")
        lines.append("")
    cues = []
    for name, sym in [("Dow", "^DJI"), ("Crude", "CL=F")]:
        d = glob.get(sym)
        if d:
            cues.append(f"{name} {d['pct']:+.2f}%")
    inr = macro.get("INR=X", {})
    if inr:
        cues.append(f"USD/INR ₹{inr['price']:.2f}")
    if cues:
        lines += ["🌍 GLOBAL CUES", " | ".join(cues), ""]
    lines += [f"Full brief → {SITE_LINK}", "",
              "#NiftyTomorrow #StocksToWatch #StockMarket #Vishleshak"]
    fb_text = "\n".join(lines)
    ig_lines = lines[4:-3]
    return {"title": "Tomorrow's Watchlist", "time_label": f"6:00 PM • {_today_str()}",
            "fb_text": fb_text, "ig_lines": ig_lines}


POST_BUILDERS = {
    "premarket": post_premarket,
    "closing": post_closing,
    "movers": post_movers,
    "summary": post_summary_sheet,
    "watchlist": post_tomorrow_watchlist,
}


# ----------------------------------------------------------------------------
# PUBLISH
# ----------------------------------------------------------------------------
def run_post(slot, public_base_url=None):
    """
    Build and publish a single post by slot key.
    Facebook is required; Instagram is attempted only if configured + image hostable.
    Returns a result dict.
    """
    builder = POST_BUILDERS.get(slot)
    if not builder:
        return {"ok": False, "error": f"unknown slot {slot}"}

    try:
        post = builder()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"ok": False, "error": f"build failed: {e}"}

    result = {"slot": slot, "title": post["title"]}

    # --- Facebook (required) ---
    result["facebook"] = social.post_to_facebook(post["fb_text"], link=SITE_LINK)

    # --- Instagram (best-effort) ---
    if social.META_IG_USER_ID and public_base_url:
        try:
            fname = f"{slot}_{datetime.now(INDIA_TZ).strftime('%Y%m%d')}.png"
            img_path = image_gen.generate_post_image(
                post["title"], post["time_label"], post["ig_lines"], fname)
            if img_path:
                image_url = f"{public_base_url.rstrip('/')}/static/posts/{fname}"
                caption = post["fb_text"]
                result["instagram"] = social.post_to_instagram(image_url, caption)
        except Exception as e:
            result["instagram"] = {"ok": False, "error": str(e)}
    else:
        result["instagram"] = {"ok": False, "error": "IG not configured (optional)"}

    return result
