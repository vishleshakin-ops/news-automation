"""
News source module — fetches + curates quality Indian financial headlines from NewsAPI.
Free tier: ~100 req/day, ~24h delay. Uses domain filter + relevance scoring to surface
the most important Indian-market news and drop clickbait / pure-global noise.
"""
import os
import re
import requests
from datetime import datetime, timedelta

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
# Cheap model for editorial headline SELECTION (not rewriting — keeps facts intact).
# Haiku 4.5 = this account's available gen (older 3.x models return 404).
CURATION_MODEL = os.getenv("CURATION_MODEL", "claude-haiku-4-5")

INDIAN_FINANCE_DOMAINS = ",".join([
    "economictimes.indiatimes.com",
    "livemint.com",
    "business-standard.com",
    "thehindubusinessline.com",
    "financialexpress.com",
    "moneycontrol.com",
])

NEWS_QUERY = "Sensex OR Nifty OR RBI OR SEBI OR markets OR earnings OR IPO OR economy OR rupee"

# High-value Indian-market signals (boost)
HIGH_VALUE = [
    "nifty", "sensex", "rbi", "sebi", "fii", "dii", "fpi", "rupee", "repo rate",
    "inflation", "gdp", "monetary policy", "bond yield", "q1 result", "q2 result",
    "q3 result", "q4 result", "earnings", "ipo", "gst", "fiscal", "bse", "nse",
    "stake", "acquisition", "merger", "dividend", "crore", "lakh crore",
    "fund raise", "funding", "order book", "results",
]
# India-relevance terms (smaller boost; absence = global-only penalty)
INDIA_TERMS = ["india", "indian", "rbi", "sebi", "nifty", "sensex", "bse", "nse",
               "rupee", "crore", "mumbai", "delhi", "adani", "tata", "reliance",
               "ambani", "modi", "nirmala"]
# Clickbait / low-value patterns (drop outright)
LOW_VALUE = [
    "stock to buy", "stocks to buy", "buy today", "buzzing stock", "stocks to watch",
    "stocks in news", "stocks in focus", "stocks to track", "quick edit", "live updates",
    "stock market live", "top picks", "multibagger", "muhurat", "f&o ban",
    "share price target", "trade setup", "stocks to add", "hot stocks", "live blog",
    "what to expect", "stock radar", "stock recommendations",
]
# Pure-global names that, without India relevance, are off-topic for our audience
GLOBAL_NOISE = ["spacex", "alphabet", "tesla", "nvidia", "openai", "microsoft",
                "apple inc", "meta platforms", "amazon", "netflix", "wall street",
                "dow jones", "s&p 500", "nasdaq"]


def _score(title, recency_rank):
    """Higher = more relevant. Returns None to drop the headline."""
    t = title.lower()
    if any(p in t for p in LOW_VALUE):
        return None  # drop clickbait
    score = 0.0
    score += sum(3 for k in HIGH_VALUE if k in t)
    has_india = any(k in t for k in INDIA_TERMS)
    if has_india:
        score += 4
    if any(g in t for g in GLOBAL_NOISE) and not has_india:
        score -= 8  # pure global, not relevant
    # mild recency preference (newer first among similar scores)
    score += max(0, 3 - recency_rank * 0.1)
    return score


_STOP = {"the", "and", "for", "from", "with", "that", "this", "may", "are", "was",
         "will", "into", "over", "amid", "year", "years", "than", "after", "before",
         "report", "today", "live", "details", "interim", "order", "against", "flags"}


def _sig_tokens(title):
    """Significant lowercase tokens (len>3, not stopwords/numbers) for topic-overlap dedup."""
    words = re.sub(r"[^a-z0-9 ]", " ", title.lower()).split()
    return {w for w in words if len(w) > 3 and not w.isdigit() and w not in _STOP}


def _fetch_raw(hours_back, page_size=50):
    from_date = (datetime.utcnow() - timedelta(hours=hours_back)).strftime("%Y-%m-%dT%H:%M:%S")
    params = {
        "q": NEWS_QUERY, "domains": INDIAN_FINANCE_DOMAINS, "from": from_date,
        "language": "en", "sortBy": "publishedAt", "pageSize": page_size,
        "apiKey": NEWS_API_KEY,
    }
    resp = requests.get("https://newsapi.org/v2/everything", params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "ok":
        print(f"NewsAPI error: {data.get('message')}")
        return []
    return data.get("articles", [])


def get_top_headlines(limit=10, hours_back=24):
    """Fetch candidates, score for Indian-market relevance, dedup, return the best `limit`."""
    if not NEWS_API_KEY:
        print("Warning: NEWS_API_KEY not set")
        return []

    articles = []
    for window in sorted({hours_back, 48, 72, 120}):
        try:
            articles = _fetch_raw(window)
            if len(articles) >= limit:
                break
        except Exception as e:
            print(f"news fetch error (window={window}): {e}")
    if not articles:
        return []

    scored = []
    seen_titles = set()
    for rank, a in enumerate(articles):
        title = (a.get("title") or "").strip()
        # strip trailing " | Source" / " - Source" noise
        title = re.sub(r"\s*[\|\-–]\s*[^|\-–]{0,30}$", "", title).strip() if title.count("|") else title
        if not title or title in seen_titles:
            continue
        s = _score(title, rank)
        if s is None:
            continue
        seen_titles.add(title)
        scored.append((s, title, _sig_tokens(title), {
            "title": title,
            "source": a.get("source", {}).get("name", ""),
            "url": a.get("url", ""),
            "published_at": a.get("publishedAt", ""),
        }))

    scored.sort(key=lambda x: x[0], reverse=True)

    # Topic-dedup: skip a headline if it shares 3+ significant tokens with one already picked.
    # Build a slightly larger pool so the AI curator has good options to choose from.
    pool_size = max(limit + 4, 14)
    picked, picked_tokens = [], []
    for _, _title, toks, h in scored:
        if any(len(toks & pt) >= 3 for pt in picked_tokens):
            continue
        picked.append(h)
        picked_tokens.append(toks)
        if len(picked) >= pool_size:
            break

    # Editorial AI selection (cheap Haiku): pick the `limit` most important, ranked.
    # Selection-only (returns indices) — never rewrites, so facts stay intact. Falls back to heuristic.
    if ANTHROPIC_API_KEY and len(picked) > limit:
        ranked = _ai_rank(picked, limit)
        if ranked:
            return ranked
    return picked[:limit]


def _ai_rank(candidates, limit):
    """Ask Haiku to pick the `limit` most important headlines (by index). Returns reordered
    list, or None on any failure. Does NOT rewrite headlines — only selects/ranks."""
    try:
        listing = "\n".join(f"{i}. {c['title']}" for i, c in enumerate(candidates))
        prompt = (
            "You are the editor of an Indian stock-market daily brief. From the numbered "
            "headlines below, choose the " + str(limit) + " MOST important for Indian investors "
            "(prioritise market-moving news: RBI/SEBI, indices, big deals, results, IPOs, policy; "
            "avoid minor/promotional items). Reply with ONLY the chosen numbers, comma-separated, "
            "ranked most-important first. Example: 3,1,7,0,5\n\n" + listing
        )
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": CURATION_MODEL, "max_tokens": 60,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=20,
        )
        resp.raise_for_status()
        text = resp.json()["content"][0]["text"]
        idxs = [int(n) for n in re.findall(r"\d+", text)]
        out, seen = [], set()
        for i in idxs:
            if 0 <= i < len(candidates) and i not in seen:
                out.append(candidates[i])
                seen.add(i)
            if len(out) >= limit:
                break
        return out if len(out) >= min(limit, 3) else None
    except Exception as e:
        print(f"AI headline ranking failed (using heuristic): {e}")
        return None


def format_headlines_text(headlines, numbered=True):
    if not headlines:
        return "No major headlines available right now."
    lines = []
    for i, h in enumerate(headlines, 1):
        prefix = f"{i}. " if numbered else "• "
        lines.append(f"{prefix}{h['title']} ({h['source']})")
    return "\n".join(lines)
