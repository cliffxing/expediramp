import React, { useState } from 'react';
import {
  Plane, Hotel, Car, Train, MapPin, ExternalLink, Clock,
  ChevronDown, ChevronUp, Star, Wifi, Waves, Dumbbell,
  Users, Calendar, DollarSign, ArrowRight, Navigation
} from 'lucide-react';

// ── Utilities ─────────────────────────────────────────────────

function formatDuration(minutes) {
  if (!minutes) return '';
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

function formatCurrency(amount) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(amount);
}

// ── Type-specific badge ───────────────────────────────────────

function TypeBadge({ type }) {
  const config = {
    flight: { icon: Plane, label: 'Flight', cls: 'ramp-badge-blue' },
    hotel: { icon: Hotel, label: 'Hotel', cls: 'ramp-badge-amber' },
    car_rental: { icon: Car, label: 'Car Rental', cls: 'ramp-badge-green' },
    transit: { icon: Train, label: 'Transit', cls: 'ramp-badge-green' },
    activity: { icon: MapPin, label: 'Activity', cls: 'ramp-badge-neutral' },
  };
  const c = config[type] || config.activity;
  const Icon = c.icon;
  return (
    <span className={c.cls}>
      <Icon size={10} className="mr-1" />
      {c.label}
    </span>
  );
}

// ── Flight Card ───────────────────────────────────────────────

function FlightCard({ item }) {
  const [expanded, setExpanded] = useState(false);
  const d = item.details || {};
  const segments = d.segments || [];
  const layovers = d.layovers || [];
  const airline = d.airline || {};

  return (
    <div className="ramp-card overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 flex items-start justify-between">
        <div className="flex items-center gap-3">
          {airline.logo ? (
            <img src={airline.logo} alt={airline.name} className="w-8 h-8 object-contain rounded" />
          ) : (
            <div className="w-8 h-8 bg-ramp-surface-alt rounded flex items-center justify-center">
              <Plane size={16} className="text-ramp-text-secondary" />
            </div>
          )}
          <div>
            <p className="text-sm font-semibold text-ramp-text">{item.title}</p>
            <p className="text-2xs text-ramp-text-tertiary">{airline.name} · {d.cabin_class || 'Economy'}</p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-sm font-semibold text-ramp-text">{formatCurrency(item.cost)}</p>
          {d.passengers > 1 && (
            <p className="text-2xs text-ramp-text-tertiary">{d.passengers} travelers</p>
          )}
        </div>
      </div>

      {/* Route summary */}
      <div className="px-5 pb-3">
        <div className="flex items-center gap-3 text-xs">
          <span className="font-mono font-semibold text-ramp-text">
            {segments[0]?.origin || '---'}
          </span>
          <div className="flex-1 flex items-center gap-1.5">
            <div className="flex-1 h-px bg-ramp-border" />
            {d.is_nonstop ? (
              <span className="ramp-badge-green">Nonstop</span>
            ) : (
              <span className="ramp-badge-amber">{layovers.length} stop{layovers.length > 1 ? 's' : ''}</span>
            )}
            <div className="flex-1 h-px bg-ramp-border" />
          </div>
          <span className="font-mono font-semibold text-ramp-text">
            {segments[segments.length - 1]?.destination || '---'}
          </span>
        </div>
        <div className="flex items-center justify-between mt-2 text-2xs text-ramp-text-secondary">
          <span>{segments[0]?.departure_time}</span>
          <span className="flex items-center gap-1">
            <Clock size={10} />
            {formatDuration(d.total_duration_minutes)}
          </span>
          <span>{segments[segments.length - 1]?.arrival_time}</span>
        </div>
      </div>

      {/* Expand for segments */}
      {segments.length > 0 && (
        <>
          <button
            onClick={() => setExpanded(!expanded)}
            className="w-full px-5 py-2.5 border-t border-ramp-border bg-ramp-surface-alt
                       flex items-center justify-center gap-1.5 text-2xs font-medium text-ramp-text-secondary
                       hover:text-ramp-text transition-colors"
          >
            {expanded ? 'Hide details' : 'View flight details'}
            {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </button>

          {expanded && (
            <div className="px-5 py-4 border-t border-ramp-border bg-ramp-surface-alt space-y-3 animate-fade-in">
              {segments.map((seg, idx) => (
                <React.Fragment key={idx}>
                  <div className="flex items-start gap-3">
                    <div className="w-1.5 h-1.5 rounded-full bg-ramp-accent mt-1.5 flex-shrink-0" />
                    <div className="flex-1 text-xs space-y-0.5">
                      <div className="flex justify-between">
                        <span className="font-medium">{seg.flight_number}</span>
                        <span className="text-ramp-text-tertiary">{seg.aircraft}</span>
                      </div>
                      <p className="text-ramp-text-secondary">
                        {seg.origin} {seg.departure_time} → {seg.destination} {seg.arrival_time}
                      </p>
                      <p className="text-ramp-text-tertiary">{formatDuration(seg.duration_minutes)}</p>
                    </div>
                  </div>
                  {idx < segments.length - 1 && layovers[idx] && (
                    <div className="ml-4 pl-3 border-l-2 border-dashed border-ramp-amber py-2">
                      <p className="text-2xs text-ramp-amber font-medium">
                        Layover in {layovers[idx].city} ({layovers[idx].airport})
                      </p>
                      <p className="text-2xs text-ramp-text-tertiary">
                        {formatDuration(layovers[idx].duration_minutes)} · {layovers[idx].airport_name}
                      </p>
                    </div>
                  )}
                </React.Fragment>
              ))}
            </div>
          )}
        </>
      )}

      {/* Booking link */}
      {item.booking_url && (
        <a
          href={item.booking_url}
          target="_blank"
          rel="noopener noreferrer"
          className="block px-5 py-2.5 border-t border-ramp-border text-center
                     text-2xs font-medium text-ramp-blue hover:bg-ramp-blue-light transition-colors"
        >
          Search on Google Flights <ExternalLink size={10} className="inline ml-1" />
        </a>
      )}
    </div>
  );
}

// ── Hotel Card ────────────────────────────────────────────────

function HotelCard({ item }) {
  const d = item.details || {};
  return (
    <div className="ramp-card overflow-hidden">
      {/* Photo */}
      {item.image_url && (
        <div className="h-44 overflow-hidden">
          <img src={item.image_url} alt={item.title} className="w-full h-full object-cover" />
        </div>
      )}

      <div className="px-5 py-4 space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-ramp-text">{item.title}</p>
            <p className="text-2xs text-ramp-text-secondary flex items-center gap-1 mt-0.5">
              <MapPin size={10} />
              {d.neighborhood}
            </p>
          </div>
          <div className="text-right flex-shrink-0">
            <p className="text-sm font-semibold text-ramp-text">{formatCurrency(item.cost)}</p>
            <p className="text-2xs text-ramp-text-tertiary">
              {formatCurrency(d.price_per_night)}/night · {d.nights}n
            </p>
          </div>
        </div>

        {/* Stars & Rating */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-0.5">
            {Array.from({ length: d.stars || 0 }).map((_, i) => (
              <Star key={i} size={12} className="text-ramp-amber fill-ramp-amber" />
            ))}
          </div>
          <span className="text-2xs font-medium text-ramp-text-secondary">
            {d.guest_rating} rating
          </span>
          {d.cancellation_policy?.includes('Free') && (
            <span className="ramp-badge-green">Free cancellation</span>
          )}
        </div>

        {/* Amenities */}
        {d.amenities && (
          <div className="flex flex-wrap gap-1.5">
            {d.amenities.slice(0, 6).map((a) => (
              <span key={a} className="ramp-badge-neutral">{a}</span>
            ))}
            {d.amenities.length > 6 && (
              <span className="ramp-badge-neutral">+{d.amenities.length - 6} more</span>
            )}
          </div>
        )}

        {/* Dates */}
        <div className="flex items-center gap-2 text-2xs text-ramp-text-tertiary pt-1 border-t border-ramp-border">
          <Calendar size={10} />
          <span>Check-in: {item.date}</span>
          <ArrowRight size={10} />
          <span>Check-out: {item.end_date}</span>
        </div>
      </div>

      {item.booking_url && (
        <a
          href={item.booking_url}
          target="_blank"
          rel="noopener noreferrer"
          className="block px-5 py-2.5 border-t border-ramp-border text-center
                     text-2xs font-medium text-ramp-blue hover:bg-ramp-blue-light transition-colors"
        >
          Search hotels <ExternalLink size={10} className="inline ml-1" />
        </a>
      )}
    </div>
  );
}

// ── Car Rental Card ───────────────────────────────────────────

function CarRentalCard({ item }) {
  const d = item.details || {};
  const company = d.company || {};
  return (
    <div className="ramp-card overflow-hidden">
      {item.image_url && (
        <div className="h-36 overflow-hidden bg-ramp-surface-alt">
          <img src={item.image_url} alt={item.title} className="w-full h-full object-cover" />
        </div>
      )}
      <div className="px-5 py-4 space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-ramp-text">{d.vehicle || item.title}</p>
            <p className="text-2xs text-ramp-text-secondary">{company.name} · {d.car_class}</p>
          </div>
          <div className="text-right">
            <p className="text-sm font-semibold text-ramp-text">{formatCurrency(item.cost)}</p>
            <p className="text-2xs text-ramp-text-tertiary">{formatCurrency(d.price_per_day)}/day · {d.days}d</p>
          </div>
        </div>
        {d.features && (
          <div className="flex flex-wrap gap-1.5">
            {d.features.map((f) => (
              <span key={f} className="ramp-badge-neutral">{f}</span>
            ))}
          </div>
        )}
      </div>
      {item.booking_url && (
        <a
          href={item.booking_url}
          target="_blank"
          rel="noopener noreferrer"
          className="block px-5 py-2.5 border-t border-ramp-border text-center
                     text-2xs font-medium text-ramp-blue hover:bg-ramp-blue-light transition-colors"
        >
          Search on Kayak <ExternalLink size={10} className="inline ml-1" />
        </a>
      )}
    </div>
  );
}

// ── Transit Card ──────────────────────────────────────────────

function TransitCard({ item }) {
  return (
    <div className="ramp-card px-5 py-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-ramp-green-light flex items-center justify-center">
            <Train size={16} className="text-ramp-green" />
          </div>
          <div>
            <p className="text-sm font-semibold text-ramp-text">{item.title}</p>
            <p className="text-2xs text-ramp-text-secondary">{item.subtitle}</p>
          </div>
        </div>
        <p className="text-sm font-semibold text-ramp-text">{formatCurrency(item.cost)}</p>
      </div>
      {item.booking_url && (
        <a
          href={item.booking_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 mt-3 text-2xs font-medium text-ramp-blue hover:underline"
        >
          Learn more <ExternalLink size={10} />
        </a>
      )}
    </div>
  );
}

// ── Activity Card ─────────────────────────────────────────────

function ActivityCard({ item }) {
  return (
    <div className="ramp-card px-5 py-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 rounded-full bg-ramp-surface-alt border border-ramp-border flex items-center justify-center flex-shrink-0">
            <Navigation size={14} className="text-ramp-text-secondary" />
          </div>
          <div>
            <p className="text-sm font-semibold text-ramp-text">{item.title}</p>
            <p className="text-xs text-ramp-text-secondary mt-0.5">{item.subtitle}</p>
          </div>
        </div>
        {item.cost > 0 && (
          <p className="text-sm font-semibold text-ramp-text flex-shrink-0">{formatCurrency(item.cost)}</p>
        )}
      </div>
    </div>
  );
}

// ── Timeline Item Router ──────────────────────────────────────

function TimelineItem({ item, index, isLast }) {
  const cardMap = {
    flight: FlightCard,
    hotel: HotelCard,
    car_rental: CarRentalCard,
    transit: TransitCard,
    activity: ActivityCard,
  };
  const Card = cardMap[item.type] || ActivityCard;

  return (
    <div className="relative flex gap-4 animate-slide-up" style={{ animationDelay: `${index * 80}ms` }}>
      {/* Timeline dot + connector */}
      <div className="flex flex-col items-center flex-shrink-0 w-10">
        <div className="w-3 h-3 rounded-full bg-ramp-accent border-2 border-ramp-bg z-10 mt-1" />
        {!isLast && <div className="flex-1 w-px bg-ramp-border mt-1" />}
      </div>

      {/* Card */}
      <div className="flex-1 pb-6 min-w-0">
        <div className="flex items-center gap-2 mb-2">
          <TypeBadge type={item.type} />
          <span className="text-2xs text-ramp-text-tertiary">{item.date}</span>
        </div>
        <Card item={item} />
      </div>
    </div>
  );
}

// ── Main Timeline ─────────────────────────────────────────────

export default function ItineraryTimeline({ itinerary }) {
  if (!itinerary) return null;

  const items = itinerary.items || [];
  const totalCost = itinerary.total_cost || items.reduce((sum, i) => sum + (i.cost || 0), 0);

  return (
    <div className="animate-slide-up">
      {/* Trip header */}
      <div className="ramp-card-elevated px-6 py-5 mb-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold text-ramp-text">{itinerary.trip_title}</h2>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-1.5 text-xs text-ramp-text-secondary">
              {itinerary.destinations?.length > 0 && (
                <span className="flex items-center gap-1">
                  <MapPin size={12} />
                  {itinerary.destinations.join(' → ')}
                </span>
              )}
              <span className="flex items-center gap-1">
                <Calendar size={12} />
                {itinerary.start_date} — {itinerary.end_date}
              </span>
              {itinerary.travelers && (
                <span className="flex items-center gap-1">
                  <Users size={12} />
                  {itinerary.travelers} traveler{itinerary.travelers > 1 ? 's' : ''}
                </span>
              )}
            </div>
          </div>
          <div className="flex-shrink-0 text-right">
            <p className="text-2xs text-ramp-text-tertiary font-medium uppercase tracking-wider">Total Cost</p>
            <p className="text-xl font-bold text-ramp-text mt-0.5">{formatCurrency(totalCost)}</p>
          </div>
        </div>
      </div>

      {/* Timeline */}
      <div className="space-y-0">
        {items.map((item, idx) => (
          <TimelineItem
            key={`${item.type}-${idx}`}
            item={item}
            index={idx}
            isLast={idx === items.length - 1}
          />
        ))}
      </div>

      {/* Cost summary footer */}
      <div className="ramp-card-elevated mt-4 px-6 py-5">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-medium text-ramp-text-secondary uppercase tracking-wider">Trip Total</p>
            <p className="text-xs text-ramp-text-tertiary mt-0.5">
              {items.filter(i => i.type === 'flight').length} flights · {' '}
              {items.filter(i => i.type === 'hotel').length} hotels · {' '}
              {items.filter(i => ['car_rental', 'transit'].includes(i.type)).length} transport
            </p>
          </div>
          <div className="text-right">
            <p className="text-2xl font-bold text-ramp-text">{formatCurrency(totalCost)}</p>
          </div>
        </div>

        {/* Item breakdown */}
        <div className="mt-4 pt-4 border-t border-ramp-border space-y-2">
          {items.filter(i => i.cost > 0).map((item, idx) => (
            <div key={idx} className="flex items-center justify-between text-xs">
              <span className="text-ramp-text-secondary truncate max-w-[70%]">{item.title}</span>
              <span className="font-medium text-ramp-text">{formatCurrency(item.cost)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
