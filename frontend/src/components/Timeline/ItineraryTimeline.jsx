import React, { useState } from 'react';
import {
  Plane, Hotel, Train, Navigation, MapPin, Calendar, Users,
  ExternalLink, ChevronDown, ChevronUp, Clock, Star, RotateCcw,
} from 'lucide-react';

// ── Formatters ────────────────────────────────────────────────

function formatCurrency(amount, item = {}) {
  if (!amount && amount !== 0) return '—';
  const code = item.currency_code || 'USD';
  const symbol = item.currency_symbol || '$';
  const formatted = Math.round(amount).toLocaleString('en-US');
  return code === 'USD' ? `$${formatted}` : `${symbol}${formatted}`;
}

function formatDate(dateStr) {
  if (!dateStr) return '—';
  try {
    const d = new Date(dateStr + (dateStr.includes('T') ? '' : 'T00:00:00'));
    return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
  } catch { return dateStr; }
}

function formatShortDate(dateStr) {
  if (!dateStr) return '';
  try {
    const match = dateStr.match(/(\d{4})-(\d{2})-(\d{2})/);
    if (match) {
      const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
      return `${months[parseInt(match[2], 10) - 1]} ${parseInt(match[3], 10)}`;
    }
    return dateStr;
  } catch { return ''; }
}

function formatTime(dateTimeStr) {
  if (!dateTimeStr) return '—';
  try {
    const match = dateTimeStr.match(/(\d{4}-\d{2}-\d{2})[T ](\d{2}):(\d{2})/);
    if (match) {
      let hours = parseInt(match[2], 10);
      const minutes = match[3];
      const ampm = hours >= 12 ? 'PM' : 'AM';
      hours = hours % 12 || 12;
      return `${hours}:${minutes} ${ampm}`;
    }
    if (/^\d{2}:\d{2}$/.test(dateTimeStr)) {
      let [h, m] = dateTimeStr.split(':').map(Number);
      const ampm = h >= 12 ? 'PM' : 'AM';
      h = h % 12 || 12;
      return `${h}:${String(m).padStart(2, '0')} ${ampm}`;
    }
    return dateTimeStr;
  } catch { return dateTimeStr; }
}

function formatDuration(minutes) {
  if (!minutes) return '';
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return h > 0 ? `${h}h ${m > 0 ? `${m}m` : ''}`.trim() : `${m}m`;
}

function getTotalCostUSD(items, itineraryTotal) {
  if (itineraryTotal && itineraryTotal > 0) return itineraryTotal;
  return items.reduce((sum, i) => sum + (i.cost || 0), 0);
}

// ── Icon map ──────────────────────────────────────────────────

const TYPE_ICONS = {
  flight:   Plane,
  hotel:    Hotel,
  transit:  Train,
  activity: Navigation,
};

// ── Shared card wrapper ───────────────────────────────────────

function CardWrapper({ href, children, className = '' }) {
  const base = `group block bg-ramp-surface border border-ramp-border shadow-ramp
                hover:shadow-ramp-md hover:border-ramp-border-strong transition-all duration-150 ${className}`;
  if (href) return <a href={href} target="_blank" rel="noopener noreferrer" className={base}>{children}</a>;
  return <div className={base}>{children}</div>;
}

function TypeLabel({ type }) {
  const labels = { flight: 'Flight', hotel: 'Hotel', transit: 'Transit', activity: 'Activity' };
  return (
    <span className="text-[10px] font-semibold uppercase tracking-widest text-ramp-text-tertiary">
      {labels[type] || type}
    </span>
  );
}

// ── Flight Leg Route Visual ───────────────────────────────────

function FlightLegRouteVisual({ segments, layovers, isNonstop, durationMinutes }) {
  if (!segments || segments.length === 0) return null;
  const originCode = segments[0]?.origin || '—';
  const destCode = segments[segments.length - 1]?.destination || '—';
  const depTime = formatTime(segments[0]?.departure_time);
  const arrTime = formatTime(segments[segments.length - 1]?.arrival_time);

  return (
    <div className="flex items-center gap-3">
      <div className="text-center">
        <p className="text-lg font-bold text-ramp-text leading-none tracking-tight">{originCode}</p>
        <p className="text-[10px] text-ramp-text-tertiary mt-0.5">{depTime}</p>
      </div>

      <div className="flex-1 flex flex-col items-center gap-1 min-w-0">
        <div className="flex items-center gap-1.5 w-full">
          <div className="flex-1 h-px bg-ramp-border" />
          {isNonstop ? (
            <span className="text-[9px] font-semibold uppercase tracking-wider text-ramp-green px-1.5 py-0.5 border border-ramp-green/30 bg-ramp-green/5 flex-shrink-0">
              Nonstop
            </span>
          ) : (
            <span className="text-[9px] font-semibold uppercase tracking-wider text-ramp-text-tertiary px-1.5 py-0.5 border border-ramp-border bg-ramp-surface-alt flex-shrink-0">
              {layovers?.length || segments.length - 1} stop{(layovers?.length || segments.length - 1) !== 1 ? 's' : ''}
            </span>
          )}
          <div className="flex-1 h-px bg-ramp-border" />
        </div>
        {durationMinutes > 0 && (
          <p className="text-[10px] text-ramp-text-tertiary flex items-center gap-1">
            <Clock size={9} />{formatDuration(durationMinutes)}
          </p>
        )}
      </div>

      <div className="text-center">
        <p className="text-lg font-bold text-ramp-text leading-none tracking-tight">{destCode}</p>
        <p className="text-[10px] text-ramp-text-tertiary mt-0.5">{arrTime}</p>
      </div>
    </div>
  );
}

// ── Flight Leg Detail Rows ────────────────────────────────────

function FlightLegDetails({ segments, layovers }) {
  if (!segments || segments.length === 0) return null;
  return (
    <div className="space-y-0">
      {segments.map((seg, idx) => (
        <React.Fragment key={idx}>
          <div className="flex items-start gap-3 py-2">
            <div className="flex flex-col items-center pt-1 flex-shrink-0">
              <div className="w-1.5 h-1.5 rounded-full bg-ramp-text-tertiary" />
              {idx < segments.length - 1 && <div className="w-px h-8 bg-ramp-border mt-1" />}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-xs font-semibold text-ramp-text">{seg.origin} → {seg.destination}</p>
                  <p className="text-[10px] text-ramp-text-tertiary mt-0.5">
                    {formatTime(seg.departure_time)} → {formatTime(seg.arrival_time)}
                    {seg.duration_minutes ? ` · ${formatDuration(seg.duration_minutes)}` : ''}
                  </p>
                </div>
                {seg.flight_number && (
                  <span className="text-[10px] text-ramp-text-tertiary border border-ramp-border px-1.5 py-0.5 flex-shrink-0">
                    {seg.flight_number}
                  </span>
                )}
              </div>
              {seg.aircraft && <p className="text-[10px] text-ramp-text-tertiary mt-0.5">{seg.aircraft}</p>}
            </div>
          </div>
          {layovers?.[idx] && (
            <div className="ml-5 border-l border-dashed border-ramp-border-strong pl-4 py-2 my-1">
              <p className="text-[11px] text-ramp-text-secondary font-medium">
                Layover · {layovers[idx].city !== '—' ? layovers[idx].city : ''} ({layovers[idx].airport})
              </p>
              <p className="text-[10px] text-ramp-text-tertiary mt-0.5">
                {formatDuration(layovers[idx].duration_minutes)}
                {layovers[idx].airport_name && layovers[idx].airport_name !== layovers[idx].airport
                  ? ` · ${layovers[idx].airport_name}` : ''}
              </p>
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

  const outboundSegments = d.outbound_segments || [];
  const outboundLayovers = d.outbound_layovers || [];
  const outboundNonstop = d.outbound_nonstop ?? false;
  const outboundDuration = d.outbound_duration_minutes || 0;
  const returnSegments = d.return_segments || [];
  const returnLayovers = d.return_layovers || [];
  const returnNonstop = d.return_nonstop ?? false;
  const returnDuration = d.return_duration_minutes || 0;
  const oneWayNonstop = d.is_nonstop ?? (segments.length <= 1);
  const hasSegments = isRoundTrip ? outboundSegments.length > 0 : segments.length > 0;

  return (
    <div className="bg-ramp-surface border border-ramp-border shadow-ramp hover:shadow-ramp-md hover:border-ramp-border-strong transition-all duration-150 overflow-hidden">
      <div className="h-0.5 bg-ramp-yellow" />
      <a href={item.booking_url} target="_blank" rel="noopener noreferrer" className="block px-5 py-4">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div className="flex items-center gap-3 min-w-0">
            {airline.logo
              ? <img src={airline.logo} alt={airline.name} className="w-7 h-7 object-contain flex-shrink-0" onError={e => e.target.style.display='none'} />
              : <div className="w-7 h-7 bg-ramp-surface-alt border border-ramp-border flex items-center justify-center flex-shrink-0">
                  <Plane size={13} className="text-ramp-text-secondary" />
                </div>
            }
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <p className="text-sm font-semibold text-ramp-text">{item.title}</p>
                {isRoundTrip
                  ? <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider border border-ramp-border bg-ramp-surface-alt text-ramp-text-secondary flex-shrink-0">
                      <RotateCcw size={9} /> Round Trip
                    </span>
                  : <span className="inline-flex items-center px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider border border-ramp-border bg-ramp-surface-alt text-ramp-text-secondary flex-shrink-0">
                      One Way
                    </span>
                }
              </div>
              <p className="text-xs text-ramp-text-tertiary mt-0.5">
                {airline.name}{d.cabin_class ? ` · ${d.cabin_class.replace('_', ' ')}` : ''}
                {d.passengers > 1 ? ` · ${d.passengers} travelers` : ''}
              </p>
            </div>
          </div>
          <div className="text-right flex-shrink-0">
            <p className="text-base font-bold text-ramp-text">{formatCurrency(item.cost, item)}</p>
            {d.passengers > 1 && <p className="text-[10px] text-ramp-text-tertiary">{formatCurrency(Math.round(item.cost / d.passengers), item)}/person</p>}
          </div>
        </div>

        {isRoundTrip && outboundSegments.length > 0 ? (
          <div className="space-y-4">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-widest text-ramp-text-tertiary mb-2">Outbound</p>
              <FlightLegRouteVisual segments={outboundSegments} layovers={outboundLayovers} isNonstop={outboundNonstop} durationMinutes={outboundDuration} />
            </div>
            {returnSegments.length > 0 && (
              <div className="pt-3 border-t border-ramp-border">
                <p className="text-[10px] font-semibold uppercase tracking-widest text-ramp-text-tertiary mb-2">Return</p>
                <FlightLegRouteVisual segments={returnSegments} layovers={returnLayovers} isNonstop={returnNonstop} durationMinutes={returnDuration} />
              </div>
            )}
          </div>
        ) : (
          <FlightLegRouteVisual segments={segments} layovers={layovers} isNonstop={oneWayNonstop} durationMinutes={d.total_duration_minutes} />
        )}
      </a>

      {hasSegments && (
        <>
          <button
            onClick={() => setExpanded(!expanded)}
            className="w-full px-5 py-2 border-t border-ramp-border bg-ramp-surface-alt
                       flex items-center justify-center gap-1.5 text-[11px] font-medium text-ramp-text-secondary
                       hover:text-ramp-text hover:bg-ramp-border/30 transition-colors"
          >
            {expanded ? 'Hide details' : 'View flight details'}
            {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </button>
          {expanded && (
            <div className="px-5 py-4 border-t border-ramp-border bg-ramp-surface-alt">
              {isRoundTrip && outboundSegments.length > 0 ? (
                <div className="space-y-4">
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-widest text-ramp-text-tertiary mb-2">Outbound</p>
                    <FlightLegDetails segments={outboundSegments} layovers={outboundLayovers} />
                  </div>
                  {returnSegments.length > 0 && (
                    <div className="pt-3 border-t border-ramp-border">
                      <p className="text-[10px] font-semibold uppercase tracking-widest text-ramp-text-tertiary mb-2">Return</p>
                      <FlightLegDetails segments={returnSegments} layovers={returnLayovers} />
                    </div>
                  )}
                </div>
              ) : (
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
  const fallbackImage = "https://ontariosings.com/wp-content/uploads/2023/07/hotel-placeholder.jpg";
  const [imgError, setImgError] = useState(false);
  const imgSrc = !imgError && item.image_url ? item.image_url : fallbackImage;

  return (
    <a
      href={item.booking_url} target="_blank" rel="noopener noreferrer"
      className="group block bg-ramp-surface border border-ramp-border shadow-ramp
                 hover:shadow-ramp-md hover:border-ramp-border-strong transition-all duration-150 overflow-hidden"
    >
      <div className="h-0.5 bg-ramp-yellow" />
      <div className="flex gap-0">
        <div className="w-32 flex-shrink-0 bg-ramp-surface-alt overflow-hidden">
          <img src={imgSrc} alt={item.title} className="w-full h-full object-cover"
               onError={() => setImgError(true)} style={{ minHeight: '120px' }} />
        </div>
        <div className="flex-1 px-4 py-4 min-w-0 space-y-2">
          <div className="flex items-start justify-between gap-3">
            <div>
              <TypeLabel type="hotel" />
              <p className="text-sm font-semibold text-ramp-text mt-0.5">{item.title}</p>
              <p className="text-xs text-ramp-text-secondary">{item.subtitle}</p>
            </div>
            <div className="text-right flex-shrink-0">
              <p className="text-base font-bold text-ramp-text">{formatCurrency(item.cost, item)}</p>
              {d.nights && <p className="text-[10px] text-ramp-text-tertiary">{d.nights} night{d.nights !== 1 ? 's' : ''}</p>}
              {d.price_per_night && <p className="text-[10px] text-ramp-text-tertiary">{formatCurrency(d.price_per_night, item)}/night</p>}
            </div>
          </div>
          {(d.stars > 0 || d.guest_rating > 0) && (
            <div className="flex items-center gap-3">
              {d.stars > 0 && (
                <div className="flex items-center gap-0.5">
                  {[...Array(Math.min(Math.floor(d.stars), 5))].map((_, i) => (
                    <Star key={i} size={9} className="fill-ramp-yellow text-ramp-yellow" />
                  ))}
                </div>
              )}
              {d.guest_rating > 0 && (
                <span className="text-[10px] text-ramp-text-secondary">{d.guest_rating.toFixed(1)} guest rating</span>
              )}
            </div>
          )}
          {d.amenities?.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {d.amenities.slice(0, 4).map((a, i) => (
                <span key={i} className="text-[9px] px-1.5 py-0.5 border border-ramp-border text-ramp-text-tertiary bg-ramp-surface-alt">{a}</span>
              ))}
            </div>
          )}
          <div className="flex items-center gap-1">
            {d.cancellation_policy?.toLowerCase().includes('free')
              ? <span className="text-[10px] text-ramp-green font-medium">✓ Free cancellation</span>
              : <span className="text-[10px] text-ramp-text-tertiary">{d.cancellation_policy || 'Check cancellation policy'}</span>
            }
            <ExternalLink size={10} className="text-ramp-text-tertiary opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
        </div>
      </div>
    </a>
  );
}

// ── Transit Card ──────────────────────────────────────────────

function TransitCard({ item }) {
  const d = item.details || {};

  // Quantity breakdown — shown when more than 1 pass is needed
  const quantity = d.quantity || 1;
  const pricePerPass = d.price_per_pass;
  const passDurationDays = d.pass_duration_days;
  const daysInCity = d.days_in_city;
  const passLabel = d.pass_label || item.title;

  // Build the per-pass breakdown string e.g. "$34/pass"
  const perPassStr = pricePerPass > 0
    ? `${formatCurrency(pricePerPass, item)}/pass`
    : null;

  // Days coverage note e.g. "covers 14 of 12 days" or "covers 12 days"
  const coverageStr = passDurationDays && daysInCity
    ? `covers ${daysInCity} day${daysInCity !== 1 ? 's' : ''}`
    : null;

  return (
    <CardWrapper href={item.booking_url}>
      <div className="h-0.5 bg-ramp-yellow" />
      <div className="px-5 py-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-8 h-8 bg-ramp-surface-alt border border-ramp-border flex items-center justify-center flex-shrink-0">
            <Train size={14} className="text-ramp-text-secondary" />
          </div>
          <div className="min-w-0">
            <TypeLabel type="transit" />
            {/* Show the quantity label if > 1 pass, otherwise just the pass name */}
            <p className="text-sm font-semibold text-ramp-text mt-0.5">{passLabel}</p>
            <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 mt-0.5">
              {item.subtitle && (
                <p className="text-xs text-ramp-text-secondary">{item.subtitle}</p>
              )}
              {quantity > 1 && perPassStr && (
                <p className="text-[10px] text-ramp-text-tertiary">
                  {perPassStr}
                </p>
              )}
              {coverageStr && (
                <p className="text-[10px] text-ramp-text-tertiary">{coverageStr}</p>
              )}
            </div>
          </div>
        </div>
        <div className="text-right flex-shrink-0 flex items-center gap-2">
          <div className="text-right">
            <p className="text-base font-bold text-ramp-text">{formatCurrency(item.cost, item)}</p>
            {quantity > 1 && (
              <p className="text-[10px] text-ramp-text-tertiary">{quantity} passes</p>
            )}
          </div>
          <ExternalLink size={11} className="text-ramp-text-tertiary opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
      </div>
    </CardWrapper>
  );
}

// ── Activity Card ─────────────────────────────────────────────

function ActivityCard({ item }) {
  return (
    <CardWrapper href={item.booking_url}>
      <div className="px-5 py-4 flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 bg-ramp-surface-alt border border-ramp-border flex items-center justify-center flex-shrink-0">
            <Navigation size={14} className="text-ramp-text-secondary" />
          </div>
          <div>
            <TypeLabel type="activity" />
            <p className="text-sm font-semibold text-ramp-text mt-0.5">{item.title}</p>
            <p className="text-xs text-ramp-text-secondary">{item.subtitle}</p>
          </div>
        </div>
        {item.cost > 0 && (
          <p className="text-base font-bold text-ramp-text flex-shrink-0">{formatCurrency(item.cost, item)}</p>
        )}
      </div>
    </CardWrapper>
  );
}

// ── Timeline Dot ──────────────────────────────────────────────

function TimelineDot({ type }) {
  const Icon = TYPE_ICONS[type] || Navigation;
  return (
    <div className="w-8 h-8 bg-ramp-text flex items-center justify-center flex-shrink-0 z-10">
      <Icon size={14} className="text-white" strokeWidth={2} />
    </div>
  );
}

// ── Timeline Item ─────────────────────────────────────────────

function TimelineItem({ item, index, isLast, runningCost }) {
  const cardMap = { flight: FlightCard, hotel: HotelCard, transit: TransitCard, activity: ActivityCard };
  const Card = cardMap[item.type] || ActivityCard;

  return (
    <div className="relative flex gap-4 animate-slide-up" style={{ animationDelay: `${index * 60}ms` }}>
      <div className="flex flex-col items-center flex-shrink-0">
        <TimelineDot type={item.type} />
        {!isLast && <div className="flex-1 w-px bg-ramp-border mt-1 mb-0 min-h-[24px]" />}
      </div>
      <div className="flex-1 pb-6 min-w-0">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium text-ramp-text-secondary">{formatDate(item.date)}</span>
          <span className="text-[10px] text-ramp-text-tertiary">
            {runningCost > 0 ? `Running: ${formatCurrency(runningCost, { currency_code: 'USD', currency_symbol: '$' })}` : ''}
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
  const totalCost = getTotalCostUSD(items, itinerary.total_cost);

  let running = 0;
  const runningCosts = items.map((item) => {
    running += (item.cost || 0);
    return running;
  });

  const flightCount = items.filter(i => i.type === 'flight').length;
  const hotelCount  = items.filter(i => i.type === 'hotel').length;

  return (
    <div className="animate-slide-up">
      {/* ── Trip Header ── */}
      <div className="bg-ramp-surface border border-ramp-border shadow-ramp mb-6 overflow-hidden">
        <div className="h-1 bg-ramp-yellow" />
        <div className="px-6 py-5 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold text-ramp-text">{itinerary.trip_title}</h2>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-xs text-ramp-text-secondary">
              {itinerary.destinations?.length > 0 && (
                <span className="flex items-center gap-1.5">
                  <MapPin size={12} className="text-ramp-text-tertiary" />
                  {itinerary.destinations.join(' → ')}
                </span>
              )}
              <span className="flex items-center gap-1.5">
                <Calendar size={12} className="text-ramp-text-tertiary" />
                {formatDate(itinerary.start_date)} — {formatDate(itinerary.end_date)}
              </span>
              {itinerary.travelers && (
                <span className="flex items-center gap-1.5">
                  <Users size={12} className="text-ramp-text-tertiary" />
                  {itinerary.travelers} traveler{itinerary.travelers > 1 ? 's' : ''}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 mt-3">
              {flightCount > 0 && (
                <span className="text-[10px] px-2 py-0.5 border border-ramp-border text-ramp-text-secondary bg-ramp-surface-alt">
                  {flightCount} flight{flightCount !== 1 ? 's' : ''}
                </span>
              )}
              {hotelCount > 0 && (
                <span className="text-[10px] px-2 py-0.5 border border-ramp-border text-ramp-text-secondary bg-ramp-surface-alt">
                  {hotelCount} hotel{hotelCount !== 1 ? 's' : ''}
                </span>
              )}
            </div>
          </div>
          <div className="text-right flex-shrink-0">
            <p className="text-2xl font-bold text-ramp-text">
              {formatCurrency(totalCost, { currency_code: 'USD', currency_symbol: '$' })}
            </p>
            <p className="text-xs text-ramp-text-tertiary mt-0.5">estimated total</p>
          </div>
        </div>
      </div>

      {/* ── Timeline Items ── */}
      <div>
        {items.map((item, idx) => (
          <TimelineItem
            key={item.id || idx}
            item={item}
            index={idx}
            isLast={idx === items.length - 1}
            runningCost={runningCosts[idx]}
          />
        ))}
      </div>
    </div>
  );
}