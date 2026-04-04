// Use VITE_API_URL if set (e.g. http://localhost:5000/api), otherwise fall back
// to the relative /api path which Vite's dev-server proxy will forward to Flask.
const API_BASE = import.meta.env.VITE_API_URL || '/api';

function getHeaders(token) {
  const h = { 'Content-Type': 'application/json' };
  if (token) h['Authorization'] = `Bearer ${token}`;
  return h;
}

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

function processSSELine(line, handlers, state) {
  // Skip SSE comments (": ...") and blank lines
  if (!line || line.startsWith(':')) return;
  if (!line.startsWith('data: ')) return;

  let event;
  try {
    event = JSON.parse(line.slice(6));
  } catch {
    return;
  }

  const { onToken, onToolStart, onToolResult, onItinerary, onDone, onError } = handlers;

  switch (event.type) {
    case 'token':
      onToken?.(event.data);
      break;
    case 'tool_start':
      onToolStart?.(event.data);
      break;
    case 'tool_result':
      onToolResult?.(event.data);
      break;
    case 'itinerary':
      onItinerary?.(event.data);
      break;
    case 'done':
      if (!state.doneReceived) {
        state.doneReceived = true;
        onDone?.(event.data);
      }
      break;
    case 'error':
      onError?.(event.data);
      break;
    default:
      break;
  }
}

export async function sendMessageStream({
  message,
  history,
  conversationId,
  token,
  signal,
  onToken,
  onToolStart,
  onToolResult,
  onItinerary,
  onDone,
  onError,
}) {
  let res;
  try {
    res = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: getHeaders(token),
      signal,
      body: JSON.stringify({
        message,
        history,
        conversation_id: conversationId,
      }),
    });
  } catch (err) {
    if (err?.name === 'AbortError') throw err;
    onError?.(String(err));
    return;
  }

  if (!res.ok) {
    const err = await res.text().catch(() => `HTTP ${res.status}`);
    onError?.(err);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  const state = { doneReceived: false };
  const handlers = { onToken, onToolStart, onToolResult, onItinerary, onDone, onError };

  try {
    while (true) {
      const { done, value } = await reader.read();

      if (value) {
        buffer += decoder.decode(value, { stream: true });
      }

      // Process all complete lines from the buffer
      const lines = buffer.split('\n');
      // Keep the last potentially-incomplete line in the buffer
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        processSSELine(line.trim(), handlers, state);
      }

      if (done) break;
    }
  } catch (err) {
    if (err?.name === 'AbortError') throw err;
    // Stream was cut — fall through to the onDone safety net below
    logger: console.warn('SSE stream read error:', err);
  } finally {
    reader.releaseLock?.();
  }

  // Process anything remaining in the buffer after the stream closed
  if (buffer.trim()) {
    for (const line of buffer.split('\n')) {
      processSSELine(line.trim(), handlers, state);
    }
  }

  // Safety net: if the stream closed without a done event (proxy cut it,
  // network blip, etc.) fire onDone anyway so the UI always unlocks.
  if (!state.doneReceived) {
    onDone?.({});
  }
}

export async function getMe(token) {
  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: getHeaders(token),
  });
  if (!res.ok) throw new Error('Not authenticated');
  return res.json();
}

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