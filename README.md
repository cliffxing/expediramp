# ExpediRamp — Modern Travel Runs on ExpediRamp

AI-powered travel agent that plans complete trip itineraries from plain-text descriptions. Searches real flights, hotels, and transportation, then presents everything in a visual timeline with photos, prices, and booking links.

## Architecture

```
frontend/  (React + Vite + Tailwind)
  └── Chat UI → streams SSE from backend
backend/   (Flask + OpenAI function-calling)
  └── Travel agent loop → calls Duffel API → builds itinerary
database/  (Supabase — Postgres + Auth)
  └── Conversations, messages, saved itineraries
```

---

## 1. API Keys — What You Need

### Required

| Service | Free tier | Sign-up |
|---------|-----------|---------|
| **OpenAI** | Pay-as-you-go | https://platform.openai.com/api-keys |

### Flight & Hotel Data (primary: Duffel)

| Service | Free tier | Sign-up |
|---------|-----------|---------|
| **Duffel** | Test environment (free) | https://app.duffel.com/ |
| **SerpAPI** | 100 searches/month (fallback) | https://serpapi.com |

> **Recommendation**: Start with a **Duffel test token** (free, sandbox airline inventory). When you're ready for real bookings, generate a live token in the Duffel dashboard.

### Optional

| Service | Purpose |
|---------|---------|
| **Supabase** | Auth + conversation history. Without it the app works fine but nothing is saved between sessions. |

---

## 2. Duffel Setup (Primary — Free Sandbox)

Duffel provides real airline and hotel inventory via a unified API. The test environment returns real flight and hotel data using sandbox credentials — no credit card is charged.

1. Go to https://app.duffel.com/ and create a free account.
2. Navigate to **Settings → Access tokens**.
3. Click **Create token** → choose **Test** environment.
4. Copy the token (starts with `duffel_test_`).
5. Add to your `.env`:
   ```
   DUFFEL_ACCESS_TOKEN=duffel_test_your-token-here
   ```

### What Duffel provides

| Feature | Duffel API |
|---------|------------|
| **Flights** | Offer Requests API — real airline inventory (200+ airlines), segments, layovers, cabin classes, live prices |
| **Hotels** | Stays API — global hotel inventory, availability, photos, amenities, nightly rates |
| **Booking** | Orders API — real bookings (live token required) |

### Going Live

To charge real cards and issue real tickets:
1. Apply for a live token in the Duffel dashboard (requires business verification).
2. Replace `DUFFEL_ACCESS_TOKEN=duffel_test_...` with your live token `duffel_live_...`.
3. Update the system prompt in `agents/tools.py` if desired.

---

## 3. SerpAPI Setup (Fallback)

Used only if Duffel is unavailable or fails.

1. Go to https://serpapi.com and sign up.
2. Copy your API key from the dashboard.
3. Add to `.env`: `SERPAPI_KEY=your-key`

---

## 4. Quick Start

```bash
# Clone and enter the project
cd expediramp-out

# Backend
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example ../.env
# Edit .env with your keys
python app.py

# Frontend (separate terminal)
cd frontend
npm install
cp .env .env.local              # edit VITE_API_URL if needed
npm run dev
```

Open http://localhost:5173 and start planning a trip!

---

## 5. Environment Variables Reference

```env
# Required
OPENAI_API_KEY=sk-...

# Duffel (primary travel data API)
DUFFEL_ACCESS_TOKEN=duffel_test_...    # or duffel_live_...

# SerpAPI (optional fallback)
SERPAPI_KEY=

# Supabase (optional — auth & persistence)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...

# Flask
FLASK_SECRET_KEY=change-me
FLASK_ENV=development
FLASK_PORT=5001
FRONTEND_URL=http://localhost:5173
```

---

## 6. API Priority Chain

```
User asks for flights or hotels
        │
        ▼
  DUFFEL_ACCESS_TOKEN set?
     YES → call Duffel API  ──fails──► SERPAPI_KEY set?
                                          YES → call SerpAPI
                                          NO  → error message
```

---

## 7. Project Structure

```
expediramp-out/
├── backend/
│   ├── app.py                    Flask entry point
│   ├── config.py                 Environment config (Duffel token, etc.)
│   ├── requirements.txt
│   ├── agents/
│   │   ├── travel_agent.py       OpenAI function-calling agent loop
│   │   └── tools.py              Tool definitions + system prompt
│   ├── services/
│   │   ├── duffel_client.py      ★ Duffel REST client (auth + helpers)
│   │   ├── flight_service.py     ★ Duffel Flights → SerpAPI fallback
│   │   ├── hotel_service.py      ★ Duffel Stays → SerpAPI fallback
│   │   ├── car_service.py        Car rental & transit
│   │   └── supabase_client.py    Auth + DB helpers
│   └── routes/
│       ├── chat.py               /api/chat and /api/chat/stream
│       └── auth.py               /api/auth/...
├── frontend/
│   └── src/
│       ├── App.jsx
│       ├── components/
│       │   ├── Chat/             Chat input, messages, tool status
│       │   ├── Timeline/         Itinerary timeline component
│       │   ├── Auth/             Login/signup modal
│       │   └── Layout/           Header
│       └── api/client.js         API wrapper
└── database/
    └── schema.sql                Supabase schema
```

★ = updated/new in Duffel integration

---

## 8. Example Conversation

```
User:  I want to fly from Toronto to Tokyo in mid-April for 10 days,
       2 adults, mid-range budget.

Agent: [calls search_flights(origin=YYZ, destination=NRT, ...)]
       [calls search_hotels(city=Tokyo, ...)]
       [calls build_itinerary(...)]

       Here's your Tokyo trip! I found a great Air Canada flight
       with one stop in Vancouver for $1,240/person. For accommodation,
       the Shinjuku Granbell Hotel checks all your boxes at $165/night...
```

---

## 9. Troubleshooting

| Problem | Fix |
|---------|-----|
| `DUFFEL_ACCESS_TOKEN is not set` | Add token to `.env` from https://app.duffel.com/ |
| Duffel returns 401 | Token may be expired or wrong environment (test vs live) |
| No hotel results for a city | City may not be in the coordinate mapping — open a PR to add it |
| Duffel 422 on offer request | Check IATA codes are valid; Duffel requires real airport codes |
| SerpAPI fallback used unexpectedly | Check Duffel logs — usually a network timeout |
