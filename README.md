# ExpediRamp

**Modern Travel Runs on ExpediRamp**

An AI-powered travel planning agent. Describe your trip in plain English and get a complete itinerary with flights, hotels, transportation, and activities — all presented in a beautiful vertical timeline with costs, photos, and booking links.

![ExpediRamp](https://images.unsplash.com/photo-1488646953014-85cb44e25828?w=800)

## Architecture

```
┌─────────────────────┐     ┌──────────────────────────┐     ┌───────────────┐
│   React Frontend    │────▶│    Flask Backend API      │────▶│   Supabase    │
│   (Vite + Tailwind) │◀────│   (OpenAI Agent Loop)     │◀────│   (DB + Auth) │
└─────────────────────┘     └──────────────────────────┘     └───────────────┘
                             │
                             ├── Flight Search Service (mock / Amadeus)
                             ├── Hotel Search Service  (mock / Booking.com)
                             ├── Car Rental Service    (mock / Kayak)
                             └── Transit Service       (mock / Rome2Rio)
```

### Tech Stack

| Layer       | Technology           | Purpose                          |
|-------------|---------------------|----------------------------------|
| Frontend    | React 19 + Vite     | SPA with SSE streaming           |
| Styling     | Tailwind CSS        | Ramp-inspired design system      |
| Backend     | Flask               | REST API + SSE streaming         |
| AI Agent    | OpenAI GPT-4o       | Function calling for travel tools|
| Database    | Supabase (Postgres) | Conversations, messages, trips   |
| Auth        | Supabase Auth       | Email/password authentication    |

## Quick Start

### 1. Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **OpenAI API key** — [Get one here](https://platform.openai.com/api-keys)
- **Supabase project** — [Create one here](https://supabase.com/dashboard)

### 2. Supabase Setup

1. Create a new Supabase project
2. Go to **SQL Editor** and run the schema from `database/schema.sql`
3. Copy your project URL, anon key, and service role key

### 3. Environment Variables

```bash
cp .env.example .env
```

Edit `.env` with your keys:

```env
OPENAI_API_KEY=sk-...
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...
FLASK_SECRET_KEY=some-random-secret-string
```

### 4. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

The API server starts on `http://localhost:5000`.

### 5. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The dev server starts on `http://localhost:5173` with automatic proxy to the backend.

### 6. Open the App

Navigate to **http://localhost:5173** and start planning trips!

## Features

### Core
- **Natural language trip planning** — Describe what you want; the agent figures out the rest
- **Multi-tool AI agent** — Searches flights, hotels, car rentals, and transit in parallel
- **Iterative refinement** — "I don't want to layover in DXB", "Find a nicer hotel", "Add Osaka"
- **Abuse filtering** — Non-travel requests are politely declined

### Itinerary Timeline
- **Vertical timeline layout** — Chronological view of every trip component
- **Flight cards** — Airline logos, segment details, layover info, nonstop badges
- **Hotel cards** — Photos, star ratings, amenity tags, cancellation policies
- **Car rental cards** — Vehicle photos, feature lists, daily/total pricing
- **Transit cards** — Local pass options with descriptions and links
- **Cost breakdown** — Running total with per-item costs and trip summary

### UX
- **Streaming responses** — Real-time token-by-token display via SSE
- **Tool activity indicators** — See what the agent is searching in real-time
- **Ramp-inspired design** — Clean, minimal, professional aesthetic
- **Responsive** — Works on desktop and mobile
- **Auth** — Optional Supabase login to save conversations

## Project Structure

```
expediramp/
├── .env.example                    # Environment template
├── database/
│   └── schema.sql                  # Supabase schema (run in SQL Editor)
├── backend/
│   ├── app.py                      # Flask entry point
│   ├── config.py                   # Environment config
│   ├── requirements.txt
│   ├── agents/
│   │   ├── tools.py                # OpenAI tool definitions + system prompt
│   │   └── travel_agent.py         # Agent loop (streaming + non-streaming)
│   ├── routes/
│   │   ├── chat.py                 # Chat API (POST /api/chat/stream)
│   │   └── auth.py                 # Auth API
│   └── services/
│       ├── supabase_client.py      # DB + auth helpers
│       ├── flight_service.py       # Flight search (mock)
│       ├── hotel_service.py        # Hotel search (mock)
│       └── car_service.py          # Car rental + transit (mock)
└── frontend/
    ├── package.json
    ├── vite.config.js
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── index.html
    └── src/
        ├── main.jsx
        ├── App.jsx                 # Main app shell
        ├── index.css               # Tailwind + Ramp design tokens
        ├── api/
        │   └── client.js           # API client with SSE streaming
        ├── context/
        │   └── AuthContext.jsx      # Auth state management
        └── components/
            ├── Auth/
            │   └── AuthModal.jsx
            ├── Chat/
            │   ├── ChatInput.jsx
            │   ├── ChatMessage.jsx
            │   ├── ToolStatus.jsx
            │   └── WelcomeScreen.jsx
            ├── Layout/
            │   └── Header.jsx
            └── Timeline/
                └── ItineraryTimeline.jsx
```

## Connecting Real APIs

The backend services use mock data by default. To connect real APIs:

### Flights — Amadeus or Duffel
Replace `services/flight_service.py` with calls to:
- [Amadeus Flight Offers Search](https://developers.amadeus.com/self-service/category/flights)
- [Duffel Offer Requests](https://duffel.com/docs/api/v1/offer-requests)

### Hotels — Booking.com or Google Hotels
Replace `services/hotel_service.py` with:
- [Booking.com Affiliate API](https://developers.booking.com/)
- [Google Hotels via SerpAPI](https://serpapi.com/google-hotels-api)

### Car Rentals — Kayak or Cartrawler
Replace `services/car_service.py` with:
- [Cartrawler API](https://www.cartrawler.com/)

### Transit — Rome2Rio
- [Rome2Rio API](https://www.rome2rio.com/documentation/)

## API Endpoints

| Method | Endpoint | Description |
|--------|---------|-------------|
| `POST` | `/api/chat` | Send message (non-streaming) |
| `POST` | `/api/chat/stream` | Send message (SSE streaming) |
| `POST` | `/api/auth/login` | Login with email/password |
| `POST` | `/api/auth/signup` | Create account |
| `GET`  | `/api/auth/me` | Get current user |
| `GET`  | `/api/conversations` | List conversations |
| `POST` | `/api/conversations` | Create conversation |
| `GET`  | `/api/conversations/:id/messages` | Get messages |
| `GET`  | `/api/health` | Health check |

## License

MIT
