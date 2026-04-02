# ExpediRamp

> **Modern Travel Runs on ExpediRamp**

ExpediRamp is an AI-powered travel planning web app. Describe your trip in plain English and the agent searches for real flights, hotels, and ground transportation, then builds a visual itinerary you can iterate on conversationally.

---

## Architecture

```
frontend/   React 19 + Vite + Tailwind CSS + Firebase Web SDK
backend/    Flask + OpenAI (GPT-4o) + Firebase Admin SDK
auth/       Firebase Authentication (Email/Password)
storage/    Cloud Firestore
flights/    `flights` (fli) package — reverse-engineered Google Flights API (no key required)
hotels/     SerpAPI Google Hotels (falls back to placeholder data if key is absent)
```

---

## Prerequisites

| Requirement | Version / Notes |
|---|---|
| Node.js | 18+ |
| Python | 3.11+ |
| Firebase project | auth + Firestore |
| OpenAI API key | GPT-4o |
| SerpAPI key | Optional — enables real hotel results |

No Duffel account or RapidAPI key is needed. Flights are fetched directly from Google Flights via the `flights` (`fli`) Python package — no API key required.

---

## 1. Firebase Setup

### 1a. Create the project

1. Go to [console.firebase.google.com](https://console.firebase.google.com/).
2. Click **Create a project**, give it a name, and finish the wizard. Analytics is optional.

### 1b. Register the web app

1. From the project overview, click the **`</>`** (web) icon.
2. Use `expediramp-web` as the app nickname.
3. Click **Register app**.
4. Copy the config object — you'll need these values for `frontend/.env.local`.

### 1c. Enable Email/Password authentication

1. In the Firebase console, open **Authentication → Sign-in method**.
2. Enable **Email/Password**.
3. Click **Save**.

### 1d. Create Firestore

1. In the Firebase console, open **Firestore Database**.
2. Click **Create database**, use the **default** database.
3. Choose a region close to your users and finish the wizard.

No manual schema is required. The backend creates all collections on demand:

- `conversations`
- `conversations/{conversationId}/messages`
- `itineraries`

### 1e. Generate the Admin SDK service account key

1. In the Firebase console, go to **Project settings → Service accounts**.
2. Click **Generate new private key**.
3. Save the downloaded JSON file **outside** version control.

You will reference this file (or its contents inline) in the backend `.env`.

---

## 2. Get API Keys

### OpenAI

Sign up or log in at [platform.openai.com](https://platform.openai.com/) and create an API key. The agent uses `gpt-4o` by default.

### SerpAPI (optional but recommended)

Used for real hotel search results and photos via the Google Hotels engine. Without it, the app falls back to placeholder hotel data.

Sign up at [serpapi.com](https://serpapi.com/) and copy your API key. The free tier is sufficient for development.

### Flights — no key needed

Flights are fetched via the [`flights` (`fli`) Python package](https://pypi.org/project/flights/), which uses the reverse-engineered Google Flights internal API. No account or API key is required.

**Currency note:** Google Flights returns prices in the currency matching the server's IP geolocation. The backend auto-detects this and converts all prices to USD using live exchange rates. If prices appear in the wrong currency, set `FLIGHT_CURRENCY=CAD` (or your local currency code) in `.env` as an explicit override.

---

## 3. Configure Environment Files

There are two env files — one for the backend (repo root) and one for the frontend.

### Backend — `.env` (repo root)

Copy the template:

```bash
# macOS / Linux
cp .env.example .env

# Windows PowerShell
Copy-Item .env.example .env
```

Fill in the values:

```env
# ── OpenAI ────────────────────────────────────────────────────
OPENAI_API_KEY=sk-your-openai-key

# ── SerpAPI (hotel search — optional but recommended) ─────────
SERPAPI_KEY=your-serpapi-key

# ── Flight currency override (optional) ───────────────────────
# The backend auto-detects via IP geolocation and converts to USD.
# Set this only if auto-detection returns the wrong currency.
# Example: FLIGHT_CURRENCY=CAD if your server runs in Canada.
FLIGHT_CURRENCY=

# ── Firebase Admin SDK ────────────────────────────────────────
# Option A (recommended): path to the downloaded service-account JSON
FIREBASE_SERVICE_ACCOUNT_KEY_PATH=/absolute/path/to/firebase-service-account.json

# Option B: inline the three fields from the JSON instead
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_CLIENT_EMAIL=firebase-adminsdk-xxxxx@your-project-id.iam.gserviceaccount.com
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"

# ── Flask ─────────────────────────────────────────────────────
FLASK_SECRET_KEY=change-me-to-a-long-random-string
FLASK_ENV=development
FLASK_PORT=5001
FRONTEND_URL=http://localhost:5173
```

Use **either** `FIREBASE_SERVICE_ACCOUNT_KEY_PATH` **or** the inline trio — not both.

### Frontend — `frontend/.env.local`

Copy the template:

```bash
# macOS / Linux
cp frontend/.env.example frontend/.env.local

# Windows PowerShell
Copy-Item frontend/.env.example frontend/.env.local
```

Fill in the values from your Firebase web app registration (step 1b):

```env
VITE_API_URL=http://localhost:5001/api

VITE_FIREBASE_API_KEY=your-web-api-key
VITE_FIREBASE_AUTH_DOMAIN=your-project-id.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-project-id
VITE_FIREBASE_APP_ID=your-web-app-id
VITE_FIREBASE_MESSAGING_SENDER_ID=your-sender-id

# Optional: require a password before accessing the app (useful for private demos).
# Leave blank or omit to disable the gate entirely.
VITE_DEMO_PASSWORD=
```

---

## 4. Install & Run

### Backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows PowerShell
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Start the server
python app.py
```

Backend runs at **http://localhost:5001** by default.

To run with gunicorn (closer to production):

```bash
gunicorn -k eventlet -w 1 app:app
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at **http://localhost:5173**.

---

## 5. How It Works

1. The user describes a trip in the chat input (e.g. *"I want to fly from Toronto to Tokyo for two weeks in September, budget around $4,000"*).
2. The Flask backend passes the conversation to a GPT-4o agent equipped with search tools.
3. The agent calls those tools — hitting Google Flights via `fli` for flights, SerpAPI for hotels, and built-in transit data for ground transportation — and streams results back via Server-Sent Events.
4. When the agent is done, the frontend renders a vertical timeline itinerary with photos, clickable booking links, layover details, and a running cost total.
5. The user can iterate in plain language (*"Skip the layover in Dubai"*, *"I want a nicer hotel"*, *"Add Osaka"*) and the agent updates only the relevant parts of the itinerary.
6. Signed-in users have their conversation and itinerary saved to Firestore automatically. Anonymous usage is supported but not persisted.

---

## 6. How Auth Works

1. The frontend signs users in with Firebase Authentication (`createUserWithEmailAndPassword` / `signInWithEmailAndPassword`).
2. Firebase returns a short-lived ID token.
3. The frontend attaches it to every API request: `Authorization: Bearer <token>`.
4. Flask verifies the token using the Firebase Admin SDK (`firebase_admin.auth.verify_id_token`).
5. If verification succeeds, the backend reads or writes that user's Firestore documents.

---

## 7. Project Structure

```
expediramp/
├── .env.example                   # Backend env template
├── backend/
│   ├── app.py                     # Flask entry point
│   ├── config.py                  # Reads .env into Config class
│   ├── requirements.txt
│   ├── agents/
│   │   ├── travel_agent.py        # OpenAI agent loop (streaming + non-streaming)
│   │   └── tools.py               # Tool definitions and system prompt
│   ├── routes/
│   │   ├── chat.py                # POST /api/chat, POST /api/chat/stream, conversation routes
│   │   └── auth.py                # GET /api/auth/me, POST /api/auth/logout
│   └── services/
│       ├── flight_service.py      # Google Flights via fli package (no API key needed)
│       ├── hotel_service.py       # SerpAPI Google Hotels (falls back to placeholders)
│       ├── currency_conversion.py # Auto-detects local currency, converts prices to USD
│       └── firebase_client.py     # Firestore helpers + token verification
└── frontend/
    ├── .env.example               # Frontend env template
    ├── index.html
    ├── package.json
    ├── vite.config.js
    ├── tailwind.config.js
    └── src/
        ├── main.jsx
        ├── App.jsx                # Main chat + itinerary state
        ├── api/                   # sendMessageStream and other API helpers
        ├── components/
        │   ├── Auth/              # AuthModal (sign in / sign up)
        │   ├── DemoGate.jsx       # Optional password gate
        │   ├── ChatInput.jsx
        │   ├── ItineraryTimeline.jsx
        │   └── ...
        └── firebase.js            # Firebase SDK initialisation
```

---

## 8. Troubleshooting

### Flight prices show in the wrong currency

The `fli` package returns prices in the currency Google Flights assigns based on the server's IP. Set `FLIGHT_CURRENCY=CAD` (or your local currency code) in `.env` to force the correct source currency before conversion to USD. Restart the Flask server after changing it.

### No hotel results / placeholder hotels showing

`SERPAPI_KEY` is not set or is invalid. Without it the app falls back to placeholder hotel data. Set a valid SerpAPI key in `.env` and restart Flask.

### `Invalid token` from the backend

The `VITE_FIREBASE_PROJECT_ID` in the frontend and the Firebase credentials in the backend must point at the **same** Firebase project. Restart the Flask server after any `.env` change.

### Trips are not being saved

- Confirm that Firestore has been created in the Firebase console (step 1d).
- Verify the backend is using valid Admin SDK credentials (Option A or B, not a partial mix of both).
- Restart Flask after editing `.env`.

### `Module not found: firebase` (frontend)

```bash
cd frontend && npm install
```

### Python import errors for `firebase_admin` or `flights`

```bash
cd backend
# Activate your virtual environment first, then:
pip install -r requirements.txt
```