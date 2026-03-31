# ExpediRamp — Modern Travel Runs on ExpediRamp

AI-powered travel agent that plans complete trip itineraries from plain-text descriptions. Searches real flights, hotels, and transportation, then presents everything in a visual timeline with photos, prices, and booking links.

## Architecture

```
frontend/  (React + Vite + Tailwind)
  └── Chat UI → streams SSE from backend
backend/   (Flask + OpenAI function-calling)
  └── Travel agent loop → calls Booking.com API → builds itinerary
database/  (Supabase — Postgres + Auth)
  └── Conversations, messages, saved itineraries
```

---

## 1. API Keys — What You Need

### Required

| Service | Free tier | Sign-up |
|---------|-----------|---------|
| **OpenAI** | Pay-as-you-go | https://platform.openai.com/api-keys |

### Flight Data (primary: Booking.com via RapidAPI)

| Service | Free tier | Sign-up |
|---------|-----------|---------|
| **RapidAPI (Booking.com)** | Free plan available | https://rapidapi.com/DataCrawler/api/booking-com15 |

> **Recommendation**: Sign up at RapidAPI, subscribe to the **Booking COM** API (by DataCrawler), and copy your `X-RapidAPI-Key`. The free plan works for development.

### Hotel Data

| Service | Free tier | Sign-up |
|---------|-----------|---------|
| **SerpAPI** | 100 searches/month | https://serpapi.com |

### Optional

| Service | Purpose |
|---------|---------|
| **Supabase** | Auth + conversation history. Without it the app works fine but nothing is saved between sessions. |

---

## 2. RapidAPI Setup (Primary — Booking.com Flights)

The Booking.com API on RapidAPI provides real-time flight search with rich data including airline logos, per-segment details, layover info, and booking links.

1. Go to https://rapidapi.com and create a free account.
2. Subscribe to **Booking COM** (booking-com15) by DataCrawler.
3. Copy your **X-RapidAPI-Key** from the dashboard.
4. Add to your `.env`:
   ```
   RAPIDAPI_KEY=your-rapidapi-key-here
   ```

### What Booking.com provides

| Feature | Details |
|---------|---------|
| **Flights** | searchFlights endpoint — real-time prices, segments, layovers, cabin classes, airline logos |
| **Booking** | Booking tokens that redirect to Booking.com checkout |

### Fallback: fast-flights

If the Booking.com API is unavailable (no key set, rate limited, or errors), the system automatically falls back to **fast-flights**, a Google Flights scraper that requires no API key. The data quality is slightly lower but it ensures the app always works.

---

## 3. SerpAPI Setup (Hotels)

Used for hotel search.

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

# RapidAPI (primary flight search — Booking.com)
RAPIDAPI_KEY=your-rapidapi-key

# SerpAPI (hotel search)
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
User asks for flights
        │
        ▼
  RAPIDAPI_KEY set?
     YES → call Booking.com searchFlights ──fails──► fast-flights (Google Flights scraper)
      NO → fast-flights directly                        │
                                                    ──fails──► empty results (never fake data)
```

```
User asks for hotels
        │
        ▼
  SERPAPI_KEY set?
     YES → call SerpAPI Google Hotels
      NO → mock hotel data
```

---

## 7. Project Structure

```
expediramp-out/
├── backend/
│   ├── app.py                    Flask entry point
│   ├── config.py                 Environment config (RapidAPI key, etc.)
│   ├── requirements.txt
│   ├── agents/
│   │   ├── travel_agent.py       OpenAI function-calling agent loop
│   │   └── tools.py              Tool definitions + system prompt
│   ├── services/
│   │   ├── flight_service.py     ★ Booking.com via RapidAPI → fast-flights fallback
│   │   ├── hotel_service.py      SerpAPI Google Hotels → mock fallback
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

★ = updated in Booking.com RapidAPI integration

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
| `RAPIDAPI_KEY is not set` | Add your RapidAPI key to `.env` from https://rapidapi.com |
| Booking.com returns 403 | Your RapidAPI plan may be exhausted or the key is invalid |
| Booking.com returns 0 results | The route may not be in their inventory — fast-flights fallback will be used automatically |
| No hotel results for a city | City may not be in the SerpAPI search results |
| `fast-flights` also returns 0 | Google may be blocking scraping — try again later |
| SerpAPI fallback used unexpectedly | Check Booking.com logs — usually a rate limit or network timeout |