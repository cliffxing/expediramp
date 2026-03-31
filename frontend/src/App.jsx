import React, { useState, useRef, useEffect, useCallback } from 'react';
import Header from './components/Layout/Header';
import ChatInput from './components/Chat/ChatInput';
import ChatMessage from './components/Chat/ChatMessage';
import ToolStatus from './components/Chat/ToolStatus';
import WelcomeScreen from './components/Chat/WelcomeScreen';
import ItineraryTimeline from './components/Timeline/ItineraryTimeline';
import AuthModal from './components/Auth/AuthModal';
import { useAuth } from './context/AuthContext';
import { sendMessageStream } from './api/client';

export default function App() {
  const { token } = useAuth();
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [activeTools, setActiveTools] = useState([]);
  const [streamingText, setStreamingText] = useState('');
  const [showAuth, setShowAuth] = useState(false);
  const [currentItinerary, setCurrentItinerary] = useState(null);
  const scrollRef = useRef(null);

  // Auto-scroll to bottom
  const scrollToBottom = useCallback(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingText, currentItinerary, scrollToBottom]);

  const handleNewChat = () => {
    setMessages([]);
    setCurrentItinerary(null);
    setStreamingText('');
    setActiveTools([]);
  };

  const handleSend = async (text) => {
    const userMsg = { role: 'user', content: text };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);
    setStreamingText('');
    setActiveTools([]);

    // Build history for API (exclude itinerary metadata from content)
    const history = messages.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    let accumulatedText = '';

    try {
      await sendMessageStream({
        message: text,
        history,
        token,
        onToken: (tok) => {
          accumulatedText += tok;
          setStreamingText(accumulatedText);
        },
        onToolStart: (data) => {
          setActiveTools((prev) => [...prev, data.tool]);
        },
        onToolResult: (data) => {
          setActiveTools((prev) => prev.filter((t) => t !== data.tool));
        },
        onItinerary: (data) => {
          setCurrentItinerary(data);
          setActiveTools([]);
        },
        onDone: () => {
          if (accumulatedText.trim()) {
            setMessages((prev) => [...prev, { role: 'assistant', content: accumulatedText }]);
          }
          setStreamingText('');
          setActiveTools([]);
          setIsLoading(false);
        },
        onError: (err) => {
          setMessages((prev) => [
            ...prev,
            { role: 'assistant', content: `Sorry, something went wrong: ${err}. Please try again.` },
          ]);
          setStreamingText('');
          setActiveTools([]);
          setIsLoading(false);
        },
      });
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Connection error. Please check that the backend is running and try again.' },
      ]);
      setStreamingText('');
      setIsLoading(false);
    }
  };

  const hasMessages = messages.length > 0 || streamingText || currentItinerary;

  return (
    <div className="flex flex-col h-screen">
      <Header
        onNewChat={handleNewChat}
        onShowAuth={() => setShowAuth(true)}
      />

      {/* Main content area */}
      <main ref={scrollRef} className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-4 py-6">
          {!hasMessages ? (
            <WelcomeScreen onSuggestionClick={handleSend} />
          ) : (
            <div className="space-y-5">
              {/* Chat messages */}
              {messages.map((msg, idx) => (
                <ChatMessage key={idx} role={msg.role} content={msg.content} />
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

              {/* Itinerary */}
              {currentItinerary && (
                <div className="mt-6">
                  <ItineraryTimeline itinerary={currentItinerary} />
                </div>
              )}
            </div>
          )}
        </div>
      </main>

      {/* Input area */}
      <div className="border-t border-ramp-border bg-ramp-bg">
        <div className="max-w-3xl mx-auto px-4 py-4">
          <ChatInput
            onSend={handleSend}
            disabled={isLoading}
            placeholder={
              currentItinerary
                ? "Refine your trip — e.g., 'I want a nicer hotel' or 'Avoid DXB layovers'"
                : "Describe your dream trip…"
            }
          />
        </div>
      </div>

      {/* Auth modal */}
      {showAuth && <AuthModal onClose={() => setShowAuth(false)} />}
    </div>
  );
}
