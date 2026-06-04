# News Automation — Daily Market Briefs

Production-ready FastAPI backend for generating and distributing AI-powered daily market briefs to Instagram & WhatsApp.

---

## 🚀 Quick Start

### 1. Setup Environment

```bash
cd D:\Future\news-automation
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure API Keys

Copy `.env.example` → `.env` and add your keys:

```bash
ALPHA_VANTAGE_KEY=your_key_here
ANTHROPIC_KEY=your_key_here
```

**Where to get keys:**
- Alpha Vantage: https://www.alphavantage.co/ (free tier, no payment)
- Anthropic: https://console.anthropic.com/ (API key from account settings)

### 3. Run Backend

```bash
python main.py
```

Server starts at `http://localhost:8000`

---

## 📊 Data Sources

### Alpha Vantage (Free Tier)
- ✅ Real-time Sensex (BSE index)
- ✅ Real-time Nifty 50 (NSE index)
- ✅ Stock quotes
- ✅ 500 API calls/day limit
- ✅ Zero payment required

### Anthropic Claude
- ✅ 4-section brief generation
- ✅ Professional market analysis
- ✅ Pay-per-token (minimal cost)

---

## 🔄 Scheduled Brief Generation

Brief generation runs automatically at:
- **9 AM** — Morning pre-market outlook
- **4 PM** — Afternoon closing summary
- **6 PM** — Evening recap

All times in Indian Standard Time (IST/Asia/Kolkata)

---

## 📡 API Endpoints

### Generate Brief (Manual)
```bash
POST /generate

Response:
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

### Get Briefs by Date
```bash
GET /brief/2026-06-04

Response:
{
  "date": "2026-06-04",
  "briefs": [...]
}
```

### Dashboard (All Briefs)
```bash
GET /dashboard

Response:
{
  "available_dates": ["2026-06-04", "2026-06-03", ...],
  "count": 30,
  "latest": "2026-06-04"
}
```

### Health Check
```bash
GET /health

Response:
{
  "status": "healthy",
  "timestamp": "2026-06-04T14:30:00",
  "alpha_vantage": "configured",
  "anthropic": "configured"
}
```

---

## 💾 Database

SQLite database (`news_briefs.db`) stores:
- **briefs table** — Daily market briefs (date, section, content, indices data)
- **analytics table** — CTR tracking (platform, clicks, impressions)

---

## 🔧 Project Structure

```
news-automation/
├── main.py                 # FastAPI app + scheduler
├── database.py            # SQLite setup
├── requirements.txt       # Dependencies
├── .env                   # API keys (create from .env.example)
├── .env.example          # Template
├── README.md             # This file
├── news_briefs.db        # SQLite database (created on first run)
└── static/
    └── dashboard.html    # Frontend UI
```

---

## 🎯 Next Steps

1. ✅ Alpha Vantage integration (DONE)
2. ✅ Anthropic brief generation (DONE)
3. ✅ Database setup (DONE)
4. ✅ Scheduled tasks (DONE)
5. ⏳ Frontend dashboard connection
6. ⏳ Instagram automation (Meta Graph API)
7. ⏳ WhatsApp broadcast setup
8. ⏳ Blog article hosting (vishleshak.in)
9. ⏳ Analytics tracking
10. ⏳ Production deployment (Railway.app)

---

## 📈 Cost Breakdown

### Daily Cost (@ Full Scale)
- **Alpha Vantage:** $0 (free tier)
- **Anthropic (3 briefs/day):** ~₹5-10/month (minimal)
- **Meta Graph API:** $0 (free)
- **Infrastructure:** ~₹500/month (Railway.app)

### Monthly Cost
- **Total:** ~₹500-600/month

### Revenue (Premium Tier)
- **Pricing:** ₹299/month per subscriber
- **Break-even:** 2-3 paying customers
- **Margin:** 95%+

---

## ⚠️ Important Notes

### API Rate Limits
- **Alpha Vantage:** 5 calls/minute, 500/day
- Your usage: ~15 calls/day = 3% of limit
- ✅ Plenty of headroom for scaling

### Costs
- No hidden charges
- All APIs have free/open tiers
- Cost scales only with customer growth

### Testing
Test brief generation manually:
```bash
curl -X POST http://localhost:8000/generate
```

---

## 🐛 Troubleshooting

### "Alpha Vantage API key not found"
→ Create `.env` file and add `ALPHA_VANTAGE_KEY`

### "Anthropic API key not found"
→ Create `.env` file and add `ANTHROPIC_KEY`

### "Database locked"
→ Another process is using the DB. Restart the server.

### Scheduler not running
→ Check console logs. Scheduler starts on app startup.

---

## 📧 Support

For issues or questions, check:
- API docs: `http://localhost:8000/docs` (Swagger UI)
- Logs: Console output when running `python main.py`
- Project memory: `D:\Future\_docs\project_news_automation.md`
