# ExpediRamp — Modern Travel Runs on ExpediRamp

AI-powered travel agent that plans complete trip itineraries from plain-text descriptions. Searches real flights, hotels, and transportation, then presents everything in a visual timeline with photos, prices, and booking links.

## Architecture

```
frontend/  (React + Vite + Tailwind)
  └── Chat UI → streams SSE from backend
backend/   (Flask + OpenAI function-calling)
  └── Travel agent loop → calls Amadeus / SerpAPI → builds itinerary
database/  (Supabase — Postgres + Auth)
  └── Conversations, messages, saved itineraries
```

---

## 1. API Keys — What You Need

### Required

| Service | Free tier | Sign-up |
|---------|-----------|---------|
| **OpenAI** | Pay-as-you-go | https://platform.openai.com/api-keys |

### Flight & Hotel Data (pick at least one)

| Service | Free tier | Sign-up |
|---------|-----------|---------|
| **Amadeus Self-Service** | 500 calls/month (test env) | https://developers.amadeus.com |
| **SerpAPI** | 100 searches/month | https://serpapi.com |

> **Recommendation**: Start with **Amadeus test environment** (free, no credit card). It returns sandbox data that looks realistic. When ready for production data, apply for Amadeus production access or add a SerpAPI key.

### Optional

| Service | Purpose |
|---------|---------|
| **Supabase** | Auth + conversation history persistence. Without it the app works fine but nothing is saved between sessions. |

---

## 2. Amadeus Setup (Recommended — Free)

1. Go to https://developers.amadeus.com and create a free account.
2. In the dashboard, click **My Self-Service Workspace → Create New App**.
3. Name it anything (e.g., "ExpediRamp").
4. Copy the **API Key** and **API Secret**.
5. Add them to your `.env`:
   ```
   AMADEUS_CLIENT_ID=<your API Key>
   AMADEUS_CLIENT_SECRET=<your API Secret>
   AMADEUS_ENV=test
   ```
6. The `test` environment uses Amadeus sandbox data — real airline/hotel names but synthetic prices. Switch to `production` once you have Amadeus production approval for live data.

### What Amadeus provides
- **Flight Offers Search v2** — real airline routes, segments, layovers, cabin classes, prices
- **Hotel Search v3** — hotels by city, room availability, nightly rates

---

## 3. SerpAPI Setup (Alternative / Fallback)

If you prefer Google Flights and Google Hotels results, or want a fallback:

1. Go to https://serpapi.com and sign up (100 free searches/month).
2. Copy your API key from the dashboard.
3. Add to `.env`:
   ```
   SERPAPI_KEY=<your key>
   ```

The backend tries **Amadeus first**, then falls back to **SerpAPI** if Amadeus fails or isn't configured.

---

## 4. Supabase Setup (Optional — for Auth & Persistence)

1. Go to https://supabase.com and create a free project.
2. In **Project Settings → API**, copy:
   - Project URL → `SUPABASE_URL`
   - `anon` public key → `SUPABASE_ANON_KEY`
   - `service_role` secret key → `SUPABASE_SERVICE_ROLE_KEY`
3. Run the schema in `database/schema.sql` via the Supabase SQL Editor.
4. Add to `.env`:
   ```
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_ANON_KEY=your-anon-key
   SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
   ```

Without Supabase, the app runs fully — you just can't sign in or save conversation history.

---

## 5. Running the App

### Prerequisites
- Python 3.11+
- Node.js 18+
- npm or yarn

### Backend

```bash
cd backend

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env from template
cp ../.env.example .env
# → Edit .env and fill in your API keys

# Run the server
python app.py
# Server starts on http://localhost:5001
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Run the dev server
npm run dev
# Opens on http://localhost:5173
# API calls are proxied to localhost:5001 automatically
```

### Open in browser
Navigate to **http://localhost:5173** and start describing your trip.

---

## 6. Configuration Reference

All config lives in a single `.env` file in the `backend/` directory:

```env
# ─── Required ───────────────────────────────────────
OPENAI_API_KEY=sk-...

# ─── Flight & Hotel APIs (need at least one) ───────
AMADEUS_CLIENT_ID=...
AMADEUS_CLIENT_SECRET=...
AMADEUS_ENV=test              # "test" or "production"

SERPAPI_KEY=...                # optional fallback

# ─── Supabase (optional) ───────────────────────────
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...

# ─── Flask ──────────────────────────────────────────
FLASK_SECRET_KEY=change-me
FLASK_ENV=development
FLASK_PORT=5001
FRONTEND_URL=http://localhost:5173
```

If you change `FLASK_PORT`, also update `VITE_BACKEND_PORT` in `frontend/.env` so the Vite proxy points to the right place.

---

## 7. Port Configuration

The frontend dev server (Vite) runs on **5173** and proxies `/api/*` requests to the Flask backend. The backend defaults to port **5001**.

| Setting | File | Default |
|---------|------|---------|
| Flask port | `backend/.env` → `FLASK_PORT` | 5001 |
| Vite proxy target | `frontend/.env` → `VITE_BACKEND_PORT` | 5001 |
| Vite dev port | `frontend/vite.config.js` | 5173 |

If the frontend can't reach the backend, make sure both port values match.

---

## 8. How It Works

1. You type a trip description (e.g., "Plan a 10-day trip to Japan").
2. The backend sends your message to **GPT-4o** with travel-specific tools.
3. GPT-4o decides what info it needs and calls tools:
   - `search_flights` → hits Amadeus/SerpAPI for real flight offers
   - `search_hotels` → hits Amadeus/SerpAPI for real hotel availability
   - `search_car_rentals` → generates booking links to Kayak/Google
   - `search_transit` → returns curated transit pass data for the destination
4. Once it has enough data, it calls `build_itinerary` to assemble everything.
5. The frontend renders the itinerary as a **vertical timeline** with:
   - Color-coded dots for each type (blue=flights, amber=hotels, etc.)
   - Photo cards for hotels and car rentals
   - Flight route visuals with layover indicators
   - Every card is clickable → links to the booking site
   - Running cost tracker + total cost summary

---

## 9. Car Rental Note

There are no widely available free car rental APIs. The app generates **booking redirect links** to Kayak, Google Travel, and Rentalcars.com with estimated price ranges by vehicle class. Clicking a car rental card takes you directly to the aggregator's search results for your dates and city.

---

## 10. Troubleshooting

| Problem | Fix |
|---------|-----|
| "No flight API configured" | Add `AMADEUS_CLIENT_ID` + `AMADEUS_CLIENT_SECRET` or `SERPAPI_KEY` to `.env` |
| Frontend shows "Connection error" | Make sure Flask is running and `FLASK_PORT` matches `VITE_BACKEND_PORT` |
| Amadeus returns empty results | In test mode, not all city pairs return data. Try major routes like JFK→LHR or LAX→NRT |
| SerpAPI returns 401 | Check your `SERPAPI_KEY` is valid and has remaining credits |
| Supabase errors on save | Run `database/schema.sql` in the Supabase SQL Editor |
