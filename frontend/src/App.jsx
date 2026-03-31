import React, { useState, useRef, useEffect, useCallback } from 'react';
import Header from './components/Layout/Header';
import Sidebar from './components/Layout/Sidebar';
import ChatInput from './components/Chat/ChatInput';
import ChatMessage from './components/Chat/ChatMessage';
import ToolStatus from './components/Chat/ToolStatus';
import WelcomeScreen from './components/Chat/WelcomeScreen';
import ItineraryTimeline from './components/Timeline/ItineraryTimeline';
import AuthModal from './components/Auth/AuthModal';
import { useAuth } from './context/AuthContext';
import { sendMessageStream, createConversation, getConversationMessages } from './api/client';

export default function App() {
  const { token, user } = useAuth();
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [activeTools, setActiveTools] = useState([]);
  const [streamingText, setStreamingText] = useState('');
  const [showAuth, setShowAuth] = useState(false);
  // Pending itinerary shown during streaming — merged into messages on done
  const [pendingItinerary, setPendingItinerary] = useState(null);
  const [conversationId, setConversationId] = useState(null);
  const [loadingConvo, setLoadingConvo] = useState(false);
  const scrollRef = useRef(null);

  const scrollToBottom = useCallback(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingText, pendingItinerary, scrollToBottom]);

  const handleNewChat = () => {
    setMessages([]);
    setPendingItinerary(null);
    setStreamingText('');
    setActiveTools([]);
    setConversationId(null);
  };

  const handleSelectConversation = async (convo) => {
    setLoadingConvo(true);
    setConversationId(convo.id);
    setPendingItinerary(null);
    setMessages([]);
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
    const userMsg = { role: 'user', content: text };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);
    setStreamingText('');
    setActiveTools([]);
    setPendingItinerary(null);

    // Create conversation on first message if signed in
    let activeConvoId = conversationId;
    if (user && !activeConvoId) {
      try {
        const convo = await createConversation(token, text.slice(0, 60));
        activeConvoId = convo.id;
        setConversationId(convo.id);
      } catch (e) {
        console.error('Failed to create conversation:', e);
      }
    }

    // Build history — include itinerary context so the agent knows
    // what was previously presented and can iterate on it.
    const history = messages.map((m) => {
      if (m.role === 'assistant' && m.itinerary) {
        const itin = m.itinerary;
        const itemSummaries = (itin.items || []).map((item) => {
          if (item.type === 'flight') return `Flight: ${item.title} — $${item.cost}`;
          if (item.type === 'hotel') return `Hotel: ${item.title} — $${item.cost}`;
          return `${item.type}: ${item.title} — $${item.cost}`;
        });
        const totalCost = (itin.items || []).reduce((sum, i) => sum + (i.cost || 0), 0);
        const itineraryContext = `\n\n[ITINERARY PRESENTED: ${itin.trip_title || 'Trip'} | ${itin.start_date} to ${itin.end_date} | ${itin.travelers || 1} traveler(s) | Items: ${itemSummaries.join('; ')} | Total: $${totalCost}]`;
        return { role: m.role, content: (m.content || '') + itineraryContext };
      }
      return { role: m.role, content: m.content };
    });

    let accumulatedText = '';
    let receivedItinerary = null;

    try {
      await sendMessageStream({
        message: text,
        history,
        conversationId: activeConvoId,
        token,
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
          // Always add an assistant message — attach itinerary if one was received
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
        },
      });
    } catch (e) {
      // Failsafe: if stream ends without done/error, clean up state
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
      }
    }
  };

  const hasMessages = messages.length > 0 || streamingText || pendingItinerary;
  const latestItinerary = [...messages].reverse().find((m) => m.itinerary)?.itinerary || null;

  return (
    <div className="flex flex-col h-screen">
      <Header onNewChat={handleNewChat} onShowAuth={() => setShowAuth(true)} />

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar — only for signed-in users */}
        {user && (
          <Sidebar
            token={token}
            activeConversationId={conversationId}
            onSelect={handleSelectConversation}
            onNewChat={handleNewChat}
          />
        )}

        {/* Main chat area */}
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
                  {/* Chat messages — itineraries rendered inline */}
                  {messages.map((msg, idx) => (
                    <React.Fragment key={idx}>
                      <ChatMessage role={msg.role} content={msg.content} />
                      {msg.itinerary && (
                        <div className="mt-4 mb-2">
                          <ItineraryTimeline itinerary={msg.itinerary} />
                        </div>
                      )}
                    </React.Fragment>
                  ))}

                  {/* Streaming response */}
                  {streamingText && (
                    <ChatMessage role="assistant" content={streamingText} isStreaming={isLoading} />
                  )}

                  {/* Tool activity */}
                  {activeTools.length > 0 && (
                    <div className="flex gap-3">
                      <div className="flex-shrink-0 w-8" />
                      <ToolStatus tools={activeTools} />
                    </div>
                  )}

                  {/* Pending itinerary (during streaming, before finalized) */}
                  {pendingItinerary && (
                    <div className="mt-4 mb-2">
                      <ItineraryTimeline itinerary={pendingItinerary} />
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
