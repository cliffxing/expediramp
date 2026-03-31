import React from 'react';
import { Plane, Hotel, Car, MapPin, Sparkles } from 'lucide-react';

const SUGGESTIONS = [
  {
    icon: Plane,
    text: 'Plan a 10-day trip to Japan covering Tokyo and Osaka',
  },
  {
    icon: Hotel,
    text: 'Find me a luxury weekend getaway in Miami for two',
  },
  {
    icon: MapPin,
    text: 'I want to backpack through Europe for 3 weeks on a budget',
  },
  {
    icon: Car,
    text: 'Road trip from LA to San Francisco with stops along the coast',
  },
];

export default function WelcomeScreen({ onSuggestionClick }) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] px-4 animate-fade-in">
      {/* Hero */}
      <div className="w-16 h-16 bg-ramp-accent rounded-2xl flex items-center justify-center mb-6 shadow-ramp-md">
        <Sparkles size={28} className="text-white" />
      </div>
      <h2 className="text-2xl font-bold text-ramp-text text-center text-balance">
        Modern Travel Runs on Expediramp
      </h2>
      <p className="text-sm text-ramp-text-secondary mt-2 text-center max-w-md text-balance">
        Describe your dream trip in plain English. Our AI agent will find the best flights,
        hotels, and transportation — then build a complete itinerary for you.
      </p>

      {/* Suggestion pills */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 mt-8 w-full max-w-lg">
        {SUGGESTIONS.map((s, i) => {
          const Icon = s.icon;
          return (
            <button
              key={i}
              onClick={() => onSuggestionClick(s.text)}
              className="ramp-card flex items-start gap-3 px-4 py-3.5 text-left
                         hover:shadow-ramp-md hover:border-ramp-border-strong
                         transition-all duration-200 group"
            >
              <Icon
                size={16}
                className="text-ramp-text-tertiary group-hover:text-ramp-accent
                           transition-colors mt-0.5 flex-shrink-0"
              />
              <span className="text-xs text-ramp-text-secondary group-hover:text-ramp-text transition-colors leading-relaxed">
                {s.text}
              </span>
            </button>
          );
        })}
      </div>

      <p className="text-2xs text-ramp-text-tertiary mt-6">
        Or type anything below to get started
      </p>
    </div>
  );
}
