import React, { useState } from 'react';
import {
  Plane, Hotel, Train, MapPin, ExternalLink, Clock,
  ChevronDown, ChevronUp, Star,
  Users, Calendar, ArrowRight, Navigation, RotateCcw
} from 'lucide-react';

// ── Utilities ─────────────────────────────────────────────────

function formatDuration(minutes) {
  if (!minutes) return '';
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return h > 0 ? `${h}h ${m > 0 ? m + 'm' : ''}` : `${m}m`;
}

function getCurrencyMeta(source = {}) {
  const currencyCode = source.currency_code || source.currencyCode || 'USD';
  const currencySymbol = source.currency_symbol || source.currencySymbol || currencyCode;
  return { currencyCode, currencySymbol };
}

function getItemCurrency(item) {
  return getCurrencyMeta({ ...(item?.details || {}), ...(item || {}) });
}

function formatCurrency(amount, source = {}) {
  if (!amount && amount !== 0) return '$0';

  const { currencyCode, currencySymbol } = getCurrencyMeta(source);
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currencyCode,
      maximumFractionDigits: 0,
    }).format(amount);
  } catch {
    return `${currencySymbol} ${amount}`;
  }
}

function getItineraryCurrencyState(items) {
  const currencies = [...new Set(
    items
      .filter((item) => item.cost > 0)
      .map((item) => getItemCurrency(item).currencyCode)
  )];

  if (currencies.length === 1) {
    return { mixed: false, currencyCode: currencies[0] };
  }

  return { mixed: currencies.length > 1, currencyCode: currencies[0] || 'USD' };
}

function formatDate(dateStr) {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr + 'T00:00:00');
    return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
  } catch {
    return dateStr;
  }
}

function formatShortDate(dateStr) {
  if (!dateStr) return '';
  try {
    // Handle both "2026-05-15" and "2026-05-15 06:30" formats
    const datePart = dateStr.split(' ')[0];
    const d = new Date(datePart + 'T00:00:00');
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch {
    return dateStr;
  }
}

function formatTime(dateTimeStr) {
  if (!dateTimeStr) return '';
  // Extract just the time part from "2026-05-15 06:30"
  const parts = dateTimeStr.split(' ');
  return parts.length > 1 ? parts[1] : dateTimeStr;
}

// ── Dot colors per type ───────────────────────────────────────

const DOT_STYLES = {
  flight:     { bg: 'bg-blue-500',   ring: 'ring-blue-100',   icon: Plane,      iconColor: 'text-blue-500' },
  hotel:      { bg: 'bg-amber-500',  ring: 'ring-amber-100',  icon: Hotel,      iconColor: 'text-amber-500' },
  transit:    { bg: 'bg-violet-500', ring: 'ring-violet-100', icon: Train,      iconColor: 'text-violet-500' },
  activity:   { bg: 'bg-gray-400',   ring: 'ring-gray-100',   icon: Navigation, iconColor: 'text-gray-500' },
};

// ── Flight Leg Route Visual ───────────────────────────────────

function FlightLegRouteVisual({ segments, layovers, isNonstop, durationMinutes }) {
  if (!segments || segments.length === 0) return null;

  const originCode = segments[0]?.origin || '—';
  const destCode = segments[segments.length - 1]?.destination || '—';
  const depTime = formatTime(segments[0]?.departure_time);
  const arrTime = formatTime(segments[segments.length - 1]?.arrival_time);

  return (
    <div className="flex items-center gap-2">
      <div className="text-center min-w-[44px]">
        <p className="text-base font-bold font-mono text-ramp-text leading-none">{originCode}</p>
        <p className="text-[10px] text-ramp-text-tertiary mt-0.5">{depTime}</p>
      </div>

      <div className="flex-1 relative flex items-center px-2">
        <div className="w-full flex items-center">
          <div className="w-2 h-2 rounded-full bg-blue-400 flex-shrink-0" />
          <div className="flex-1 h-px bg-ramp-border relative">
            {!isNonstop && layovers && layovers.length > 0 && layovers.map((_, i) => (
              <div
                key={i}
                className="absolute top-1/2 -translate-y-1/2 w-1.5 h-1.5 rounded-full bg-amber-400 border border-white"
                style={{ left: `${((i + 1) / (layovers.length + 1)) * 100}%` }}
              />
            ))}
          </div>
          <div className="w-2 h-2 rounded-full bg-blue-600 flex-shrink-0" />
        </div>
        <div className="absolute -bottom-4 left-1/2 -translate-x-1/2 whitespace-nowrap">
          {isNonstop ? (
            <span className="text-[10px] font-medium text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full">
              Nonstop · {formatDuration(durationMinutes)}
            </span>
          ) : (
            <span className="text-[10px] font-medium text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full">
              {layovers?.length || 0} stop{(layovers?.length || 0) > 1 ? 's' : ''} · {formatDuration(durationMinutes)}
            </span>
          )}
        </div>
      </div>

      <div className="text-center min-w-[44px]">
        <p className="text-base font-bold font-mono text-ramp-text leading-none">{destCode}</p>
        <p className="text-[10px] text-ramp-text-tertiary mt-0.5">{arrTime}</p>
      </div>
    </div>
  );
}

// ── Flight Leg Expanded Details ───────────────────────────────

function FlightLegDetails({ segments, layovers }) {
  if (!segments || segments.length === 0) return null;

  return (
    <div className="space-y-0">
      {segments.map((seg, idx) => (
        <React.Fragment key={idx}>
          <div className="flex items-start gap-3 py-2">
            <div className="mt-1 flex-shrink-0">
              <div className="w-2.5 h-2.5 rounded-full bg-blue-500 ring-4 ring-blue-50" />
            </div>
            <div className="flex-1 text-xs space-y-1">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-ramp-text">{seg.flight_number}</span>
                <span className="text-ramp-text-tertiary">{seg.aircraft}</span>
              </div>
              <div className="flex items-center gap-2 text-ramp-text-secondary">
                <span className="font-mono font-medium">{seg.origin}</span>
                <span>{formatTime(seg.departure_time)}</span>
                <ArrowRight size={10} className="text-ramp-text-tertiary" />
                <span className="font-mono font-medium">{seg.destination}</span>
                <span>{formatTime(seg.arrival_time)}</span>
              </div>
              <p className="text-ramp-text-tertiary flex items-center gap-1">
                <Clock size={10} />
                {formatDuration(seg.duration_minutes)}
              </p>
            </div>
          </div>

          {idx < segments.length - 1 && layovers && layovers[idx] && (
            <div className="ml-[5px] border-l-2 border-dashed border-amber-300 pl-6 py-3 my-1">
              <div className="bg-amber-50 rounded-lg px-3 py-2">
                <p className="text-xs font-medium text-amber-700">
                  ⏱ Layover in {layovers[idx].city !== '—' ? layovers[idx].city : ''} ({layovers[idx].airport})
                </p>
                <p className="text-[11px] text-amber-600 mt-0.5">
                  {formatDuration(layovers[idx].duration_minutes)}
                  {layovers[idx].airport_name && layovers[idx].airport_name !== layovers[idx].airport
                    ? ` · ${layovers[idx].airport_name}` : ''}
                </p>
              </div>
            </div>
          )}
        </React.Fragment>
      ))}
    </div>
  );
}

// ── Flight Card ───────────────────────────────────────────────

function FlightCard({ item }) {
  const [expanded, setExpanded] = useState(false);
  const d = item.details || {};
  const segments = d.segments || [];
  const layovers = d.layovers || [];
  const airline = d.airline || {};
  const isRoundTrip = d.is_round_trip || d.trip_type === 'round_trip';

  // Round-trip specific data
  const outboundSegments = d.outbound_segments || [];
  const outboundLayovers = d.outbound_layovers || [];
  const outboundNonstop = d.outbound_nonstop ?? false;
  const outboundDuration = d.outbound_duration_minutes || 0;
  const returnSegments = d.return_segments || [];
  const returnLayovers = d.return_layovers || [];
  const returnNonstop = d.return_nonstop ?? false;
  const returnDuration = d.return_duration_minutes || 0;

  // For one-way, use segments directly
  const oneWayNonstop = d.is_nonstop ?? (segments.length <= 1);

  return (
    <div className="group rounded-xl border border-ramp-border bg-ramp-surface overflow-hidden shadow-sm hover:shadow-md transition-shadow duration-200">
      {/* Clickable header area */}
      <a
        href={item.booking_url}
        target="_blank"
        rel="noopener noreferrer"
        className="block"
      >
        {/* Colored top bar */}
        <div className={`h-1.5 ${isRoundTrip
          ? 'bg-gradient-to-r from-blue-400 via-blue-500 to-blue-400'
          : 'bg-gradient-to-r from-blue-400 to-blue-600'}`}
        />

        {/* Main content */}
        <div className="px-5 py-4">
          {/* Title row: airline logo + title + badge + price */}
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              {airline.logo ? (
                <img
                  src={airline.logo}
                  alt={airline.name}
                  className="w-9 h-9 object-contain rounded-lg bg-white p-1 border border-ramp-border flex-shrink-0"
                  onError={(e) => { e.target.style.display = 'none'; }}
                />
              ) : (
                <div className="w-9 h-9 bg-blue-50 rounded-lg flex items-center justify-center flex-shrink-0">
                  <Plane size={16} className="text-blue-500" />
                </div>
              )}
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-semibold text-ramp-text truncate">{item.title}</p>
                  {isRoundTrip && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider rounded-full bg-blue-100 text-blue-700 border border-blue-200 flex-shrink-0">
                      <RotateCcw size={9} />
                      Round Trip
                    </span>
                  )}
                  {!isRoundTrip && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider rounded-full bg-gray-100 text-gray-600 border border-gray-200 flex-shrink-0">
                      One Way
                    </span>
                  )}
                </div>
                <p className="text-xs text-ramp-text-tertiary">
                  {airline.name} · {(d.cabin_class || 'economy').replace('_', ' ')}
                  {d.passengers > 1 ? ` · ${d.passengers} travelers` : ''}
                </p>
              </div>
            </div>
            <div className="text-right flex-shrink-0">
              <p className="text-base font-bold text-ramp-text">{formatCurrency(item.cost, item)}</p>
              {d.passengers > 1 && (
                <p className="text-[10px] text-ramp-text-tertiary">
                  {formatCurrency(Math.round(item.cost / d.passengers), item)}/person
                </p>
              )}
              <ExternalLink size={12} className="text-ramp-text-tertiary ml-auto opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
          </div>

          {/* Route visuals */}
          {isRoundTrip && outboundSegments.length > 0 ? (
            /* ── Round-trip: two leg visuals ── */
            <div className="mt-5 space-y-7">
              {/* Outbound leg */}
              <div>
                <div className="flex items-center gap-1.5 mb-2">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-blue-600 bg-blue-50 px-2 py-0.5 rounded">
                    Outbound
                  </span>
                  {outboundSegments[0]?.departure_time && (
                    <span className="text-[10px] text-ramp-text-tertiary">
                      {formatShortDate(outboundSegments[0].departure_time)}
                    </span>
                  )}
                </div>
                <FlightLegRouteVisual
                  segments={outboundSegments}
                  layovers={outboundLayovers}
                  isNonstop={outboundNonstop}
                  durationMinutes={outboundDuration}
                />
              </div>

              {/* Return leg */}
              {returnSegments.length > 0 && (
                <div>
                  <div className="flex items-center gap-1.5 mb-2">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded">
                      Return
                    </span>
                    {returnSegments[0]?.departure_time && (
                      <span className="text-[10px] text-ramp-text-tertiary">
                        {formatShortDate(returnSegments[0].departure_time)}
                      </span>
                    )}
                  </div>
                  <FlightLegRouteVisual
                    segments={returnSegments}
                    layovers={returnLayovers}
                    isNonstop={returnNonstop}
                    durationMinutes={returnDuration}
                  />
                </div>
              )}
            </div>
          ) : (
            /* ── One-way: single route visual ── */
            <div className="mt-4">
              <FlightLegRouteVisual
                segments={segments}
                layovers={layovers}
                isNonstop={oneWayNonstop}
                durationMinutes={d.total_duration_minutes}
              />
            </div>
          )}
        </div>
      </a>

      {/* Expand for segment details */}
      {segments.length > 0 && (
        <>
          <button
            onClick={() => setExpanded(!expanded)}
            className="w-full px-5 py-2 border-t border-ramp-border bg-ramp-surface-alt
                       flex items-center justify-center gap-1.5 text-xs font-medium text-ramp-text-secondary
                       hover:text-ramp-text transition-colors"
          >
            {expanded ? 'Hide flight details' : 'View flight details'}
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>

          {expanded && (
            <div className="px-5 py-4 border-t border-ramp-border bg-ramp-surface-alt">
              {isRoundTrip && outboundSegments.length > 0 ? (
                /* ── Round-trip expanded: outbound + return sections ── */
                <div className="space-y-4">
                  {/* Outbound section */}
                  <div>
                    <div className="flex items-center gap-2 mb-3">
                      <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-blue-50 border border-blue-100">
                        <Plane size={11} className="text-blue-600" />
                        <span className="text-[11px] font-semibold text-blue-700 uppercase tracking-wider">Outbound</span>
                      </div>
                      <div className="flex-1 h-px bg-ramp-border" />
                      {outboundSegments[0]?.departure_time && (
                        <span className="text-[10px] text-ramp-text-tertiary">
                          {formatShortDate(outboundSegments[0].departure_time)}
                        </span>
                      )}
                    </div>
                    <FlightLegDetails segments={outboundSegments} layovers={outboundLayovers} />
                  </div>

                  {/* Return section */}
                  {returnSegments.length > 0 && (
                    <div>
                      <div className="flex items-center gap-2 mb-3 pt-3 border-t border-ramp-border">
                        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-indigo-50 border border-indigo-100">
                          <Plane size={11} className="text-indigo-600 rotate-180" />
                          <span className="text-[11px] font-semibold text-indigo-700 uppercase tracking-wider">Return</span>
                        </div>
                        <div className="flex-1 h-px bg-ramp-border" />
                        {returnSegments[0]?.departure_time && (
                          <span className="text-[10px] text-ramp-text-tertiary">
                            {formatShortDate(returnSegments[0].departure_time)}
                          </span>
                        )}
                      </div>
                      <FlightLegDetails segments={returnSegments} layovers={returnLayovers} />
                    </div>
                  )}
                </div>
              ) : (
                /* ── One-way expanded: flat segment list ── */
                <FlightLegDetails segments={segments} layovers={layovers} />
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── Hotel Card ────────────────────────────────────────────────

function HotelCard({ item }) {
  const d = item.details || {};
  return (
    <a
      href={item.booking_url}
      target="_blank"
      rel="noopener noreferrer"
      className="group block rounded-xl border border-ramp-border bg-ramp-surface overflow-hidden shadow-sm hover:shadow-md transition-shadow duration-200"
    >
      {/* Photo */}
      {item.image_url && (
        <div className="h-44 overflow-hidden relative">
          <img
            src={item.image_url}
            alt={item.title}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/30 to-transparent" />
          {/* Stars badge */}
          {d.stars > 0 && (
            <div className="absolute top-3 left-3 bg-white/90 backdrop-blur-sm rounded-full px-2 py-1 flex items-center gap-0.5">
              {Array.from({ length: d.stars }).map((_, i) => (
                <Star key={i} size={10} className="text-amber-400 fill-amber-400" />
              ))}
            </div>
          )}
          {/* Price badge */}
          <div className="absolute bottom-3 right-3 bg-white/90 backdrop-blur-sm rounded-lg px-2.5 py-1">
            <p className="text-sm font-bold text-ramp-text">{formatCurrency(item.cost, item)}</p>
          </div>
        </div>
      )}

      <div className="px-5 py-4 space-y-2.5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-ramp-text truncate">{item.title}</p>
            <p className="text-xs text-ramp-text-secondary flex items-center gap-1 mt-0.5">
              <MapPin size={10} className="flex-shrink-0" />
              {d.neighborhood || d.city}
            </p>
          </div>
          {!item.image_url && (
            <p className="text-base font-bold text-ramp-text flex-shrink-0">{formatCurrency(item.cost, item)}</p>
          )}
        </div>

        {/* Rating & price-per-night */}
        <div className="flex items-center gap-3 text-xs text-ramp-text-secondary">
          {d.guest_rating > 0 && (
            <span className="flex items-center gap-1">
              <Star size={11} className="text-amber-400 fill-amber-400" />
              {d.guest_rating}
            </span>
          )}
          <span>{formatCurrency(d.price_per_night, item)}/night</span>
          <span>{d.nights} night{d.nights > 1 ? 's' : ''}</span>
        </div>

        {/* Amenities */}
        {d.amenities && d.amenities.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {d.amenities.slice(0, 4).map((a) => (
              <span key={a} className="text-[10px] px-2 py-0.5 rounded-full bg-ramp-surface-alt text-ramp-text-secondary border border-ramp-border">
                {a}
              </span>
            ))}
            {d.amenities.length > 4 && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-ramp-surface-alt text-ramp-text-tertiary">
                +{d.amenities.length - 4} more
              </span>
            )}
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between pt-1.5 border-t border-ramp-border text-[11px] text-ramp-text-tertiary">
          <div className="flex items-center gap-3">
            {d.cancellation_policy?.toLowerCase().includes('free') && (
              <span className="text-emerald-600 font-medium">✓ Free cancel</span>
            )}
            {!d.cancellation_policy?.toLowerCase().includes('free') && (
              <span>{d.cancellation_policy || 'Check cancellation policy'}</span>
            )}
          </div>
          <ExternalLink size={10} className="opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>

        {/* Dates */}
        {(item.date || item.end_date) && (
          <div className="flex items-center gap-2 text-[11px] text-ramp-text-tertiary">
            <Calendar size={10} />
            <span>{formatDate(item.date)}</span>
            <ArrowRight size={10} />
            <span>{formatDate(item.end_date)}</span>
          </div>
        )}
      </div>
    </a>
  );
}

// ── Transit Card ──────────────────────────────────────────────

function TransitCard({ item }) {
  const Wrapper = item.booking_url ? 'a' : 'div';
  const wrapperProps = item.booking_url
    ? { href: item.booking_url, target: '_blank', rel: 'noopener noreferrer' }
    : {};

  return (
    <Wrapper
      {...wrapperProps}
      className="group block rounded-xl border border-ramp-border bg-ramp-surface px-5 py-4 shadow-sm hover:shadow-md transition-shadow duration-200"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-violet-50 flex items-center justify-center flex-shrink-0">
            <Train size={18} className="text-violet-500" />
          </div>
          <div>
            <p className="text-sm font-semibold text-ramp-text">{item.title}</p>
            <p className="text-xs text-ramp-text-secondary mt-0.5">{item.subtitle}</p>
          </div>
        </div>
        <div className="text-right flex-shrink-0 flex items-center gap-2">
          <p className="text-base font-bold text-ramp-text">{formatCurrency(item.cost, item)}</p>
          <ExternalLink size={12} className="text-ramp-text-tertiary opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
      </div>
    </Wrapper>
  );
}

// ── Activity Card ─────────────────────────────────────────────

function ActivityCard({ item }) {
  const Wrapper = item.booking_url ? 'a' : 'div';
  const wrapperProps = item.booking_url
    ? { href: item.booking_url, target: '_blank', rel: 'noopener noreferrer' }
    : {};

  return (
    <Wrapper
      {...wrapperProps}
      className="group block rounded-xl border border-ramp-border bg-ramp-surface px-5 py-4 shadow-sm hover:shadow-md transition-shadow duration-200"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-gray-50 border border-ramp-border flex items-center justify-center flex-shrink-0">
            <Navigation size={16} className="text-ramp-text-secondary" />
          </div>
          <div>
            <p className="text-sm font-semibold text-ramp-text">{item.title}</p>
            <p className="text-xs text-ramp-text-secondary mt-0.5">{item.subtitle}</p>
          </div>
        </div>
        {item.cost > 0 && (
          <p className="text-base font-bold text-ramp-text flex-shrink-0">{formatCurrency(item.cost, item)}</p>
        )}
      </div>
    </Wrapper>
  );
}

// ── Timeline Dot ──────────────────────────────────────────────

function TimelineDot({ type }) {
  const style = DOT_STYLES[type] || DOT_STYLES.activity;
  const Icon = style.icon;
  return (
    <div className={`w-9 h-9 rounded-full flex items-center justify-center ring-4 ${style.ring} ${style.bg} z-10 flex-shrink-0`}>
      <Icon size={15} className="text-white" strokeWidth={2.5} />
    </div>
  );
}

// ── Timeline Item Router ──────────────────────────────────────

function TimelineItem({ item, index, isLast, runningCost, mixedCurrencies }) {
  const cardMap = {
    flight: FlightCard,
    hotel: HotelCard,
    transit: TransitCard,
    activity: ActivityCard,
  };
  const Card = cardMap[item.type] || ActivityCard;

  return (
    <div
      className="relative flex gap-5 animate-slide-up"
      style={{ animationDelay: `${index * 60}ms` }}
    >
      {/* Timeline track: dot + connector line */}
      <div className="flex flex-col items-center flex-shrink-0" style={{ width: '36px' }}>
        <TimelineDot type={item.type} />
        {!isLast && (
          <div className="flex-1 w-0.5 bg-gradient-to-b from-ramp-border to-ramp-border/30 mt-2 mb-0" />
        )}
      </div>

      {/* Card + date label */}
      <div className="flex-1 pb-8 min-w-0">
        {/* Date & running cost */}
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium text-ramp-text-secondary">{formatDate(item.date)}</span>
          <span className="text-[10px] text-ramp-text-tertiary">
            {mixedCurrencies ?
              'Running total unavailable' : `Running: ${formatCurrency(runningCost, item)}`}
          </span>
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
  const itineraryCurrency = getItineraryCurrencyState(items);

  // Calculate running costs
  let running = 0;
  const runningCosts = items.map((item) => {
    running += (item.cost || 0);
    return running;
  });

  return (
    <div className="animate-slide-up">
      {/* ── Trip Header ──────────────────────────────── */}
      <div className="relative rounded-2xl border border-ramp-border bg-gradient-to-br from-ramp-surface to-ramp-surface-alt overflow-hidden shadow-md mb-8">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-amber-500/5" />
        <div className="relative px-6 py-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-xl font-bold text-ramp-text">{itinerary.trip_title}</h2>
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-xs text-ramp-text-secondary">
                {itinerary.destinations?.length > 0 && (
                  <span className="flex items-center gap-1.5">
                    <MapPin size={13} className="text-ramp-text-tertiary" />
                    {itinerary.destinations.join(' → ')}
                  </span>
                )}
                <span className="flex items-center gap-1.5">
                  <Calendar size={13} className="text-ramp-text-tertiary" />
                  {formatDate(itinerary.start_date)} — {formatDate(itinerary.end_date)}
                </span>
                {itinerary.travelers && (
                  <span className="flex items-center gap-1.5">
                    <Users size={13} className="text-ramp-text-tertiary" />
                    {itinerary.travelers} traveler{itinerary.travelers > 1 ? 's' : ''}
                  </span>
                )}
              </div>
            </div>
            <div className="flex-shrink-0 text-right bg-white/70 backdrop-blur-sm rounded-xl px-4 py-3 border border-ramp-border">
              <p className="text-[10px] text-ramp-text-tertiary font-medium uppercase tracking-wider">Total</p>
              <p className="text-2xl font-bold text-ramp-text">
                {itineraryCurrency.mixed ? 'Mixed currencies' : formatCurrency(totalCost, { currency_code: itineraryCurrency.currencyCode })}
              </p>
              <p className="text-[10px] text-ramp-text-tertiary mt-0.5">
                {items.filter(i => i.type === 'flight').length} flight{items.filter(i => i.type === 'flight').length !== 1 ? 's' : ''}
                {items.filter(i => i.type === 'hotel').length > 0 && ` · ${items.filter(i => i.type === 'hotel').length} hotel${items.filter(i => i.type === 'hotel').length !== 1 ? 's' : ''}`}
                {items.filter(i => i.type === 'transit').length > 0 && ` · ${items.filter(i => i.type === 'transit').length} transit`}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* ── Timeline ─────────────────────────────────── */}
      <div className="space-y-0 pl-1">
        {items.map((item, idx) => (
          <TimelineItem
            key={`${item.type}-${idx}`}
            item={item}
            index={idx}
            isLast={idx === items.length - 1}
            runningCost={runningCosts[idx]}
            mixedCurrencies={itineraryCurrency.mixed}
          />
        ))}
      </div>

      {/* ── Cost Summary Footer ──────────────────────── */}
      <div className="rounded-2xl border border-ramp-border bg-ramp-surface overflow-hidden shadow-md mt-4">
        <div className="px-6 py-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-ramp-text-secondary uppercase tracking-wider">
                Trip Total
              </p>
              <p className="text-xs text-ramp-text-tertiary mt-0.5">
                {items.filter(i => i.type === 'flight').length} flight{items.filter(i => i.type === 'flight').length !== 1 ? 's' : ''} ·{' '}
                {items.filter(i => i.type === 'hotel').length} hotel{items.filter(i => i.type === 'hotel').length !== 1 ? 's' : ''} ·{' '}
                {items.filter(i => i.type === 'transit').length} transit
              </p>
            </div>
            <div className="text-right">
              <p className="text-3xl font-bold text-ramp-text">
                {itineraryCurrency.mixed ?
                  'Mixed currencies' : formatCurrency(totalCost, { currency_code: itineraryCurrency.currencyCode })}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}