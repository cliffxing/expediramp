# ExpediRamp

ExpediRamp is a React + Flask travel planner that streams AI trip planning results, saves signed-in users' trip history, and now uses Firebase for authentication and persistence.

## What changed

- Supabase auth was replaced with Firebase Authentication.
- Supabase conversation storage was replaced with Cloud Firestore.
- The signup flow now uses Firebase's `createUserWithEmailAndPassword`, so an email that already exists is rejected cleanly instead of creating a broken duplicate-signup state.
- The backend now verifies Firebase ID tokens with the Firebase Admin SDK before returning user-specific data.

## Architecture

```text
frontend/  React + Vite + Tailwind + Firebase Web SDK
backend/   Flask + OpenAI + Firebase Admin SDK
storage/   Cloud Firestore
auth/      Firebase Authentication (Email/Password)
```

## Prerequisites

- Node.js 18+
- Python 3.11+
- A Firebase project
- An OpenAI API key
- Optional: RapidAPI Booking.com key and SerpAPI key

## Exact Firebase setup

These steps follow the current Firebase docs for web setup, email/password auth, Admin SDK setup, Firestore creation, and ID-token verification:

- Web app setup: [Add Firebase to your JavaScript project](https://firebase.google.com/docs/web/setup)
- Email/password auth: [Authenticate with Firebase using Password-Based Accounts](https://firebase.google.com/docs/auth/web/password-auth)
- Admin SDK credentials: [Add the Firebase Admin SDK to your server](https://firebase.google.com/docs/admin/setup)
- Backend token verification: [Verify ID Tokens](https://firebase.google.com/docs/auth/admin/verify-id-tokens)
- Firestore database creation: [Manage databases](https://firebase.google.com/docs/firestore/manage-databases)

### 1. Create the Firebase project

1. Open the [Firebase console](https://console.firebase.google.com/).
2. Click `Create a project`.
3. Give it a name.
4. Analytics is optional for this app. You can leave it off if you just want auth + Firestore.
5. Wait for the project to finish provisioning.

Firebase's web setup guide says you first create a Firebase project, then register your web app, and Firebase gives you the config object used by the frontend.

### 2. Register the web app

1. In the Firebase project overview, click the web icon `</>`.
2. App nickname: use `expediramp-web`.
3. Click `Register app`.
4. Copy the Firebase config values shown on screen.

You will use those values in `frontend/.env.local`.

### 3. Enable Email/Password auth

1. In Firebase console, open `Authentication`.
2. Open the `Sign-in method` tab.
3. Enable `Email/Password`.
4. Click `Save`.

The Firebase auth docs explicitly call out this exact flow before using `createUserWithEmailAndPassword` and `signInWithEmailAndPassword`.

### 4. Create Firestore

1. In Firebase console, open `Firestore Database`.
2. Click `Create database`.
3. Use the default database.
4. Pick a region close to your users.
5. Finish the wizard.

This app uses Firestore from the backend only, so you do not need to build client-side Firestore queries for the current feature set.

### 5. Generate the Admin SDK service account key

1. In Firebase console, open `Project settings`.
2. Open the `Service accounts` tab.
3. Click `Generate new private key`.
4. Save the downloaded JSON somewhere outside version control.

Firebase's Admin SDK docs recommend using service account credentials for trusted server environments.

## Environment files

This repo now uses two env files:

- Root `.env` for Flask/backend secrets
- `frontend/.env.local` for Vite/Firebase web config

### Backend `.env`

Copy the template:

```bash
Copy-Item .env.example .env
```

Set these values:

```env
OPENAI_API_KEY=sk-...
RAPIDAPI_KEY=your-rapidapi-key
SERPAPI_KEY=your-serpapi-key
FLASK_SECRET_KEY=change-me
FLASK_ENV=development
FLASK_PORT=5001
FRONTEND_URL=http://localhost:5173

# Preferred option: point to the downloaded service-account JSON
FIREBASE_SERVICE_ACCOUNT_KEY_PATH=C:\\path\\to\\firebase-service-account.json

# Optional alternative instead of FIREBASE_SERVICE_ACCOUNT_KEY_PATH
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_CLIENT_EMAIL=firebase-adminsdk-xxxxx@your-project-id.iam.gserviceaccount.com
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
```

Use either:

- `FIREBASE_SERVICE_ACCOUNT_KEY_PATH`, or
- the inline trio `FIREBASE_PROJECT_ID`, `FIREBASE_CLIENT_EMAIL`, and `FIREBASE_PRIVATE_KEY`

### Frontend `frontend/.env.local`

Copy the template:

```bash
cd frontend
Copy-Item .env.example .env.local
```

Then fill in:

```env
VITE_API_URL=http://localhost:5001/api
VITE_FIREBASE_API_KEY=your-web-api-key
VITE_FIREBASE_AUTH_DOMAIN=your-project-id.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-project-id
VITE_FIREBASE_APP_ID=your-web-app-id
VITE_FIREBASE_MESSAGING_SENDER_ID=your-sender-id
```

All of these values come from the Firebase web app registration screen or Project settings.

## Install and run

### Backend

```bash
cd backend
python -m venv venv
# Windows PowerShell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Backend runs on `http://localhost:5001` by default.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:5173`.

## Firestore data model

No manual SQL schema is required anymore. The backend creates documents on demand in these collections:

- `conversations`
- `conversations/{conversationId}/messages`
- `itineraries`

Each signed-in user's conversation list is filtered server-side after Firebase ID token verification.

## How auth works now

1. The frontend signs users in with Firebase Auth.
2. Firebase returns an ID token for the signed-in user.
3. The frontend sends that token to Flask in the `Authorization: Bearer <token>` header.
4. Flask verifies the token with `firebase_admin.auth.verify_id_token(...)`.
5. If verification succeeds, the backend loads or writes that user's Firestore data.

That follows Firebase's recommended backend flow for custom servers: send the client's ID token over HTTPS, then verify it server-side with the Admin SDK.

## Duplicate-signup bug fix

The old signup flow proxied to Supabase and could leave the UI in a bad state when an address already existed. The new signup flow uses Firebase Authentication directly in the frontend and maps `auth/email-already-in-use` to a clear error message:

- `An account with this email already exists. Sign in instead.`

That means an existing email can no longer silently "sign up" again.

## Migration notes

- Existing Supabase users are not automatically migrated by this code change.
- Existing Supabase conversation history is not imported into Firestore by this change.
- If you want, the next step can be a one-time migration script from Supabase Auth + tables into Firebase Auth + Firestore.

## Troubleshooting

### `Invalid token`

Usually means one of these:

- frontend is pointed at one Firebase project and backend service-account creds point at another
- backend `.env` is missing Firebase Admin credentials
- frontend `.env.local` still contains old values

### Firebase signup/login works but saved trips do not

Usually means:

- Firestore was not created yet
- backend is not using valid Admin SDK credentials
- backend needs a restart after editing `.env`

### `Module not found: firebase`

Run:

```bash
cd frontend
npm install
```

### Python import errors for Firebase Admin

Run:

```bash
cd backend
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

