import React, { useEffect, useMemo, useState } from 'react';
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

function DeepThinkingPanel({
  elapsedMs,
  activeToolCount,
  notifyEnabled,
  notificationPermission,
  onToggleNotify,
}) {
  const seconds = Math.max(1, Math.round(elapsedMs / 1000));
  const detail = useMemo(() => {
    if (activeToolCount > 1) {
      return 'Comparing flights, stays, and transit to get the best mix.';
    }
    if (activeToolCount === 1) {
      return 'Finishing a deeper pass so the trip stays coherent and bookable.';
    }
    return 'Taking a deeper planning pass to weigh timing, routing, and tradeoffs.';
  }, [activeToolCount]);

  const notifyLabel =
    notificationPermission === 'granted'
      ? (notifyEnabled ? 'Will notify when finished' : 'Notify me when finished')
      : 'Enable finish notification';

  return (
    <div className="rounded-xl border border-ramp-border bg-ramp-surface px-3 py-3 shadow-sm animate-fade-in sm:px-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex items-start gap-3">
            <PulseBar />
            <div className="min-w-0">
              <p className="text-sm font-semibold text-ramp-text">Thinking deeply</p>
              <p className="mt-0.5 text-xs leading-relaxed text-ramp-text-secondary">{detail}</p>
            </div>
          </div>
          <p className="mt-2 text-2xs uppercase tracking-[0.18em] text-ramp-text-tertiary">
            {seconds}s elapsed
          </p>
        </div>
        <div className="flex w-full shrink-0 items-center sm:w-auto">
          <button
            type="button"
            onClick={onToggleNotify}
            className={`border px-3 py-1.5 text-xs font-medium transition-colors ${
              notifyEnabled
                ? 'border-ramp-yellow bg-ramp-yellow/15 text-ramp-text'
                : 'border-ramp-border bg-ramp-surface-alt text-ramp-text-secondary hover:bg-ramp-bg hover:text-ramp-text'
            } w-full text-center sm:w-auto`}
          >
            {notifyLabel}
          </button>
        </div>
      </div>
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

export default function ToolStatus({
  tools,
  isLoading,
  elapsedMs = 0,
  notifyEnabled = false,
  notificationPermission = 'default',
  onToggleNotify = () => {},
}) {
  if (!isLoading && (!tools || tools.length === 0)) return null;

  const activeKnownTools = [...new Set((tools || []).filter((t) => TOOL_META[t]))];
  const showDeepThinking = elapsedMs >= 6000;

  return (
    <div className="space-y-2 py-1">
      {showDeepThinking && (
        <DeepThinkingPanel
          elapsedMs={elapsedMs}
          activeToolCount={activeKnownTools.length}
          notifyEnabled={notifyEnabled}
          notificationPermission={notificationPermission}
          onToggleNotify={onToggleNotify}
        />
      )}
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
