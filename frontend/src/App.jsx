import React, { useState, useRef, useEffect, useCallback } from 'react';
import Header from './components/Layout/Header';
import Sidebar from './components/Layout/Sidebar';
import ChatInput from './components/Chat/ChatInput';
import ChatMessage from './components/Chat/ChatMessage';
import ToolStatus from './components/Chat/ToolStatus';
import WelcomeScreen from './components/Chat/WelcomeScreen';
import ItineraryTimeline, { DailyItineraryTimeline } from './components/Timeline/ItineraryTimeline';
import AuthModal from './components/Auth/AuthModal';
import { useAuth } from './context/AuthContext';
import { sendMessageStream, createConversation, getConversationMessages } from './api/client';
import { downloadItineraryPdf } from './lib/pdf';
import { showNotification, requestPermission } from './notificationHelper';

function SmartTimeline({ itinerary }) {
  if (!itinerary) return null;
  const isDaily = itinerary.items?.length > 0 && itinerary.items.every(i => i.type === 'activity');
  if (isDaily) return <DailyItineraryTimeline itinerary={itinerary} />;
  return <ItineraryTimeline itinerary={itinerary} />;
}

const DAILY_ITINERARY_CONFIRMATION =
  'Yes, build me a day-by-day itinerary with things to do each day.';

function isDailyItineraryPrompt(content = '') {
  const normalized = content.toLowerCase();
  return (
    normalized.includes('would you like me to build') &&
    (normalized.includes('day-by-day itinerary') ||
      normalized.includes('things to do each day'))
  );
}

// ── Returns true if the itinerary is a trip-level plan (flights/hotels/transit)
function isTripItinerary(itinerary) {
  if (!itinerary) return false;
  return (itinerary.items || []).some(
    (i) => i.type === 'flight' || i.type === 'hotel' || i.type === 'transit'
  );
}

// ── Returns true if the itinerary is a daily activities plan (activities only)
function isDailyItinerary(itinerary) {
  if (!itinerary) return false;
  const items = itinerary.items || [];
  return items.length > 0 && items.every((i) => i.type === 'activity');
}

// ── FIX: self-dismisses on confirm to prevent double-send ──────────────────
function DayItineraryPrompt({ onConfirm, onDismiss, disabled }) {
  const [sent, setSent] = React.useState(false);

  const handleConfirm = () => {
    if (sent || disabled) return;
    setSent(true);
    onDismiss(); // hide immediately so it cannot fire again
    onConfirm();
  };

  if (sent) return null;

  return (
    <div className="mt-3">
      <div className="border border-ramp-border bg-ramp-surface-alt px-4 py-3 shadow-sm animate-slide-up">
        <p className="text-xs font-semibold text-ramp-text">
          Build your day-by-day itinerary?
        </p>
        <p className="mt-0.5 text-xs text-ramp-text-secondary">
          Add a full activity plan with things to do each day.
        </p>
        <div className="mt-2.5 flex items-center gap-2">
          <button
            type="button"
            onClick={handleConfirm}
            disabled={disabled || sent}
            className="inline-flex items-center justify-center px-3 py-1.5 text-xs font-semibold
                       bg-ramp-yellow text-ramp-text hover:bg-ramp-yellow-hover
                       transition-colors disabled:opacity-50"
          >
            Yes, build it
          </button>
          <button
            type="button"
            onClick={onDismiss}
            disabled={disabled}
            className="inline-flex items-center justify-center px-3 py-1.5 text-xs font-medium
                       text-ramp-text-secondary border border-ramp-border bg-ramp-surface
                       hover:bg-ramp-bg transition-colors disabled:opacity-50"
          >
            Dismiss
          </button>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const { token, user } = useAuth();
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [activeTools, setActiveTools] = useState([]);
  const [streamingText, setStreamingText] = useState('');
  const [showAuth, setShowAuth] = useState(false);
  const [pendingItinerary, setPendingItinerary] = useState(null);
  const [conversationId, setConversationId] = useState(null);
  const [loadingConvo, setLoadingConvo] = useState(false);
  const [dismissedPromptKey, setDismissedPromptKey] = useState(null);
  const [requestStartedAt, setRequestStartedAt] = useState(null);
  const [notifyOnFinish, setNotifyOnFinish] = useState(false);
  const [sidebarRefreshKey, setSidebarRefreshKey] = useState(0);
  const [elapsedNow, setElapsedNow] = useState(Date.now());
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [notificationPermission, setNotificationPermission] = useState(() => {
    if (typeof window === 'undefined' || !('Notification' in window)) return 'denied';
    return Notification.permission;
  });
  const scrollRef = useRef(null);
  const currentStreamControllerRef = useRef(null);
  const requestInFlightRef = useRef(false);
  const notifyOnFinishRef = useRef(false);
  const notificationPermissionRef = useRef(notificationPermission);
  const messagesRef = useRef(messages);
  const backgroundSyncInFlightRef = useRef(false);
  const completionNotificationSentRef = useRef(false);
  const lastStreamActivityAtRef = useRef(0);
  const prevUserRef = useRef(user);

  // ── Background conversation cache ─────────────────────────────────────────
  // Stores per-conversation state for conversations that have an active stream
  // running in the background. Shape: Map<conversationId, { messages, streamingText,
  // isLoading, activeTools, pendingItinerary, requestStartedAt, streamController,
  // requestInFlight, dismissedPromptKey }>
  const conversationCacheRef = useRef(new Map());

  // ── Active stream conversation ID ref ─────────────────────────────────────
  // Tracks which conversationId currently owns the stream, even when the user
  // has navigated away from it.
  const streamingConversationIdRef = useRef(null);

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  const clearLoadingState = useCallback(() => {
    requestInFlightRef.current = false;
    notifyOnFinishRef.current = false;
    backgroundSyncInFlightRef.current = false;
    setStreamingText('');
    setActiveTools([]);
    setPendingItinerary(null);
    setIsLoading(false);
    setRequestStartedAt(null);
    setNotifyOnFinish(false);
  }, []);

  const abortActiveStream = useCallback(() => {
    if (!currentStreamControllerRef.current) return;
    currentStreamControllerRef.current.abort();
    currentStreamControllerRef.current = null;
    clearLoadingState();
  }, [clearLoadingState]);

  useEffect(() => {
    notifyOnFinishRef.current = notifyOnFinish;
  }, [notifyOnFinish]);

  useEffect(() => {
    notificationPermissionRef.current = notificationPermission;
  }, [notificationPermission]);

  useEffect(() => {
    const prev = prevUserRef.current;
    prevUserRef.current = user;
    if (prev && !user) {
      setMessages([]);
      setPendingItinerary(null);
      setStreamingText('');
      setActiveTools([]);
      setConversationId(null);
      setDismissedPromptKey(null);
      conversationCacheRef.current.clear();
      streamingConversationIdRef.current = null;
      abortActiveStream();
    }
  }, [abortActiveStream, user]);

  const notifyRequestFinished = useCallback((title, body) => {
    if (
      completionNotificationSentRef.current ||
      !notifyOnFinishRef.current ||
      typeof window === 'undefined' ||
      !('Notification' in window) ||
      notificationPermissionRef.current !== 'granted'
    ) {
      return;
    }

    completionNotificationSentRef.current = true;

    showNotification(title, body).then((sent) => {
      if (!sent) {
        completionNotificationSentRef.current = false;
        console.warn('Notification could not be delivered on this platform.');
      }
    });
  }, []);

  const handleToggleNotifyOnFinish = useCallback(async () => {
    if (typeof window === 'undefined' || !('Notification' in window)) {
      alert('Notifications are not supported in this browser. On iOS, you may need to tap "Share" and "Add to Home Screen" first.');
      return;
    }

    try {
      if (notificationPermission !== 'granted') {
        const permission = await requestPermission();
        setNotificationPermission(permission);
        if (permission !== 'granted') {
          alert('Notification permission was not granted. Please enable it in your browser settings.');
          return;
        }
      }
      setNotifyOnFinish((prev) => !prev);
    } catch (error) {
      console.error('Error requesting notification permission:', error);
      alert('There was an error requesting notification permissions.');
    }
  }, [notificationPermission]);

  const recoverConversationState = useCallback(async () => {
    if (!user || !token || !conversationId) return;

    const latestMessage = messagesRef.current[messagesRef.current.length - 1];
    const streamLooksStale =
      currentStreamControllerRef.current &&
      lastStreamActivityAtRef.current > 0 &&
      Date.now() - lastStreamActivityAtRef.current > 12000;
    const shouldRecover =
      isLoading ||
      requestInFlightRef.current ||
      Boolean(streamingText) ||
      (latestMessage?.role === 'user') ||
      streamLooksStale;

    if (!shouldRecover) return;

    try {
      const data = await getConversationMessages(token, conversationId);
      const loaded = (data.messages || []).map((m) => ({
        role: m.role,
        content: m.content,
        itinerary: m.metadata?.itinerary || null,
      }));

      if (loaded.length < messagesRef.current.length) return;

      const latestLoaded = loaded[loaded.length - 1];
      const latestCurrent = messagesRef.current[messagesRef.current.length - 1];
      const hasNewMessage = loaded.length > messagesRef.current.length && latestLoaded?.role === 'assistant';
      const hasUpdatedAssistantReply =
        loaded.length === messagesRef.current.length &&
        latestLoaded?.role === 'assistant' &&
        latestCurrent?.role === 'assistant' &&
        (
          latestCurrent.content !== latestLoaded.content ||
          Boolean(latestLoaded.itinerary && !latestCurrent.itinerary)
        );

      if (!hasNewMessage && !hasUpdatedAssistantReply) return;

      currentStreamControllerRef.current?.abort();
      currentStreamControllerRef.current = null;
      setMessages(loaded);
      clearLoadingState();
    } catch (error) {
      console.error('Failed to recover conversation after app resume:', error);
    }
  }, [clearLoadingState, conversationId, isLoading, streamingText, token, user]);

  useEffect(() => {
    const handleResume = () => {
      setTimeout(() => {
        if (scrollRef.current) {
          scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
      }, 50);
      recoverConversationState();
      setTimeout(() => recoverConversationState(), 1200);
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        handleResume();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('focus', handleResume);
    window.addEventListener('pageshow', handleResume);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('focus', handleResume);
      window.removeEventListener('pageshow', handleResume);
    };
  }, [recoverConversationState]);

  useEffect(() => {
    if (!isLoading || !conversationId || !user || !token) {
      return undefined;
    }

    const interval = setInterval(() => {
      const latestMessage = messagesRef.current[messagesRef.current.length - 1];
      const streamLooksStale =
        currentStreamControllerRef.current &&
        lastStreamActivityAtRef.current > 0 &&
        Date.now() - lastStreamActivityAtRef.current > 12000;

      if (streamLooksStale || latestMessage?.role === 'user') {
        recoverConversationState();
      }
    }, 8000);

    return () => clearInterval(interval);
  }, [conversationId, isLoading, recoverConversationState, token, user]);

  useEffect(() => {
    if (!user || !token || !conversationId) return undefined;

    const syncBackgroundConversation = async () => {
      if (
        !requestInFlightRef.current ||
        !notifyOnFinishRef.current ||
        document.visibilityState !== 'hidden' ||
        backgroundSyncInFlightRef.current
      ) {
        return;
      }

      backgroundSyncInFlightRef.current = true;
      try {
        const data = await getConversationMessages(token, conversationId);
        const loaded = (data.messages || []).map((m) => ({
          role: m.role,
          content: m.content,
          itinerary: m.metadata?.itinerary || null,
        }));

        if (loaded.length < messagesRef.current.length) return;

        const latestLoaded = loaded[loaded.length - 1];
        const latestCurrent = messagesRef.current[messagesRef.current.length - 1];
        const hasNewMessage = loaded.length > messagesRef.current.length && latestLoaded?.role === 'assistant';
        const hasUpdatedAssistantReply =
          loaded.length === messagesRef.current.length &&
          latestLoaded?.role === 'assistant' &&
          latestCurrent?.role === 'assistant' &&
          (
            latestCurrent.content !== latestLoaded.content ||
            Boolean(latestLoaded.itinerary && !latestCurrent.itinerary)
          );

        if (!hasNewMessage && !hasUpdatedAssistantReply) return;

        currentStreamControllerRef.current?.abort();
        currentStreamControllerRef.current = null;
        setMessages(loaded);
        clearLoadingState();
        notifyRequestFinished(
          latestLoaded.itinerary ? 'Your trip is ready' : 'Expediramp finished thinking',
          latestLoaded.itinerary?.trip_title || 'Your latest travel response is ready.'
        );
      } catch (error) {
        console.error('Failed to sync background conversation state:', error);
      } finally {
        backgroundSyncInFlightRef.current = false;
      }
    };

    const interval = setInterval(syncBackgroundConversation, 12000);
    return () => clearInterval(interval);
  }, [clearLoadingState, conversationId, notifyRequestFinished, token, user]);

  useEffect(() => {
    if (!isLoading || !requestStartedAt) return undefined;
    const interval = setInterval(() => setElapsedNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, [isLoading, requestStartedAt]);

  const scrollToBottom = useCallback(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingText, pendingItinerary, scrollToBottom]);

  const handleNewChat = () => {
    // If there's an active stream, save it to cache before clearing
    if (streamingConversationIdRef.current && currentStreamControllerRef.current) {
      conversationCacheRef.current.set(streamingConversationIdRef.current, {
        messages: [...messagesRef.current],
        streamingText,
        isLoading,
        activeTools,
        pendingItinerary,
        requestStartedAt,
        streamController: currentStreamControllerRef.current,
        requestInFlight: requestInFlightRef.current,
        dismissedPromptKey,
      });
      // Don't abort — let it keep running in the background
      currentStreamControllerRef.current = null;
      requestInFlightRef.current = false;
    } else {
      abortActiveStream();
    }

    streamingConversationIdRef.current = null;
    setMessages([]);
    setPendingItinerary(null);
    setConversationId(null);
    setDismissedPromptKey(null);
    setStreamingText('');
    setActiveTools([]);
    setIsLoading(false);
    setRequestStartedAt(null);
    setNotifyOnFinish(false);
  };

  const handleDownloadPdf = useCallback((message) => {
    if (!message?.itinerary) return;
    downloadItineraryPdf(message.itinerary, message.content || '');
  }, []);

  const handleSelectConversation = async (convo) => {
    // ── Step 1: save current in-progress state to cache (if there's an active stream) ──
    const currentlyStreamingId = streamingConversationIdRef.current;
    if (currentlyStreamingId && currentStreamControllerRef.current) {
      conversationCacheRef.current.set(currentlyStreamingId, {
        messages: [...messagesRef.current],
        streamingText,
        isLoading,
        activeTools,
        pendingItinerary,
        requestStartedAt,
        streamController: currentStreamControllerRef.current,
        requestInFlight: requestInFlightRef.current,
        dismissedPromptKey,
      });
      // Detach from UI state but do NOT abort — stream keeps running in background
      currentStreamControllerRef.current = null;
      requestInFlightRef.current = false;
    } else if (conversationId && conversationId !== convo.id) {
      // No active stream but save the settled messages so switching back is instant
      conversationCacheRef.current.set(conversationId, {
        messages: [...messagesRef.current],
        streamingText: '',
        isLoading: false,
        activeTools: [],
        pendingItinerary: null,
        requestStartedAt: null,
        streamController: null,
        requestInFlight: false,
        dismissedPromptKey,
      });
    }

    // ── Step 2: check if the target conversation is already cached ──
    const cached = conversationCacheRef.current.get(convo.id);
    if (cached) {
      // Restore all state from cache — no network fetch needed
      setConversationId(convo.id);
      setMessages(cached.messages);
      setStreamingText(cached.streamingText || '');
      setIsLoading(cached.isLoading || false);
      setActiveTools(cached.activeTools || []);
      setPendingItinerary(cached.pendingItinerary || null);
      setRequestStartedAt(cached.requestStartedAt || null);
      setDismissedPromptKey(cached.dismissedPromptKey || null);
      setNotifyOnFinish(false);

      // If there's a live stream controller in the cache, re-attach it
      if (cached.streamController) {
        currentStreamControllerRef.current = cached.streamController;
        requestInFlightRef.current = cached.requestInFlight || false;
        streamingConversationIdRef.current = convo.id;
      } else {
        streamingConversationIdRef.current = null;
      }
      return;
    }

    // ── Step 3: not cached — fetch from server ──
    setLoadingConvo(true);
    setConversationId(convo.id);
    setPendingItinerary(null);
    setMessages([]);
    setStreamingText('');
    setActiveTools([]);
    setIsLoading(false);
    setRequestStartedAt(null);
    setDismissedPromptKey(null);
    setNotifyOnFinish(false);
    streamingConversationIdRef.current = null;
    currentStreamControllerRef.current = null;
    requestInFlightRef.current = false;

    try {
      const data = await getConversationMessages(token, convo.id);
      const loaded = (data.messages || []).map((m) => ({
        role: m.role,
        content: m.content,
        itinerary: m.metadata?.itinerary || null,
      }));
      setMessages(loaded);
    } catch (e) {
      console.error('Failed to load conversation:', e);
    } finally {
      setLoadingConvo(false);
    }
  };

  const handleSend = async (text) => {
    if (isLoading || currentStreamControllerRef.current) {
      return;
    }

    // ── FIX: dedup — don't re-send if the last message is already this text ──
    const lastMsg = messagesRef.current[messagesRef.current.length - 1];
    if (lastMsg?.role === 'user' && lastMsg?.content === text) {
      return;
    }

    requestInFlightRef.current = true;
    notifyOnFinishRef.current = false;
    completionNotificationSentRef.current = false;
    lastStreamActivityAtRef.current = Date.now();
    const userMsg = { role: 'user', content: text };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);
    setElapsedNow(Date.now());
    setRequestStartedAt(Date.now());
    setNotifyOnFinish(false);
    setStreamingText('');
    setActiveTools([]);
    setPendingItinerary(null);
    setDismissedPromptKey(null);

    let activeConvoId = conversationId;
    if (user && !activeConvoId) {
      try {
        const convo = await createConversation(token, text.slice(0, 60));
        activeConvoId = convo.id;
        setConversationId(convo.id);
        setSidebarRefreshKey((prev) => prev + 1);
      } catch (e) {
        console.error('Failed to create conversation:', e);
      }
    }

    // Track which conversation owns this stream
    streamingConversationIdRef.current = activeConvoId;

    // ── Dual itinerary context injection ──────────────────────────────────────
    const latestTripItineraryMsg = [...messages]
      .reverse()
      .find((m) => m.role === 'assistant' && m.itinerary && isTripItinerary(m.itinerary));

    const latestDailyItineraryMsg = [...messages]
      .reverse()
      .find((m) => m.role === 'assistant' && m.itinerary && isDailyItinerary(m.itinerary));

    function buildFlightSchedule(itin) {
      const flights = (itin.items || []).filter(i => i.type === 'flight');
      if (!flights.length) return '';

      const lines = ['FLIGHT SCHEDULE (use this to constrain day-by-day activities):'];
      for (const f of flights) {
        const d = f.details || {};
        const getSegs = (segs) => Array.isArray(segs) ? segs : [];
        const isRT = d.is_round_trip || d.trip_type === 'round_trip';

        if (isRT) {
          const outSegs = getSegs(d.outbound_segments);
          const retSegs = getSegs(d.return_segments);
          if (outSegs.length) {
            const dep = outSegs[0];
            const arr = outSegs[outSegs.length - 1];
            lines.push(`  OUTBOUND ${dep.origin || '?'} → ${arr.destination || '?'}: departs ${dep.departure_time || '?'}, arrives ${arr.arrival_time || '?'}`);
          }
          if (retSegs.length) {
            const dep = retSegs[0];
            const arr = retSegs[retSegs.length - 1];
            lines.push(`  RETURN ${dep.origin || '?'} → ${arr.destination || '?'}: departs ${dep.departure_time || '?'}, arrives ${arr.arrival_time || '?'}`);
          }
        } else {
          const segs = getSegs(d.segments);
          if (segs.length) {
            const dep = segs[0];
            const arr = segs[segs.length - 1];
            lines.push(`  FLIGHT ${dep.origin || '?'} → ${arr.destination || '?'}: departs ${dep.departure_time || '?'}, arrives ${arr.arrival_time || '?'} on ${f.date || '?'}`);
          }
        }
      }
      return lines.join('\n');
    }

    const history = messages.map((m) => {
      const cleanContent = (m.content || '')
        .replace(/\[CURRENT_ITINERARY:.*?\](?=\s|$)/gs, '')
        .replace(/\[FULL_ITINERARY_JSON:.*?\](?=\s|$)/gs, '')
        .replace(/\[FULL_DAILY_ITINERARY_JSON:.*?\](?=\s|$)/gs, '')
        .replace(/\[FLIGHT SCHEDULE[\s\S]*?(?=\[|$)/g, '')
        .trimEnd();

      let extraContext = '';

      if (m === latestTripItineraryMsg) {
        const itin = m.itinerary;
        const totalCost = (itin.items || []).reduce((sum, i) => sum + (i.cost || 0), 0);

        const itemSummaries = (itin.items || []).map((item) => {
          const d = item.details || {};
          if (item.type === 'flight') {
            const isRT = d.is_round_trip || d.trip_type === 'round_trip';
            if (isRT) {
              const out = (d.outbound_segments || [])[0];
              const ret = (d.return_segments || [])[0];
              return `Flight: ${out?.origin || '?'}→${(d.outbound_segments || []).slice(-1)[0]?.destination || '?'} on ${item.date || '?'}` +
                     (ret ? `, return ${ret.origin || '?'}→${(d.return_segments || []).slice(-1)[0]?.destination || '?'} on ${d.return_date || '?'}` : '');
            }
            const segs = d.segments || [];
            return `Flight: ${segs[0]?.origin || '?'}→${segs.slice(-1)[0]?.destination || '?'} on ${item.date || '?'} dep ${segs[0]?.departure_time || '?'} arr ${segs.slice(-1)[0]?.arrival_time || '?'}`;
          }
          if (item.type === 'hotel') {
            return `Hotel: ${item.title} in ${item.subtitle || ''} (check-in ${item.date || '?'}, ${d.nights || '?'} nights)`;
          }
          return `${item.type}: ${item.title}`;
        });

        const flightSchedule = buildFlightSchedule(itin);

        extraContext +=
          `\n\n[CURRENT_ITINERARY: ${itin.trip_title || 'Trip'} | ` +
          `${itin.start_date} to ${itin.end_date} | ` +
          `${itin.travelers || 1} traveler(s) | ` +
          `Items: ${itemSummaries.join('; ')} | ` +
          `Total: $${totalCost}]` +
          (flightSchedule ? `\n${flightSchedule}` : '') +
          `\n[FULL_ITINERARY_JSON: ${JSON.stringify(itin)}]`;
      }

      if (m === latestDailyItineraryMsg) {
        extraContext += `\n[FULL_DAILY_ITINERARY_JSON: ${JSON.stringify(m.itinerary)}]`;
      }

      if (extraContext) {
        return { role: m.role, content: cleanContent + extraContext };
      }
      return { role: m.role, content: cleanContent };
    });

    let accumulatedText = '';
    let receivedItinerary = null;
    const streamController = new AbortController();
    currentStreamControllerRef.current = streamController;

    // Capture which conversation this stream belongs to (for background update logic)
    const thisStreamConvoId = activeConvoId;

    try {
      await sendMessageStream({
        message: text,
        history,
        conversationId: activeConvoId,
        token,
        signal: streamController.signal,
        onToken: (tok) => {
          lastStreamActivityAtRef.current = Date.now();
          accumulatedText += tok;
          // Only update UI if this stream is still the active (visible) one
          if (streamingConversationIdRef.current === thisStreamConvoId) {
            setStreamingText(accumulatedText);
          } else {
            // Update the cache entry instead
            const cached = conversationCacheRef.current.get(thisStreamConvoId);
            if (cached) {
              conversationCacheRef.current.set(thisStreamConvoId, {
                ...cached,
                streamingText: accumulatedText,
              });
            }
          }
        },
        onToolStart: (data) => {
          lastStreamActivityAtRef.current = Date.now();
          if (streamingConversationIdRef.current === thisStreamConvoId) {
            setActiveTools((prev) => [...prev, data.tool]);
          } else {
            const cached = conversationCacheRef.current.get(thisStreamConvoId);
            if (cached) {
              conversationCacheRef.current.set(thisStreamConvoId, {
                ...cached,
                activeTools: [...(cached.activeTools || []), data.tool],
              });
            }
          }
        },
        onToolResult: (data) => {
          lastStreamActivityAtRef.current = Date.now();
          if (streamingConversationIdRef.current === thisStreamConvoId) {
            setActiveTools((prev) => prev.filter((t) => t !== data.tool));
          } else {
            const cached = conversationCacheRef.current.get(thisStreamConvoId);
            if (cached) {
              conversationCacheRef.current.set(thisStreamConvoId, {
                ...cached,
                activeTools: (cached.activeTools || []).filter((t) => t !== data.tool),
              });
            }
          }
        },
        onItinerary: (data) => {
          lastStreamActivityAtRef.current = Date.now();
          receivedItinerary = data;
          if (streamingConversationIdRef.current === thisStreamConvoId) {
            setPendingItinerary(data);
            setActiveTools([]);
          } else {
            const cached = conversationCacheRef.current.get(thisStreamConvoId);
            if (cached) {
              conversationCacheRef.current.set(thisStreamConvoId, {
                ...cached,
                pendingItinerary: data,
                activeTools: [],
              });
            }
          }
        },
        onDone: () => {
          const assistantMsg = { role: 'assistant', content: accumulatedText || '' };
          if (receivedItinerary) {
            assistantMsg.itinerary = receivedItinerary;
          }

          const isVisibleConvo = streamingConversationIdRef.current === thisStreamConvoId;

          if (isVisibleConvo) {
            // Normal path — conversation is still on screen
            if (accumulatedText.trim() || receivedItinerary) {
              setMessages((prev) => [...prev, assistantMsg]);
            }
            setStreamingText('');
            setActiveTools([]);
            setPendingItinerary(null);
            setIsLoading(false);
            setRequestStartedAt(null);
            setNotifyOnFinish(false);
            currentStreamControllerRef.current = null;
            streamingConversationIdRef.current = null;
            requestInFlightRef.current = false;
          } else {
            // Conversation was switched away from — update cache with final state
            const cached = conversationCacheRef.current.get(thisStreamConvoId);
            const baseMessages = cached ? cached.messages : [];
            const finalMessages = (accumulatedText.trim() || receivedItinerary)
              ? [...baseMessages, assistantMsg]
              : baseMessages;

            conversationCacheRef.current.set(thisStreamConvoId, {
              messages: finalMessages,
              streamingText: '',
              isLoading: false,
              activeTools: [],
              pendingItinerary: null,
              requestStartedAt: null,
              streamController: null,
              requestInFlight: false,
              dismissedPromptKey: cached?.dismissedPromptKey || null,
            });
          }

          setSidebarRefreshKey((prev) => prev + 1);
          notifyRequestFinished(
            receivedItinerary ? 'Your trip is ready' : 'Expediramp finished thinking',
            receivedItinerary
              ? (receivedItinerary.trip_title || 'Your itinerary is ready to review.')
              : 'Your latest travel response is ready.'
          );
        },
        onError: (err) => {
          const isVisibleConvo = streamingConversationIdRef.current === thisStreamConvoId;
          if (isVisibleConvo) {
            setMessages((prev) => [
              ...prev,
              { role: 'assistant', content: `Sorry, something went wrong: ${err}. Please try again.` },
            ]);
            setStreamingText('');
            setActiveTools([]);
            setPendingItinerary(null);
            setIsLoading(false);
            setRequestStartedAt(null);
            setNotifyOnFinish(false);
            streamingConversationIdRef.current = null;
          } else {
            // Clear error state from cache
            const cached = conversationCacheRef.current.get(thisStreamConvoId);
            if (cached) {
              conversationCacheRef.current.set(thisStreamConvoId, {
                ...cached,
                streamingText: '',
                isLoading: false,
                activeTools: [],
                pendingItinerary: null,
                requestStartedAt: null,
                streamController: null,
                requestInFlight: false,
              });
            }
          }
          setSidebarRefreshKey((prev) => prev + 1);
          currentStreamControllerRef.current = null;
          requestInFlightRef.current = false;
          notifyRequestFinished('Trip planning stopped', 'Expediramp ran into an error on your latest request.');
        },
      });
    } catch (e) {
      if (e?.name === 'AbortError') {
        return;
      }
      const isVisibleConvo = streamingConversationIdRef.current === thisStreamConvoId;
      if (isVisibleConvo && isLoading) {
        if (accumulatedText.trim() || receivedItinerary) {
          const assistantMsg = { role: 'assistant', content: accumulatedText || '' };
          if (receivedItinerary) assistantMsg.itinerary = receivedItinerary;
          setMessages((prev) => [...prev, assistantMsg]);
        } else {
          setMessages((prev) => [
            ...prev,
            { role: 'assistant', content: 'Connection error. Please check that the backend is running and try again.' },
          ]);
        }
        setStreamingText('');
        setPendingItinerary(null);
        setIsLoading(false);
        setRequestStartedAt(null);
        setNotifyOnFinish(false);
        streamingConversationIdRef.current = null;
      }
      setSidebarRefreshKey((prev) => prev + 1);
      currentStreamControllerRef.current = null;
      requestInFlightRef.current = false;
      notifyRequestFinished('Trip planning stopped', 'Expediramp could not finish your latest request.');
    }
  };

  const hasMessages = messages.length > 0 || streamingText || pendingItinerary;

  // Whether the currently-viewed conversation has a stream running (for ChatInput disable logic)
  const activeConvoIsStreaming =
    isLoading && streamingConversationIdRef.current === conversationId;

  return (
    <div className="flex flex-col h-[100dvh] overflow-hidden">
      <Header
        onNewChat={handleNewChat}
        onShowAuth={() => setShowAuth(true)}
        onMobileSidebarOpen={() => setMobileSidebarOpen(true)}
      />

      <div className="flex flex-1 overflow-hidden min-h-0">
        {user && (
          <Sidebar
            token={token}
            activeConversationId={conversationId}
            refreshKey={sidebarRefreshKey}
            onSelect={handleSelectConversation}
            onNewChat={handleNewChat}
            mobileOpen={mobileSidebarOpen}
            onMobileClose={() => setMobileSidebarOpen(false)}
          />
        )}

        <div className="flex flex-col flex-1 overflow-hidden min-w-0">
          <main ref={scrollRef} className="flex-1 overflow-y-auto">
            <div className="max-w-3xl mx-auto px-3 sm:px-4 py-4 sm:py-6">
              {loadingConvo ? (
                <div className="flex justify-center mt-20">
                  <div className="animate-spin w-6 h-6 border-2 border-ramp-accent border-t-transparent rounded-full" />
                </div>
              ) : !hasMessages ? (
                <WelcomeScreen onSuggestionClick={handleSend} />
              ) : (
                <div className="space-y-5">
                  {messages.map((msg, idx) => {
                    const isLastMsg = idx === messages.length - 1;
                    const showPrompt =
                      msg.role === 'assistant' &&
                      isLastMsg &&
                      dismissedPromptKey !== `${idx}:${msg.content}` &&
                      isDailyItineraryPrompt(msg.content);

                    return (
                      <React.Fragment key={idx}>
                        <ChatMessage
                          role={msg.role}
                          content={msg.content}
                          canDownloadPdf={Boolean(msg.itinerary)}
                          onDownloadPdf={() => handleDownloadPdf(msg)}
                        />

                        {msg.itinerary && (
                          <div className="mt-4 mb-2">
                            <SmartTimeline itinerary={msg.itinerary} />
                          </div>
                        )}

                        {showPrompt && (
                          <DayItineraryPrompt
                            disabled={activeConvoIsStreaming}
                            onConfirm={() => handleSend(DAILY_ITINERARY_CONFIRMATION)}
                            onDismiss={() => setDismissedPromptKey(`${idx}:${msg.content}`)}
                          />
                        )}
                      </React.Fragment>
                    );
                  })}

                  {streamingText && (
                    <ChatMessage role="assistant" content={streamingText} isStreaming={activeConvoIsStreaming} />
                  )}

                  {activeConvoIsStreaming && (
                    <div className="flex gap-3">
                      <div className="flex-shrink-0 w-8 hidden sm:block" />
                      <ToolStatus
                        tools={activeTools}
                        isLoading={activeConvoIsStreaming}
                        elapsedMs={requestStartedAt ? elapsedNow - requestStartedAt : 0}
                        notifyEnabled={notifyOnFinish}
                        notificationPermission={notificationPermission}
                        onToggleNotify={handleToggleNotifyOnFinish}
                      />
                    </div>
                  )}
                </div>
              )}
            </div>
          </main>

          <div className="border-t border-ramp-border bg-ramp-bg px-3 sm:px-4 py-3">
            <div className="max-w-3xl mx-auto">
              {/* Show a read-only banner when viewing a different conversation while one is loading */}
              {isLoading && !activeConvoIsStreaming && (
                <div className="mb-2 flex items-center gap-2 px-3 py-2 bg-ramp-surface border border-ramp-border text-xs text-ramp-text-secondary">
                  <div className="w-1.5 h-1.5 rounded-full bg-ramp-yellow animate-pulse flex-shrink-0" />
                  A trip is still being planned in another conversation. Switch back to continue.
                </div>
              )}
              <ChatInput
                onSend={handleSend}
                disabled={activeConvoIsStreaming}
                isLoading={activeConvoIsStreaming}
              />
            </div>
          </div>
        </div>
      </div>

      {showAuth && <AuthModal onClose={() => setShowAuth(false)} />}
    </div>
  );
}