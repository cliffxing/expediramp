// Use VITE_API_URL if set (e.g. http://localhost:5000/api), otherwise fall back
// to the relative /api path which Vite's dev-server proxy will forward to Flask.
const API_BASE = import.meta.env.VITE_API_URL || '/api';

function getHeaders(token) {
  const h = { 'Content-Type': 'application/json' };
  if (token) h['Authorization'] = `Bearer ${token}`;
  return h;
}

// ── Chat ────────────────────────────────────────────────────────

export async function sendMessage({ message, history, conversationId, token }) {
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: getHeaders(token),
    body: JSON.stringify({
      message,
      history,
      conversation_id: conversationId,
    }),
  });
  if (!res.ok) throw new Error(`Chat error: ${res.status}`);
  return res.json();
}

export async function sendMessageStream({ message, history, conversationId, token, onToken, onToolStart, onToolResult, onItinerary, onDone, onError }) {
  const res = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: getHeaders(token),
    body: JSON.stringify({
      message,
      history,
      conversation_id: conversationId,
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    onError?.(err);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let doneReceived = false;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      try {
        const event = JSON.parse(line.slice(6));
        switch (event.type) {
          case 'token': onToken?.(event.data); break;
          case 'tool_start': onToolStart?.(event.data); break;
          case 'tool_result': onToolResult?.(event.data); break;
          case 'itinerary': onItinerary?.(event.data); break;
          case 'done':
            doneReceived = true;
            onDone?.(event.data);
            break;
          case 'error': onError?.(event.data); break;
        }
      } catch { /* skip malformed lines */ }
    }
  }

  // Process any remaining data in the buffer
  if (buffer.startsWith('data: ')) {
    try {
      const event = JSON.parse(buffer.slice(6));
      switch (event.type) {
        case 'token': onToken?.(event.data); break;
        case 'tool_start': onToolStart?.(event.data); break;
        case 'tool_result': onToolResult?.(event.data); break;
        case 'itinerary': onItinerary?.(event.data); break;
        case 'done':
          doneReceived = true;
          onDone?.(event.data);
          break;
        case 'error': onError?.(event.data); break;
      }
    } catch { /* skip malformed line */ }
  }

  // Safety net: if stream ended without a done event, fire onDone
  // so the UI doesn't get permanently stuck in loading state
  if (!doneReceived) {
    onDone?.({});
  }
}

// ── Auth ────────────────────────────────────────────────────────

export async function login(email, password) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.error || 'Login failed');
  }
  return res.json();
}

export async function signup(email, password) {
  const res = await fetch(`${API_BASE}/auth/signup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.error || 'Signup failed');
  }
  return res.json();
}

export async function getMe(token) {
  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: getHeaders(token),
  });
  if (!res.ok) throw new Error('Not authenticated');
  return res.json();
}

// ── Conversations ───────────────────────────────────────────────

export async function getConversations(token) {
  const res = await fetch(`${API_BASE}/conversations`, {
    headers: getHeaders(token),
  });
  if (!res.ok) throw new Error('Failed to load conversations');
  return res.json();
}

export async function createConversation(token, title = 'New Trip') {
  const res = await fetch(`${API_BASE}/conversations`, {
    method: 'POST',
    headers: getHeaders(token),
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error('Failed to create conversation');
  return res.json();
}

export async function getConversationMessages(token, conversationId) {
  const res = await fetch(`${API_BASE}/conversations/${conversationId}/messages`, {
    headers: getHeaders(token),
  });
  if (!res.ok) throw new Error('Failed to load messages');
  return res.json();
}