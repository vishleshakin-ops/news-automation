"""
News source module — fetches clean Indian financial headlines from NewsAPI.
Free tier: 100 requests/day. Uses domains filter for quality Indian financial news.
"""
import os
import requests
from datetime import datetime, timedelta

NEWS_API_KEY = os.getenv("NEWS_API_KEY")

# Trusted Indian financial news domains (clean, relevant, no sports noise)
INDIAN_FINANCE_DOMAINS = ",".join([
    "economictimes.indiatimes.com",
    "livemint.com",
    "business-standard.com",
    "thehindubusinessline.com",
    "financialexpress.com",
    "moneycontrol.com",
])

NEWS_QUERY = "Sensex OR Nifty OR markets OR stocks OR RBI OR economy OR IPO OR earnings"


def _fetch(limit, hours_back):
    """Single NewsAPI call. Returns list of headline dicts (may be empty)."""
    from_date = (datetime.utcnow() - timedelta(hours=hours_back)).strftime("%Y-%m-%dT%H:%M:%S")
    params = {
        "q": NEWS_QUERY,
        "domains": INDIAN_FINANCE_DOMAINS,
        "from": from_date,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": min(limit * 3, 40),
        "apiKey": NEWS_API_KEY,
    }
    resp = requests.get("https://newsapi.org/v2/everything", params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "ok":
        print(f"NewsAPI error: {data.get('message')}")
        return []
    seen, out = set(), []
    for a in data.get("articles", []):
        title = (a.get("title") or "").strip()
        if not title or title in seen:
            continue
        seen.add(title)
        out.append({
            "title": title,
            "source": a.get("source", {}).get("name", ""),
            "url": a.get("url", ""),
            "published_at": a.get("publishedAt", ""),
        })
        if len(out) >= limit:
            break
    return out


def get_top_headlines(limit=10, hours_back=24):
    """
    Fetch top Indian financial headlines. NewsAPI free tier has a ~24h delay,
    so we widen the window progressively until we have enough headlines.
    """
    if not NEWS_API_KEY:
        print("Warning: NEWS_API_KEY not set")
        return []
    # Try the requested window, then widen to guarantee content (free-tier delay safe)
    for window in sorted({hours_back, 48, 72, 120}):
        try:
            headlines = _fetch(limit, window)
            if len(headlines) >= min(limit, 5):
                return headlines
        except Exception as e:
            print(f"Error fetching news (window={window}): {e}")
    # Last attempt — return whatever the widest window gave
    try:
        return _fetch(limit, 168)
    except Exception:
        return []


def format_headlines_text(headlines, numbered=True):
    """Format a list of headlines into clean text for a post."""
    if not headlines:
        return "No major headlines available right now."
    lines = []
    for i, h in enumerate(headlines, 1):
        prefix = f"{i}. " if numbered else "• "
        lines.append(f"{prefix}{h['title']} ({h['source']})")
    return "\n".join(lines)
