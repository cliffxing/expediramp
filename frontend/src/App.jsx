import React, { useState, useRef, useEffect, useCallback } from 'react';
import Header from './components/Layout/Header';
import Sidebar from './components/Layout/Sidebar';
import ChatInput from './components/Chat/ChatInput';
import ChatMessage from './components/Chat/ChatMessage';
import ToolStatus from './components/Chat/ToolStatus';
import WelcomeScreen from './components/Chat/WelcomeScreen';
import ItineraryTimeline, { DailyItineraryTimeline } from './components/Timeline/ItineraryTimeline';

function SmartTimeline({ itinerary }) {
  if (!itinerary) return null;
  // build_daily_itinerary items are all type="activity"
  const isDaily = itinerary.items?.length > 0 && itinerary.items.every(i => i.type === 'activity');
  if (isDaily) return <DailyItineraryTimeline itinerary={itinerary} />;
  return <ItineraryTimeline itinerary={itinerary} />;
}
import AuthModal from './components/Auth/AuthModal';
import { useAuth } from './context/AuthContext';
import { sendMessageStream, createConversation, getConversationMessages } from './api/client';
import { downloadItineraryPdf } from './lib/pdf';

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

function DayItineraryPrompt({ onConfirm, onDismiss, disabled }) {
  return (
    <div className="ml-11 mt-3">
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
            onClick={onConfirm}
            disabled={disabled}
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
  const [notificationPermission, setNotificationPermission] = useState(() => {
    if (typeof window === 'undefined' || !('Notification' in window)) return 'denied';
    return Notification.permission;
  });
  const scrollRef = useRef(null);
  const currentStreamControllerRef = useRef(null);

  const prevUserRef = useRef(user);

  const clearLoadingState = useCallback(() => {
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
    const prev = prevUserRef.current;
    prevUserRef.current = user;
    if (prev && !user) {
      setMessages([]);
      setPendingItinerary(null);
      setStreamingText('');
      setActiveTools([]);
      setConversationId(null);
      setDismissedPromptKey(null);
      abortActiveStream();
    }
  }, [abortActiveStream, user]);

  const notifyRequestFinished = useCallback((title, body) => {
    if (
      !notifyOnFinish ||
      typeof window === 'undefined' ||
      !('Notification' in window) ||
      Notification.permission !== 'granted'
    ) {
      return;
    }

    if (document.visibilityState === 'visible' && document.hasFocus()) {
      return;
    }

    try {
      new Notification(title, {
        body,
        icon: '/favicon.svg',
        badge: '/favicon.svg',
      });
    } catch (error) {
      console.error('Failed to show completion notification:', error);
    }
  }, [notifyOnFinish]);

  const handleToggleNotifyOnFinish = useCallback(async () => {
    if (typeof window === 'undefined' || !('Notification' in window)) {
      return;
    }

    if (Notification.permission === 'granted') {
      setNotifyOnFinish((prev) => !prev);
      setNotificationPermission('granted');
      return;
    }

    const permission = await Notification.requestPermission();
    setNotificationPermission(permission);
    setNotifyOnFinish(permission === 'granted');
  }, []);

  const recoverConversationState = useCallback(async () => {
    if (!user || !token || !conversationId || !isLoading) return;

    try {
      const data = await getConversationMessages(token, conversationId);
      const loaded = (data.messages || []).map((m) => ({
        role: m.role,
        content: m.content,
        itinerary: m.metadata?.itinerary || null,
      }));

      const hasAssistantReply = loaded.some((message) => message.role === 'assistant');
      if (!hasAssistantReply) return;

      currentStreamControllerRef.current?.abort();
      currentStreamControllerRef.current = null;
      setMessages(loaded);
      clearLoadingState();
    } catch (error) {
      console.error('Failed to recover conversation after app resume:', error);
    }
  }, [clearLoadingState, conversationId, isLoading, token, user]);

  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden' && !notifyOnFinish) {
        abortActiveStream();
        return;
      }

      if (document.visibilityState === 'visible') {
        setTimeout(() => {
          if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
          }
        }, 50);
        recoverConversationState();
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [abortActiveStream, notifyOnFinish, recoverConversationState]);

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
    abortActiveStream();
    setMessages([]);
    setPendingItinerary(null);
    setConversationId(null);
    setDismissedPromptKey(null);
  };

  const handleDownloadPdf = useCallback((message) => {
    if (!message?.itinerary) return;
    downloadItineraryPdf(message.itinerary, message.content || '');
  }, []);

  const handleSelectConversation = async (convo) => {
    abortActiveStream();
    setLoadingConvo(true);
    setConversationId(convo.id);
    setPendingItinerary(null);
    setMessages([]);
    setDismissedPromptKey(null);
    setRequestStartedAt(null);
    setNotifyOnFinish(false);
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

    const latestItineraryMsg = [...messages]
      .reverse()
      .find((m) => m.role === 'assistant' && m.itinerary);

    // Build a rich per-day schedule from flight items so the AI knows
    // exactly which city the traveler is in at each point in time.
    function buildFlightSchedule(itin) {
      const flights = (itin.items || []).filter(i => i.type === 'flight');
      if (!flights.length) return '';

      const lines = ['FLIGHT SCHEDULE (use this to constrain day-by-day activities):'];
      for (const f of flights) {
        const d = f.details || {};
        // Extract first departure time and last arrival time from segments
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
      // Strip any stale [FULL_ITINERARY_JSON] blocks that may have been injected
      // in previous turns — we only ever want ONE copy in the context.
      const cleanContent = (m.content || '').replace(/\[FULL_ITINERARY_JSON:.*?\](?=\s|$)/gs, '').trimEnd();

      if (m === latestItineraryMsg) {
        const itin = m.itinerary;
        const totalCost = (itin.items || []).reduce((sum, i) => sum + (i.cost || 0), 0);

        // Rich item summaries — flights include date + route, hotels include city + dates
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

        const itineraryContext =
          `\n\n[CURRENT_ITINERARY: ${itin.trip_title || 'Trip'} | ` +
          `${itin.start_date} to ${itin.end_date} | ` +
          `${itin.travelers || 1} traveler(s) | ` +
          `Items: ${itemSummaries.join('; ')} | ` +
          `Total: $${totalCost}]` +
          (flightSchedule ? `\n${flightSchedule}` : '') +
          `\n[FULL_ITINERARY_JSON: ${JSON.stringify(itin)}]`;

        return { role: m.role, content: cleanContent + itineraryContext };
      }
      return { role: m.role, content: cleanContent };
    });

    let accumulatedText = '';
    let receivedItinerary = null;
    const streamController = new AbortController();
    currentStreamControllerRef.current = streamController;

    try {
      await sendMessageStream({
        message: text,
        history,
        conversationId: activeConvoId,
        token,
        signal: streamController.signal,
        onToken: (tok) => {
          accumulatedText += tok;
          setStreamingText(accumulatedText);
        },
        onToolStart: (data) => setActiveTools((prev) => [...prev, data.tool]),
        onToolResult: (data) => setActiveTools((prev) => prev.filter((t) => t !== data.tool)),
        onItinerary: (data) => {
          receivedItinerary = data;
          setPendingItinerary(data);
          setActiveTools([]);
        },
        onDone: () => {
          const assistantMsg = { role: 'assistant', content: accumulatedText || '' };
          if (receivedItinerary) {
            assistantMsg.itinerary = receivedItinerary;
          }
          if (accumulatedText.trim() || receivedItinerary) {
            setMessages((prev) => [...prev, assistantMsg]);
          }
          setStreamingText('');
          setActiveTools([]);
          setPendingItinerary(null);
          setIsLoading(false);
          setRequestStartedAt(null);
          setNotifyOnFinish(false);
          setSidebarRefreshKey((prev) => prev + 1);
          currentStreamControllerRef.current = null;
          notifyRequestFinished(
            receivedItinerary ? 'Your trip is ready' : 'Expediramp finished thinking',
            receivedItinerary
              ? (receivedItinerary.trip_title || 'Your itinerary is ready to review.')
              : 'Your latest travel response is ready.'
          );
        },
        onError: (err) => {
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
          setSidebarRefreshKey((prev) => prev + 1);
          currentStreamControllerRef.current = null;
          notifyRequestFinished('Trip planning stopped', 'Expediramp ran into an error on your latest request.');
        },
      });
    } catch (e) {
      if (e?.name === 'AbortError') {
        return;
      }
      if (isLoading) {
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
        setSidebarRefreshKey((prev) => prev + 1);
        currentStreamControllerRef.current = null;
        notifyRequestFinished('Trip planning stopped', 'Expediramp could not finish your latest request.');
      }
    }
  };

  const hasMessages = messages.length > 0 || streamingText || pendingItinerary;
  const latestItinerary = [...messages].reverse().find((m) => m.itinerary)?.itinerary || null;

  return (
    <div className="flex flex-col h-screen">
      <Header onNewChat={handleNewChat} onShowAuth={() => setShowAuth(true)} />

      <div className="flex flex-1 overflow-hidden">
        {user && (
          <Sidebar
            token={token}
            activeConversationId={conversationId}
            refreshKey={sidebarRefreshKey}
            onSelect={handleSelectConversation}
            onNewChat={handleNewChat}
          />
        )}

        <div className="flex flex-col flex-1 overflow-hidden">
          <main ref={scrollRef} className="flex-1 overflow-y-auto">
            <div className="max-w-3xl mx-auto px-4 py-6">
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

                        {/* Itinerary renders first so the prompt appears below it */}
                        {msg.itinerary && (
                          <div className="mt-4 mb-2">
                            <SmartTimeline itinerary={msg.itinerary} />
                          </div>
                        )}

                        {/* Prompt appears AFTER the itinerary block */}
                        {showPrompt && (
                          <DayItineraryPrompt
                            disabled={isLoading}
                            onConfirm={() => handleSend(DAILY_ITINERARY_CONFIRMATION)}
                            onDismiss={() => setDismissedPromptKey(`${idx}:${msg.content}`)}
                          />
                        )}
                      </React.Fragment>
                    );
                  })}

                  {streamingText && (
                    <ChatMessage role="assistant" content={streamingText} isStreaming={isLoading} />
                  )}

                  {isLoading && (
                    <div className="flex gap-3">
                      <div className="flex-shrink-0 w-8" />
                      <ToolStatus
                        tools={activeTools}
                        isLoading={isLoading}
                        elapsedMs={requestStartedAt ? elapsedNow - requestStartedAt : 0}
                        notifyEnabled={notifyOnFinish}
                        notificationPermission={notificationPermission}
                        onToggleNotify={handleToggleNotifyOnFinish}
                      />
                    </div>
                  )}

                  {pendingItinerary && (
                    <div className="mt-4 mb-2">
                      <SmartTimeline itinerary={pendingItinerary} />
                    </div>
                  )}
                </div>
              )}
            </div>
          </main>

          <div className="border-t border-ramp-border bg-ramp-bg">
            <div className="max-w-3xl mx-auto px-4 py-4">
              <ChatInput
                onSend={handleSend}
                disabled={isLoading}
                placeholder={
                  latestItinerary
                    ? "Refine your trip — e.g., 'I want a nicer hotel' or 'Avoid DXB layovers'"
                    : "Describe your dream trip…"
                }
              />
            </div>
          </div>
        </div>
      </div>

      {showAuth && <AuthModal onClose={() => setShowAuth(false)} />}
    </div>
  );
}
