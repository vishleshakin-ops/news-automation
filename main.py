import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import requests
import yfinance as yf
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import pytz
import json
from database import init_db, save_brief, get_brief, get_all_briefs
import daily_posts
import social

# Public base URL of this service (for Instagram image hosting). Set in Railway.
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://news-automation-production-df05.up.railway.app")

load_dotenv()

# Initialize FastAPI
app = FastAPI(title="News Automation API")

# Initialize database
init_db()

# API Keys
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

def call_anthropic(prompt: str) -> str:
    """Call Anthropic API directly via HTTP — no SDK, no proxies issue."""
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    payload = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}]
    }
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers=headers,
        json=payload,
        timeout=30
    )
    response.raise_for_status()
    return response.json()["content"][0]["text"]

# Timezone
INDIA_TZ = pytz.timezone("Asia/Kolkata")

# ============================================================================
# ALPHA VANTAGE INTEGRATION
# ============================================================================

def get_sensex_data():
    """Fetch Sensex (BSE index) data from Alpha Vantage."""
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "GLOBAL_QUOTE",
        "symbol": "SENSEX",
        "apikey": ALPHA_VANTAGE_KEY
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if "Global Quote" in data:
            quote = data["Global Quote"]
            return {
                "symbol": "SENSEX",
                "price": quote.get("05. price", "N/A"),
                "change": quote.get("09. change", "0"),
                "change_percent": quote.get("10. change percent", "0%"),
                "timestamp": quote.get("07. latest trading day", "")
            }
    except Exception as e:
        print(f"Error fetching Sensex: {e}")

    return None

def get_nifty_data():
    """Fetch Nifty 50 (NSE index) data from Alpha Vantage."""
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "GLOBAL_QUOTE",
        "symbol": "^NSEI",
        "apikey": ALPHA_VANTAGE_KEY
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if "Global Quote" in data:
            quote = data["Global Quote"]
            return {
                "symbol": "NIFTY50",
                "price": quote.get("05. price", "N/A"),
                "change": quote.get("09. change", "0"),
                "change_percent": quote.get("10. change percent", "0%"),
                "timestamp": quote.get("07. latest trading day", "")
            }
    except Exception as e:
        print(f"Error fetching Nifty: {e}")

    return None

def get_top_movers():
    """Get real NSE top gainers and losers via Yahoo Finance."""
    NIFTY_50 = [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
        "HINDUNILVR.NS", "BAJFINANCE.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
        "LT.NS", "AXISBANK.NS", "WIPRO.NS", "MARUTI.NS", "ULTRACEMCO.NS",
        "TITAN.NS", "SUNPHARMA.NS", "POWERGRID.NS", "NTPC.NS", "ASIANPAINT.NS",
        "TECHM.NS", "HCLTECH.NS", "BAJAJFINSV.NS", "TATASTEEL.NS", "ONGC.NS",
        "COALINDIA.NS", "INDUSINDBK.NS", "ADANIENT.NS", "JSWSTEEL.NS", "NESTLEIND.NS"
    ]
    try:
        tickers = " ".join(NIFTY_50)
        data = yf.download(tickers, period="2d", interval="1d", group_by="ticker", progress=False)
        results = []
        for ticker in NIFTY_50:
            try:
                closes = data[ticker]["Close"].dropna()
                if len(closes) >= 2:
                    prev = float(closes.iloc[-2])
                    curr = float(closes.iloc[-1])
                    change = ((curr - prev) / prev) * 100
                    symbol = ticker.replace(".NS", "")
                    results.append({
                        "symbol": symbol,
                        "price": f"₹{curr:,.2f}",
                        "change_percent": f"{change:+.2f}%"
                    })
            except:
                continue

        results.sort(key=lambda x: float(x["change_percent"].replace("%", "")), reverse=True)
        return {
            "top_gainers": results[:5],
            "top_losers": list(reversed(results[-5:]))
        }
    except Exception as e:
        print(f"Error fetching top movers: {e}")
        return {"top_gainers": [], "top_losers": []}

# ============================================================================
# BRIEF GENERATION
# ============================================================================

def generate_market_brief():
    """Generate 4-section market brief using Anthropic Claude."""

    # Fetch market data
    sensex = get_sensex_data()
    nifty = get_nifty_data()
    movers = get_top_movers()

    indices_data = {
        "sensex": sensex,
        "nifty": nifty,
        "movers": movers
    }

    # Current time in India
    current_time = datetime.now(INDIA_TZ)
    hour = current_time.hour

    # Determine time slot and context
    if 8 <= hour < 12:
        time_slot = "morning"
        context = "Pre-market trading outlook for the Indian stock market"
    elif 15 <= hour < 17:
        time_slot = "closing"
        context = "Closing market summary and performance analysis"
    else:
        time_slot = "evening"
        context = "Evening market recap and key takeaways"

    # Create prompt for Anthropic
    prompt = f"""You are a financial news analyst for the Indian stock market. Generate a professional 4-section market brief.

Current Market Data:
- Sensex: {sensex['price'] if sensex else 'N/A'} ({sensex['change_percent'] if sensex else 'N/A'})
- Nifty 50: {nifty['price'] if nifty else 'N/A'} ({nifty['change_percent'] if nifty else 'N/A'})
- Top Gainers: {', '.join([f"{g['symbol']} {g['change_percent']}" for g in movers['top_gainers'][:3]])}
- Top Losers: {', '.join([f"{l['symbol']} {l['change_percent']}" for l in movers['top_losers'][:3]])}

Context: {context}
Time Slot: {time_slot}

Generate a brief with these 4 sections (each 2-3 sentences):

1. Market Overview - Current indices, opening/closing trend, overall sentiment
2. Key Headlines - Top 3 moving stocks and reasons
3. Sector Analysis - Which sectors are leading/lagging
4. Investor Takeaway - Strategic insight and what to watch

Format as plain text, no markdown. Be concise and professional."""

    try:
        brief_text = call_anthropic(prompt)
        return {
            "status": "success",
            "time_slot": time_slot,
            "content": brief_text,
            "indices_data": indices_data
        }

    except Exception as e:
        print(f"Error generating brief: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": str(e)
        }

# ============================================================================
# SCHEDULED TASKS
# ============================================================================

def scheduled_brief_generation():
    """Generate and save brief at scheduled times."""
    brief = generate_market_brief()

    if brief["status"] == "success":
        current_date = datetime.now(INDIA_TZ).strftime("%Y-%m-%d")
        brief_id = save_brief(
            date=current_date,
            section="daily",
            time_slot=brief["time_slot"],
            title=f"Market Brief - {brief['time_slot'].capitalize()}",
            content=brief["content"],
            indices_data=brief["indices_data"]
        )
        print(f"[OK] Brief saved (ID: {brief_id}) - {brief['time_slot']}")
    else:
        print(f"❌ Brief generation failed: {brief['message']}")

def start_scheduler():
    """Start APScheduler for daily brief generation."""
    scheduler = BackgroundScheduler(timezone=INDIA_TZ)

    # 9 AM - Morning brief
    scheduler.add_job(
        scheduled_brief_generation,
        'cron',
        hour=9,
        minute=0,
        id='morning_brief'
    )

    # 4 PM - Afternoon brief
    scheduler.add_job(
        scheduled_brief_generation,
        'cron',
        hour=16,
        minute=0,
        id='afternoon_brief'
    )

    # 6 PM - Evening summary
    scheduler.add_job(
        scheduled_brief_generation,
        'cron',
        hour=18,
        minute=0,
        id='evening_brief'
    )

    # ----- SOCIAL POSTS (Facebook required, Instagram best-effort) -----
    # 5 daily posts at IST times
    social_schedule = [
        ("premarket", 9, 0),    # 9:00 AM  Pre-Market Watchlist
        ("closing", 16, 0),     # 4:00 PM  Closing Summary
        ("movers", 16, 15),     # 4:15 PM  Top 5 Gainers & Losers
        ("summary", 16, 30),    # 4:30 PM  Daily Summary Sheet
        ("watchlist", 18, 0),   # 6:00 PM  Tomorrow's Watchlist
    ]
    for slot, hh, mm in social_schedule:
        scheduler.add_job(
            run_social_post, 'cron', hour=hh, minute=mm,
            args=[slot], id=f"social_{slot}"
        )

    scheduler.start()
    print("[OK] Scheduler started: 3 briefs + 5 social posts (IST)")


def run_social_post(slot):
    """Generate + publish one social post (called by scheduler)."""
    try:
        result = daily_posts.run_post(slot, public_base_url=PUBLIC_BASE_URL)
        fb = result.get("facebook", {})
        ig = result.get("instagram", {})
        print(f"[SOCIAL {slot}] FB ok={fb.get('ok')} {fb.get('id', fb.get('error'))} | "
              f"IG ok={ig.get('ok')} {ig.get('id', ig.get('error'))}")
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"ok": False, "error": str(e)}

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Start scheduler on app startup."""
    start_scheduler()

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "News Automation API",
        "status": "running",
        "endpoints": [
            "GET /dashboard - Fetch all briefs",
            "GET /brief/{date} - Fetch brief for specific date",
            "POST /generate - Generate brief manually",
            "GET /health - Health check"
        ]
    }

@app.post("/generate")
async def generate_brief_manually():
    """Generate brief on-demand (for testing)."""
    brief = generate_market_brief()

    if brief["status"] == "success":
        current_date = datetime.now(INDIA_TZ).strftime("%Y-%m-%d")
        brief_id = save_brief(
            date=current_date,
            section="daily",
            time_slot=brief["time_slot"],
            title=f"Market Brief - {brief['time_slot'].capitalize()}",
            content=brief["content"],
            indices_data=brief["indices_data"]
        )
        return {
            "status": "success",
            "brief_id": brief_id,
            "time_slot": brief["time_slot"],
            "content": brief["content"],
            "indices": brief["indices_data"]
        }
    else:
        raise HTTPException(status_code=500, detail=brief["message"])

@app.get("/brief/{date}")
async def get_brief_by_date(date: str):
    """Fetch brief for a specific date (format: YYYY-MM-DD)."""
    brief = get_brief(date)

    if brief:
        return {
            "date": date,
            "briefs": [
                {
                    "id": b[0],
                    "section": b[2],
                    "time_slot": b[3],
                    "title": b[4],
                    "content": b[5],
                    "indices": json.loads(b[6]) if b[6] else {}
                }
                for b in brief
            ]
        }
    else:
        raise HTTPException(status_code=404, detail="No brief found for this date")

@app.get("/dashboard")
async def get_dashboard():
    """Fetch all available briefs for dashboard."""
    dates = get_all_briefs(limit=30)

    return {
        "available_dates": dates,
        "count": len(dates),
        "latest": dates[0] if dates else None
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(INDIA_TZ).isoformat(),
        "alpha_vantage": "configured" if ALPHA_VANTAGE_KEY else "missing",
        "anthropic": "configured" if ANTHROPIC_API_KEY else "missing",
        "news_api": "configured" if os.getenv("NEWS_API_KEY") else "missing",
        "facebook": "configured" if social.is_configured() else "missing",
        "instagram": "configured" if social.META_IG_USER_ID else "not linked (optional)"
    }


@app.get("/social/preview/{slot}")
async def preview_social(slot: str):
    """Preview the generated text for a post WITHOUT publishing. slot: premarket|closing|movers|summary|watchlist"""
    builder = daily_posts.POST_BUILDERS.get(slot)
    if not builder:
        raise HTTPException(status_code=404, detail=f"Unknown slot. Use: {list(daily_posts.POST_BUILDERS)}")
    try:
        post = builder()
        return {"slot": slot, "title": post["title"], "facebook_text": post["fb_text"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/social/post/{slot}")
async def trigger_social(slot: str):
    """Manually generate + PUBLISH a post now (Facebook + Instagram if configured)."""
    if slot not in daily_posts.POST_BUILDERS:
        raise HTTPException(status_code=404, detail=f"Unknown slot. Use: {list(daily_posts.POST_BUILDERS)}")
    return run_social_post(slot)


@app.get("/social/derive-debug")
async def derive_debug():
    """Verbose token derivation — shows where it fails + the permanent page token to store."""
    return social.derive_debug()


@app.get("/debug/data")
async def debug_data():
    """Diagnose market-data fetch on Railway: curl_cffi status + live macro result."""
    out = {"curl_cffi_available": daily_posts._cffi is not None}
    try:
        macro = daily_posts.get_macro()
        out["macro_keys"] = list(macro.keys())
        out["nifty"] = macro.get("^NSEI")
        out["ok"] = bool(macro)
    except Exception as e:
        import traceback
        out["error"] = str(e)
        out["trace"] = traceback.format_exc()[-800:]
    return out


@app.get("/social/token-scopes")
async def token_scopes():
    """Show which permissions the configured token actually has (via debug_token)."""
    import requests as _rq
    app_id = social.APP_ID
    secret = social.APP_SECRET
    user_token = social.META_USER_TOKEN
    if not (app_id and secret and user_token):
        return {"error": "Need META_APP_ID + APP_SECRET + META_USER_TOKEN set"}
    try:
        app_token = f"{app_id}|{secret}"
        r = _rq.get("https://graph.facebook.com/v21.0/debug_token",
                    params={"input_token": user_token, "access_token": app_token},
                    timeout=20).json()
        scopes = r.get("data", {}).get("scopes", [])
        needed = ["pages_manage_posts", "pages_read_engagement", "pages_show_list",
                  "instagram_basic", "instagram_content_publish"]
        return {
            "granted_scopes": scopes,
            "missing": [s for s in needed if s not in scopes],
            "has_all_required": all(s in scopes for s in needed),
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/social/diagnose")
async def diagnose_social():
    """Diagnose Meta token setup. Shows whether a page token resolves + the IG account id."""
    token = social.get_page_token()
    ig_id = social.fetch_ig_user_id() if token else None
    return {
        "page_id": social.META_PAGE_ID,
        "page_token_resolved": bool(token),
        "instagram_business_account_id": ig_id,
        "instagram_env_set": bool(social.META_IG_USER_ID),
        "hint": "If page_token_resolved is true, Facebook posting will work. "
                "Copy instagram_business_account_id into Railway as META_IG_USER_ID to enable Instagram.",
    }

# ============================================================================
# STATIC FILES
# ============================================================================

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# ============================================================================
# RUN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
