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
  const [currentItinerary, setCurrentItinerary] = useState(null);
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
  }, [messages, streamingText, currentItinerary, scrollToBottom]);

  const handleNewChat = () => {
    setMessages([]);
    setCurrentItinerary(null);
    setStreamingText('');
    setActiveTools([]);
    setConversationId(null);
  };

  const handleSelectConversation = async (convo) => {
    setLoadingConvo(true);
    setConversationId(convo.id);
    setCurrentItinerary(null);
    setMessages([]);
    try {
      const data = await getConversationMessages(token, convo.id);
      const loaded = (data.messages || []).map((m) => ({
        role: m.role,
        content: m.content,
        itinerary: m.metadata?.itinerary || null,
      }));
      setMessages(loaded);
      // Restore last itinerary if any
      const lastWithItinerary = [...loaded].reverse().find((m) => m.itinerary);
      if (lastWithItinerary) setCurrentItinerary(lastWithItinerary.itinerary);
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

    const history = messages.map((m) => ({ role: m.role, content: m.content }));
    let accumulatedText = '';

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
                  {messages.map((msg, idx) => (
                    <ChatMessage key={idx} role={msg.role} content={msg.content} />
                  ))}
                  {streamingText && (
                    <ChatMessage role="assistant" content={streamingText} isStreaming={isLoading} />
                  )}
                  {activeTools.length > 0 && (
                    <div className="flex gap-3">
                      <div className="flex-shrink-0 w-8" />
                      <ToolStatus tools={activeTools} />
                    </div>
                  )}
                  {currentItinerary && (
                    <div className="mt-6">
                      <ItineraryTimeline itinerary={currentItinerary} />
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
                  currentItinerary
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