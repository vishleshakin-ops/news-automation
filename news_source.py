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


def get_top_headlines(limit=10, hours_back=24):
    """
    Fetch top Indian financial headlines from the last `hours_back` hours.
    Returns a list of dicts: {title, source, url, published_at}.
    """
    if not NEWS_API_KEY:
        print("Warning: NEWS_API_KEY not set")
        return []

    from_date = (datetime.utcnow() - timedelta(hours=hours_back)).strftime("%Y-%m-%dT%H:%M:%S")

    params = {
        "q": NEWS_QUERY,
        "domains": INDIAN_FINANCE_DOMAINS,
        "from": from_date,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": min(limit * 2, 30),  # fetch extra to dedupe
        "apiKey": NEWS_API_KEY,
    }

    try:
        resp = requests.get("https://newsapi.org/v2/everything", params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "ok":
            print(f"NewsAPI error: {data.get('message')}")
            return []

        seen_titles = set()
        headlines = []
        for article in data.get("articles", []):
            title = (article.get("title") or "").strip()
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)
            headlines.append({
                "title": title,
                "source": article.get("source", {}).get("name", ""),
                "url": article.get("url", ""),
                "published_at": article.get("publishedAt", ""),
            })
            if len(headlines) >= limit:
                break
        return headlines

    except Exception as e:
        print(f"Error fetching news: {e}")
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
