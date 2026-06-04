import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import requests
from anthropic import Anthropic
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import pytz
import json
from database import init_db, save_brief, get_brief, get_all_briefs

load_dotenv()

# Initialize FastAPI
app = FastAPI(title="News Automation API")

# Initialize database
init_db()

# API Keys
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Clients - Initialize lazily to avoid startup issues
def get_anthropic_client():
    """Get or create Anthropic client."""
    try:
        return Anthropic(api_key=ANTHROPIC_API_KEY)
    except Exception as e:
        print(f"Warning: Could not initialize Anthropic client: {e}")
        return None

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
    """Get top gainers and losers (using simple API or cached data)."""
    # Note: Alpha Vantage doesn't have built-in top movers endpoint
    # For now, return placeholder. In production, use a dedicated endpoint or cache
    return {
        "top_gainers": [
            {"symbol": "RELIANCE", "change_percent": "+2.5%"},
            {"symbol": "TCS", "change_percent": "+1.8%"},
            {"symbol": "INFY", "change_percent": "+1.2%"},
            {"symbol": "HDFC", "change_percent": "+0.9%"},
            {"symbol": "ICICIBANK", "change_percent": "+0.7%"}
        ],
        "top_losers": [
            {"symbol": "MARUTI", "change_percent": "-1.5%"},
            {"symbol": "BAJAJFINSV", "change_percent": "-1.2%"},
            {"symbol": "AXISBANK", "change_percent": "-0.8%"},
            {"symbol": "KOTAKBANK", "change_percent": "-0.6%"},
            {"symbol": "LT", "change_percent": "-0.5%"}
        ]
    }

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
        client = get_anthropic_client()
        if not client:
            return {
                "status": "error",
                "message": "Anthropic client not available"
            }

        message = client.messages.create(
            model="claude-opus-4-1-20250805",
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        brief_text = message.content[0].text

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

    scheduler.start()
    print("[OK] Scheduler started (9 AM, 4 PM, 6 PM India time)")

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
        "anthropic": "configured" if ANTHROPIC_API_KEY else "missing"
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
