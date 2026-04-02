import React, { useEffect, useState } from 'react';
import { Plane, Hotel, Train, Map, RotateCcw } from 'lucide-react';

const TOOL_META = {
  search_flights:          { icon: Plane,      label: 'Searching flights' },
  search_flights_roundtrip:{ icon: RotateCcw,  label: 'Searching round-trip flights' },
  search_hotels:           { icon: Hotel,      label: 'Finding hotels' },
  search_transit:          { icon: Train,      label: 'Looking up transit' },
  build_itinerary:         { icon: Map,        label: 'Building your itinerary' },
};

const THINKING_PHRASES = [
  'Thinking through your trip…',
  'Figuring out the best options…',
  'On it…',
  'Mapping out your journey…',
];

// Minimal pulsing bar — three ramp-yellow segments
function PulseBar() {
  return (
    <div className="flex items-center gap-0.5">
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="w-1 bg-ramp-yellow animate-pulse-dot"
          style={{ height: '10px', animationDelay: `${i * 150}ms` }}
        />
      ))}
    </div>
  );
}

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
      <PulseBar />
      <span
        className="text-xs text-ramp-text-secondary transition-opacity duration-300"
        style={{ opacity: visible ? 1 : 0 }}
      >
        {THINKING_PHRASES[phraseIdx]}
      </span>
    </div>
  );
}

function ToolRow({ name }) {
  const meta = TOOL_META[name];
  if (!meta) return null;
  const Icon = meta.icon;

  return (
    <div className="flex items-center gap-2.5 animate-fade-in">
      <PulseBar />
      <div className="flex items-center gap-1.5">
        <Icon size={12} className="text-ramp-text-tertiary flex-shrink-0" />
        <span className="text-xs text-ramp-text-secondary">{meta.label}</span>
      </div>
    </div>
  );
}

export default function ToolStatus({ tools, isLoading }) {
  if (!isLoading && (!tools || tools.length === 0)) return null;

  const activeKnownTools = (tools || []).filter((t) => TOOL_META[t]);

  return (
    <div className="space-y-2 py-1">
      {activeKnownTools.length > 0 ? (
        activeKnownTools.map((tool, i) => (
          <ToolRow key={`${tool}-${i}`} name={tool} />
        ))
      ) : (
        isLoading && <ThinkingIndicator />
      )}
    </div>
  );
}