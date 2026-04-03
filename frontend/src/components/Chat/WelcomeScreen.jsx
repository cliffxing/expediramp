import React from 'react';
import { Plane, Hotel, Train, MapPin } from 'lucide-react';

const SUGGESTIONS = [
  { icon: Plane,  label: 'Multi-city Asia',  text: 'Plan a 10-day trip to Japan covering Tokyo and Osaka' },
  { icon: Hotel,  label: 'Weekend escape',   text: 'Find me a luxury weekend getaway in Miami for two' },
  { icon: MapPin, label: 'Budget travel',    text: 'I want to backpack through Europe for 3 weeks on a budget' },
  { icon: Train,  label: 'City explorer',    text: 'Plan a city break in Seoul with subway-friendly neighborhoods' },
];

export default function WelcomeScreen({ onSuggestionClick }) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] px-4 animate-fade-in">
      {/* Badge */}
      <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-ramp-yellow text-ramp-text text-xs font-semibold mb-6">
        <Plane size={12} />
        AI-Powered Travel Planning
      </div>

      <h2 className="text-3xl font-bold text-ramp-text text-center text-balance leading-tight">
          Modern Travel Runs on Expediramp
      </h2>
      <p className="text-sm text-ramp-text-secondary mt-3 text-center max-w-md text-balance leading-relaxed">
        Describe your dream trip in plain English. Our AI agent finds the best flights,
        hotels, and transportation — then builds a complete itinerary.
      </p>

      {/* Suggestion cards — Ramp table-row style, sharp corners */}
      <div className="w-full max-w-lg mt-8 bg-ramp-surface border border-ramp-border shadow-ramp overflow-hidden">
        {SUGGESTIONS.map((s, i) => {
          const Icon = s.icon;
          return (
            <button
              key={i}
              onClick={() => onSuggestionClick(s.text)}
              className={`w-full flex items-center gap-4 px-4 py-3.5 text-left
                         hover:bg-ramp-surface-alt transition-colors group
                         ${i < SUGGESTIONS.length - 1 ? 'border-b border-ramp-border' : ''}`}
            >
              <div className="w-7 h-7 flex items-center justify-center bg-ramp-yellow/20 flex-shrink-0">
                <Icon size={13} className="text-ramp-text" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-ramp-text-secondary group-hover:text-ramp-text transition-colors">{s.label}</p>
                <p className="text-xs text-ramp-text-tertiary truncate">{s.text}</p>
              </div>
              <svg width="13" height="13" viewBox="0 0 16 16" fill="none" className="text-ramp-text-tertiary group-hover:text-ramp-text transition-colors flex-shrink-0">
                <path d="M6 3l5 5-5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          );
        })}
      </div>

      <p className="text-2xs text-ramp-text-tertiary mt-5">
        Or type anything below to get started
      </p>
    </div>
  );
}
