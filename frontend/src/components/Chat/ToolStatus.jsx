import React, { useEffect, useState } from 'react';
import { Plane, Hotel, Train, Map, Loader2, Sparkles } from 'lucide-react';

const TOOL_META = {
  search_flights: { icon: Plane, label: 'Searching flights', color: 'text-ramp-blue' },
  search_flights_roundtrip: { icon: Plane, label: 'Searching round-trip flights', color: 'text-ramp-blue' },
  search_hotels: { icon: Hotel, label: 'Finding hotels', color: 'text-ramp-amber' },
  search_transit: { icon: Train, label: 'Looking up transit', color: 'text-ramp-green' },
  build_itinerary: { icon: Map, label: 'Building your itinerary', color: 'text-ramp-accent' },
};

const THINKING_PHRASES = [
  'Thinking through your trip…',
  'Figuring out the best options…',
  'On it…',
  'Mapping out your journey…',
];

function ThinkingIndicator() {
  const [phraseIdx, setPhraseIdx] = useState(0);
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const interval = setInterval(() => {
      setVisible(false);
      setTimeout(() => {
        setPhraseIdx((i) => (i + 1) % THINKING_PHRASES.length);
        setVisible(true);
      }, 300);
    }, 2800);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex items-center gap-3 animate-fade-in">
      {/* Animated orb */}
      <div className="relative flex items-center justify-center w-7 h-7">
        <div className="absolute inset-0 rounded-full bg-ramp-accent opacity-10 animate-ping" />
        <div className="w-5 h-5 rounded-full bg-ramp-accent flex items-center justify-center">
          <Sparkles size={10} className="text-white" />
        </div>
      </div>

      {/* Rotating phrase + dots */}
      <div className="flex items-center gap-2">
        <span
          className="text-xs font-medium text-ramp-text-secondary transition-opacity duration-300"
          style={{ opacity: visible ? 1 : 0 }}
        >
          {THINKING_PHRASES[phraseIdx]}
        </span>
        <span className="flex gap-0.5">
          <span className="typing-dot" style={{ animationDelay: '0ms' }} />
          <span className="typing-dot" style={{ animationDelay: '150ms' }} />
          <span className="typing-dot" style={{ animationDelay: '300ms' }} />
        </span>
      </div>
    </div>
  );
}

function ToolPill({ name }) {
  const meta = TOOL_META[name];
  if (!meta) return null;

  const Icon = meta.icon;

  return (
    <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-ramp-surface border border-ramp-border animate-fade-in">
      <Loader2 size={12} className={`${meta.color} animate-spin`} />
      <Icon size={12} className={meta.color} />
      <span className="text-xs font-medium text-ramp-text-secondary">{meta.label}</span>
    </div>
  );
}

export default function ToolStatus({ tools, isLoading }) {
  if (!isLoading && (!tools || tools.length === 0)) return null;

  const activeKnownTools = (tools || []).filter((t) => TOOL_META[t]);

  return (
    <div className="space-y-2">
      {activeKnownTools.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {activeKnownTools.map((tool, i) => (
            <ToolPill key={`${tool}-${i}`} name={tool} />
          ))}
        </div>
      ) : (
        isLoading && <ThinkingIndicator />
      )}
    </div>
  );
}