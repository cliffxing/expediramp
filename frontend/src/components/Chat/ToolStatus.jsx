import React from 'react';
import { Plane, Hotel, Car, Train, Map, Loader2 } from 'lucide-react';

const TOOL_META = {
  search_flights: { icon: Plane, label: 'Searching flights', color: 'text-ramp-blue' },
  search_hotels: { icon: Hotel, label: 'Finding hotels', color: 'text-ramp-amber' },
  search_car_rentals: { icon: Car, label: 'Checking car rentals', color: 'text-ramp-green' },
  search_transit: { icon: Train, label: 'Looking up transit', color: 'text-ramp-green' },
  build_itinerary: { icon: Map, label: 'Building your itinerary', color: 'text-ramp-accent' },
};

export default function ToolStatus({ tools }) {
  if (!tools || tools.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2 animate-fade-in">
      {tools.map((tool, i) => {
        const meta = TOOL_META[tool] || { icon: Loader2, label: tool, color: 'text-ramp-text-secondary' };
        const Icon = meta.icon;
        return (
          <div
            key={`${tool}-${i}`}
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full
                       bg-ramp-surface-alt border border-ramp-border text-xs font-medium text-ramp-text-secondary"
          >
            <Icon size={13} className={`${meta.color} animate-spin-slow`} />
            <span>{meta.label}</span>
            <Loader2 size={11} className="animate-spin text-ramp-text-tertiary" />
          </div>
        );
      })}
    </div>
  );
}
