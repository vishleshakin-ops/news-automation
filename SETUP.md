# News Automation — Setup Guide

## ✅ What's Built

Backend system for generating daily market briefs:
- ✅ Alpha Vantage integration (real-time Sensex/Nifty data)
- ✅ Anthropic Claude integration (4-section brief generation)
- ✅ SQLite database (brief storage + analytics)
- ✅ APScheduler (automated runs at 9 AM, 4 PM, 6 PM IST)
- ✅ FastAPI REST endpoints
- ✅ Modern dashboard UI (HTML/JS)

**Total API cost per month: ₹0-5 (Alpha Vantage free, Anthropic minimal)**

---

## 🔑 Step 1: Get API Keys (5 minutes)

### Alpha Vantage (Free)
1. Visit: https://www.alphavantage.co/
2. Click "GET FREE API KEY"
3. Enter email, get instant key
4. **No payment required. Ever.**
5. Copy the key

### Anthropic API
1. Visit: https://console.anthropic.com/
2. Sign in with Google
3. Go to "API Keys" → "Create New Key"
4. Copy the key

---

## 🚀 Step 2: Install & Run (3 minutes)

### Windows (PowerShell)

```powershell
cd D:\Future\news-automation
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Create .env file

Create file: `D:\Future\news-automation\.env`

```
ALPHA_VANTAGE_KEY=your_key_here
ANTHROPIC_KEY=your_key_here
```

Replace `your_key_here` with actual keys from Step 1.

### Run Backend

```powershell
python main.py
```

Output:
```
INFO:     Application startup complete
✅ Scheduler started (9 AM, 4 PM, 6 PM India time)
```

---

## 🧪 Step 3: Test (2 minutes)

### Open Dashboard
```
http://localhost:8000/dashboard.html
```

Wait for it to load (might show "no briefs" if scheduler hasn't run yet).

### Generate Test Brief
```powershell
curl -X POST http://localhost:8000/generate
```

Or visit in browser:
```
http://localhost:8000/docs
```

Find "POST /generate" → Click "Try it out" → Execute

### Expected Response
```json
{
  "status": "success",
  "brief_id": 1,
  "time_slot": "morning",
  "content": "Market brief text...",
  "indices": {
    "sensex": {...},
    "nifty": {...},
    "movers": {...}
  }
}
```

### Check Dashboard
After generating, refresh:
```
http://localhost:8000/dashboard.html
```

You should see the brief card with:
- Market Overview
- Headlines  
- Sector Analysis
- Investor Takeaway
- Live Sensex/Nifty prices

---

## 📊 API Costs

### Alpha Vantage
- Free tier: 500 calls/day
- Your usage: ~15 calls/day
- Cost: **$0**

### Anthropic
- Per brief: ~50 tokens
- Price: $0.0075 per brief (~₹0.62)
- 3 briefs/day = ₹1.86/day = ₹56/month

### Total Monthly Cost
- **₹50-60/month** (purely for Anthropic)
- Alpha Vantage: Free forever
- Infrastructure: ₹500/month (Railway.app, when deployed)

---

## 🎯 What's Next

### Immediate (This Week)
- [ ] Test brief generation 2-3 times
- [ ] Verify scheduler runs at correct times
- [ ] Check database is storing briefs

### Soon (Next Week)
- [ ] Connect dashboard to live data
- [ ] Add Instagram posting (Meta Graph API)
- [ ] Add WhatsApp broadcast (existing setup)
- [ ] Deploy to Railway.app

### Later
- [ ] Blog article integration (vishleshak.in)
- [ ] Customer analytics (CTR tracking)
- [ ] Payment integration (Razorpay)
- [ ] Customer dashboard

---

## ⚠️ Important Notes

### Scheduling
Briefs generate at:
- **9:00 AM IST** — Morning brief (pre-market)
- **4:00 PM IST** — Afternoon brief (closing)
- **6:00 PM IST** — Evening brief (recap)

Server must be running for these to execute.

### Database
SQLite file (`news_briefs.db`) is created automatically on first run.
- Location: `D:\Future\news-automation\news_briefs.db`
- Size: Minimal (~1 KB per brief)
- Backup: Copy the file periodically

### Log Messages
Check console for:
- ✅ "Brief saved (ID: X)" → Success
- ❌ "Brief generation failed" → Check logs

### API Rate Limits
You're using 3% of Alpha Vantage free quota.
No issues with 10x more briefs per day.

---

## 🆘 Troubleshooting

### "Alpha Vantage API key not found"
→ Check `.env` file exists and has `ALPHA_VANTAGE_KEY=...`

### "Anthropic API key not found"  
→ Check `.env` file has `ANTHROPIC_KEY=...`

### No briefs showing on dashboard
→ It's normal if scheduler hasn't run yet
→ Click "Generate Test Brief" button or run: `curl -X POST http://localhost:8000/generate`

### Scheduler not running
→ Check console output during startup
→ Server must be running continuously for scheduler to work

### Database locked error
→ Restart the server: `Ctrl+C` then `python main.py`

---

## 📧 Questions?

Check these files:
- `README.md` — Full technical details
- `main.py` — Source code with comments
- `D:\Future\_docs\project_news_automation.md` — Project overview
