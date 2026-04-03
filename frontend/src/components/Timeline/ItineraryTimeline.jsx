import React, { useState } from 'react';
import {
  Plane, Hotel, Train, Navigation, MapPin, Calendar, Users,
  ChevronDown, ChevronUp, Clock, Star, ExternalLink, Link2Off,
  Utensils, Landmark, TreePine, Moon, Sun, Coffee, Sunset,
} from 'lucide-react';

// ── Formatters ────────────────────────────────────────────────

function formatCurrency(amount, item = {}) {
  if (!amount && amount !== 0) return '';
  const symbol = item.currency_symbol || item.details?.currency_symbol || '$';
  const code   = item.currency_code   || item.details?.currency_code   || 'USD';
  if (code === 'USD' || symbol === '$') {
    return `$${Number(amount).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
  }
  return `${symbol}${Number(amount).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })} ${code}`;
}

function formatDate(dateStr) {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr + 'T12:00:00');
    return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
  } catch { return dateStr; }
}

function formatDateShort(dateStr) {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr + 'T12:00:00');
    return d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });
  } catch { return dateStr; }
}

function formatTime(dateTimeStr) {
  if (!dateTimeStr) return '';
  try {
    if (dateTimeStr.includes('T') || (dateTimeStr.includes('-') && dateTimeStr.length > 10)) {
      const d = new Date(dateTimeStr);
      if (!isNaN(d)) {
        let hours = d.getHours();
        const minutes = String(d.getMinutes()).padStart(2, '0');
        const ampm = hours >= 12 ? 'PM' : 'AM';
        hours = hours % 12 || 12;
        return `${hours}:${minutes} ${ampm}`;
      }
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

// ── Time slot parsing ─────────────────────────────────────────

const TIME_SLOT_MAP = {
  breakfast:        { label: '8:00 AM',  icon: Coffee  },
  morning:          { label: '9:30 AM',  icon: Sun     },
  'late morning':   { label: '11:00 AM', icon: Sun     },
  midday:           { label: '12:00 PM', icon: Sun     },
  lunch:            { label: '12:30 PM', icon: Utensils },
  afternoon:        { label: '2:00 PM',  icon: Sunset  },
  'late afternoon': { label: '4:00 PM',  icon: Sunset  },
  dinner:           { label: '7:00 PM',  icon: Utensils },
  evening:          { label: '7:30 PM',  icon: Moon    },
  night:            { label: '9:30 PM',  icon: Moon    },
  nightlife:        { label: '10:00 PM', icon: Moon    },
};

function parseTimeSlot(subtitle = '') {
  const lower = subtitle.toLowerCase();
  for (const [key, val] of Object.entries(TIME_SLOT_MAP)) {
    if (lower.startsWith(key) || lower.includes(`· ${key}`) || lower.includes(`- ${key}`)) {
      return val;
    }
  }
  // category fallbacks
  if (lower.includes('food') || lower.includes('restaurant') || lower.includes('café') || lower.includes('cafe') || lower.includes('eat')) {
    return TIME_SLOT_MAP['lunch'];
  }
  return null;
}

// ── Category icon map ─────────────────────────────────────────

function getCategoryIcon(category = '') {
  const c = category.toLowerCase();
  if (c.includes('food') || c.includes('restaurant') || c.includes('eat') || c.includes('cafe') || c.includes('dining')) return Utensils;
  if (c.includes('park') || c.includes('garden') || c.includes('nature') || c.includes('beach')) return TreePine;
  if (c.includes('night') || c.includes('bar') || c.includes('club')) return Moon;
  return Landmark;
}

// ── Icon map ──────────────────────────────────────────────────

const TYPE_ICONS = {
  flight:   Plane,
  hotel:    Hotel,
  transit:  Train,
  activity: Navigation,
};

// ── URL validator ────────────────────────────────────────────
// Returns the href only if it looks like a real, navigable http(s) URL.
// Rejects: empty strings, relative paths, Quora/Reddit/forum links,
// and anything that isn't a proper web address.
const JUNK_DOMAINS = [
  'quora.com', 'reddit.com', 'tripadvisor.com', 'yahoo.com',
  'answers.com', 'ask.com', 'wikitravel.org', 'wikivoyage.org',
  'lonelyplanet.com', 'expat.com',
];
function safeHref(url) {
  if (!url || typeof url !== 'string') return null;
  const trimmed = url.trim();
  if (!trimmed.startsWith('http://') && !trimmed.startsWith('https://')) return null;
  try {
    const host = new URL(trimmed).hostname.replace(/^www\./, '');
    if (JUNK_DOMAINS.some(d => host === d || host.endsWith('.' + d))) return null;
  } catch { return null; }
  return trimmed;
}

// ── Shared card wrapper ───────────────────────────────────────

function CardWrapper({ href, children, className = '' }) {
  const base = `group block bg-ramp-surface border border-ramp-border shadow-ramp
                hover:shadow-ramp-md hover:border-ramp-border-strong transition-all duration-150 ${className}`;
  const validHref = safeHref(href);
  if (validHref) return <a href={validHref} target="_blank" rel="noopener noreferrer" className={base}>{children}</a>;
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
            <div className="ml-[3px] border-l border-dashed border-ramp-border-strong pl-[19px] py-2 my-1">
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
  const [logoError, setLogoError] = useState(false);
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
            {airline.logo && !logoError
              ? <img src={airline.logo} alt={airline.name || ''} className="w-7 h-7 object-contain flex-shrink-0" onError={() => setLogoError(true)} />
              : <div className="w-7 h-7 bg-ramp-surface-alt border border-ramp-border flex items-center justify-center flex-shrink-0"><Plane size={12} className="text-ramp-text-secondary" /></div>
            }
            <div className="min-w-0">
              <TypeLabel type="flight" />
              <p className="text-sm font-semibold text-ramp-text mt-0.5 truncate">{item.title}</p>
              {airline.name && <p className="text-xs text-ramp-text-secondary">{airline.name}</p>}
            </div>
          </div>
          <div className="text-right flex-shrink-0">
            <p className="text-base font-bold text-ramp-text">{formatCurrency(item.cost, item)}</p>
            {d.passengers > 1 && <p className="text-[10px] text-ramp-text-tertiary">{d.passengers} passengers</p>}
            {d.cabin_class && <p className="text-[10px] text-ramp-text-tertiary capitalize">{d.cabin_class.replace('_', ' ')}</p>}
          </div>
        </div>
        {isRoundTrip && outboundSegments.length > 0 ? (
          <div className="space-y-3">
            <div>
              <p className="text-[9px] font-semibold uppercase tracking-widest text-ramp-text-tertiary mb-1.5">Outbound</p>
              <FlightLegRouteVisual segments={outboundSegments} layovers={outboundLayovers} isNonstop={outboundNonstop} durationMinutes={outboundDuration} />
            </div>
            {returnSegments.length > 0 && (
              <div className="pt-3 border-t border-ramp-border">
                <p className="text-[9px] font-semibold uppercase tracking-widest text-ramp-text-tertiary mb-1.5">Return · {d.return_date ? formatDate(d.return_date) : ''}</p>
                <FlightLegRouteVisual segments={returnSegments} layovers={returnLayovers} isNonstop={returnNonstop} durationMinutes={returnDuration} />
              </div>
            )}
          </div>
        ) : segments.length > 0 ? (
          <FlightLegRouteVisual segments={segments} layovers={layovers} isNonstop={oneWayNonstop} durationMinutes={d.total_duration_minutes || 0} />
        ) : null}
      </a>
      {hasSegments && (
        <>
          <button
            onClick={() => setExpanded((e) => !e)}
            className="w-full flex items-center justify-center gap-1.5 px-5 py-2.5
                       border-t border-ramp-border text-[11px] font-medium text-ramp-text-secondary
                       hover:bg-ramp-surface-alt transition-colors"
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
  const quantity = d.quantity || 1;
  const pricePerPass = d.price_per_pass;
  const passDurationDays = d.pass_duration_days;
  const daysInCity = d.days_in_city;
  const passLabel = d.pass_label || item.title;

  const perPassStr = pricePerPass > 0 ? `${formatCurrency(pricePerPass, item)}/pass` : null;
  const coverageStr = passDurationDays && daysInCity ? `covers ${daysInCity} day${daysInCity !== 1 ? 's' : ''}` : null;

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
            <p className="text-sm font-semibold text-ramp-text mt-0.5">{passLabel}</p>
            <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 mt-0.5">
              {item.subtitle && <p className="text-xs text-ramp-text-secondary">{item.subtitle}</p>}
              {quantity > 1 && perPassStr && <p className="text-[10px] text-ramp-text-tertiary">{perPassStr}</p>}
              {coverageStr && <p className="text-[10px] text-ramp-text-tertiary">{coverageStr}</p>}
            </div>
          </div>
        </div>
        <div className="text-right flex-shrink-0 flex items-center gap-2">
          <div className="text-right">
            <p className="text-base font-bold text-ramp-text">{formatCurrency(item.cost, item)}</p>
            {quantity > 1 && <p className="text-[10px] text-ramp-text-tertiary">{quantity} passes</p>}
          </div>
          {safeHref(item.booking_url) && (
            <ExternalLink size={11} className="text-ramp-text-tertiary opacity-0 group-hover:opacity-100 transition-opacity" />
          )}
        </div>
      </div>
    </CardWrapper>
  );
}

// ── Activity Card (main timeline) ─────────────────────────────

function ActivityCard({ item }) {
  const d = item.details || {};
  const fallbackImage = "https://images.unsplash.com/photo-1488646953014-85cb44e25828?w=600";
  const [imgError, setImgError] = useState(false);
  const imgSrc = !imgError && item.image_url ? item.image_url : fallbackImage;
  const category = d.category || '';
  const hasLink = Boolean(safeHref(item.booking_url));

  return (
    <a
      href={hasLink ? safeHref(item.booking_url) : undefined}
      target={hasLink ? '_blank' : undefined}
      rel="noopener noreferrer"
      onClick={!hasLink ? (e) => e.preventDefault() : undefined}
      className={`group block bg-ramp-surface border border-ramp-border shadow-ramp
                 hover:shadow-ramp-md hover:border-ramp-border-strong transition-all duration-150 overflow-hidden
                 ${!hasLink ? 'cursor-default' : ''}`}
    >
      <div className="h-0.5 bg-ramp-yellow" />
      <div className="flex gap-0">
        <div className="w-28 flex-shrink-0 bg-ramp-surface-alt overflow-hidden">
          <img src={imgSrc} alt={item.title} className="w-full h-full object-cover"
               onError={() => setImgError(true)} style={{ minHeight: '110px' }} />
        </div>
        <div className="flex-1 px-4 py-4 min-w-0 space-y-1.5">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <TypeLabel type="activity" />
              <p className="text-sm font-semibold text-ramp-text mt-0.5 truncate">{item.title}</p>
              <p className="text-xs text-ramp-text-secondary">{item.subtitle}</p>
            </div>
            <div className="text-right flex-shrink-0">
              {item.cost === 0 ? (
                <span className="text-xs font-semibold text-ramp-green">Free</span>
              ) : (
                <p className="text-base font-bold text-ramp-text">{formatCurrency(item.cost, item)}</p>
              )}
            </div>
          </div>
          {d.description && d.description !== item.subtitle && (
            <p className="text-[11px] text-ramp-text-tertiary leading-relaxed line-clamp-2">{d.description}</p>
          )}
          <div className="flex items-center gap-2">
            {category && (
              <span className="text-[9px] px-1.5 py-0.5 border border-ramp-border text-ramp-text-tertiary bg-ramp-surface-alt capitalize">{category}</span>
            )}
            {d.city && (
              <span className="text-[9px] px-1.5 py-0.5 border border-ramp-border text-ramp-text-tertiary bg-ramp-surface-alt">{d.city}</span>
            )}
            {hasLink ? (
              <ExternalLink size={10} className="text-ramp-text-tertiary opacity-0 group-hover:opacity-100 transition-opacity ml-auto" title="Visit link" />
            ) : (
              <span className="flex items-center gap-0.5 text-[9px] text-ramp-text-tertiary opacity-0 group-hover:opacity-60 transition-opacity ml-auto italic" title="No link available">
                <Link2Off size={9} />no link
              </span>
            )}
          </div>
        </div>
      </div>
    </a>
  );
}

// ── Daily Activity Card (day-by-day timeline) ─────────────────

function DailyActivityCard({ item, isLast }) {
  const d = item.details || {};
  const fallbackImage = "https://images.unsplash.com/photo-1488646953014-85cb44e25828?w=600";
  const [imgError, setImgError] = useState(false);
  const imgSrc = !imgError && item.image_url ? item.image_url : fallbackImage;
  const hasLink = Boolean(safeHref(item.booking_url));
  const timeSlot = parseTimeSlot(item.subtitle || '');
  const TimeIcon = timeSlot?.icon || Clock;
  const CategoryIcon = getCategoryIcon(d.category || item.subtitle || '');

  return (
    <div className="relative flex gap-3">
      {/* Left: time column */}
      <div className="flex flex-col items-center flex-shrink-0 w-16">
        <div className={`text-[10px] font-semibold text-ramp-text-tertiary whitespace-nowrap`}>
          {item.time_slot || timeSlot?.label || ''}
        </div>
        {/* connector dot */}
        <div className="mt-1.5 w-2 h-2 rounded-full bg-ramp-border border-2 border-ramp-surface flex-shrink-0" />
        {!isLast && <div className="flex-1 w-px bg-ramp-border mt-1" style={{ minHeight: '40px' }} />}
      </div>

      {/* Right: card */}
      <div className="flex-1 pb-4 min-w-0">
        <a
          href={hasLink ? safeHref(item.booking_url) : undefined}
          target={hasLink ? '_blank' : undefined}
          rel="noopener noreferrer"
          onClick={!hasLink ? (e) => e.preventDefault() : undefined}
          className={`group flex gap-0 bg-ramp-surface border border-ramp-border shadow-ramp overflow-hidden
                     hover:shadow-ramp-md hover:border-ramp-border-strong transition-all duration-150
                     ${!hasLink ? 'cursor-default' : ''}`}
        >
          {/* Image */}
          <div className="w-20 flex-shrink-0 bg-ramp-surface-alt overflow-hidden">
            <img
              src={imgSrc}
              alt={item.title}
              className="w-full h-full object-cover"
              onError={() => setImgError(true)}
              style={{ minHeight: '88px' }}
            />
          </div>

          {/* Content */}
          <div className="flex-1 px-3 py-3 min-w-0">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                {/* Category pill */}
                {d.category && (
                  <span className="inline-flex items-center gap-1 text-[9px] font-semibold uppercase tracking-wider text-ramp-text-tertiary mb-1">
                    <CategoryIcon size={8} />
                    {d.category}
                  </span>
                )}
                <p className="text-xs font-semibold text-ramp-text leading-snug truncate">{item.title}</p>
                {d.description && (
                  <p className="text-[10px] text-ramp-text-tertiary leading-relaxed mt-0.5 line-clamp-2">{d.description}</p>
                )}
              </div>
              <div className="flex-shrink-0 text-right">
                {item.cost === 0 ? (
                  <span className="text-[10px] font-semibold text-ramp-green">Free</span>
                ) : item.cost > 0 ? (
                  <span className="text-[11px] font-bold text-ramp-text">{formatCurrency(item.cost, item)}</span>
                ) : null}
                {hasLink && (
                  <ExternalLink size={9} className="text-ramp-text-tertiary opacity-0 group-hover:opacity-100 transition-opacity mt-1 ml-auto block" />
                )}
              </div>
            </div>
          </div>
        </a>
      </div>
    </div>
  );
}

// ── Day Header ────────────────────────────────────────────────

function DayHeader({ dayNumber, dateStr, items }) {
  const totalCost = items.reduce((s, i) => s + (i.cost || 0), 0);
  const activityCount = items.length;
  const hasFood = items.some(i => {
    const c = (i.details?.category || i.subtitle || '').toLowerCase();
    return c.includes('food') || c.includes('restaurant') || c.includes('eat') || c.includes('lunch') || c.includes('dinner') || c.includes('breakfast') || c.includes('cafe');
  });

  return (
    <div className="sticky top-0 z-10 bg-ramp-bg border-b border-ramp-border py-3 mb-4 -mx-1 px-1">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-ramp-text flex items-center justify-center flex-shrink-0">
            <span className="text-xs font-bold text-white">{dayNumber}</span>
          </div>
          <div>
            <p className="text-sm font-bold text-ramp-text">{formatDateShort(dateStr)}</p>
            <p className="text-[10px] text-ramp-text-tertiary mt-0.5">
              {activityCount} stop{activityCount !== 1 ? 's' : ''}
              {hasFood ? ' · includes dining' : ''}
              {totalCost > 0 ? ` · ~${formatCurrency(totalCost, {})} est.` : ''}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          {items.some(i => (i.details?.category || '').toLowerCase().includes('food') || (i.subtitle || '').toLowerCase().includes('lunch') || (i.subtitle || '').toLowerCase().includes('dinner') || (i.subtitle || '').toLowerCase().includes('breakfast')) && (
            <span className="text-[9px] px-1.5 py-0.5 border border-ramp-border bg-ramp-surface-alt text-ramp-text-tertiary flex items-center gap-1">
              <Utensils size={8} /> Dining
            </span>
          )}
        </div>
      </div>
    </div>
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

// ── Main Trip Timeline ────────────────────────────────────────

export default function ItineraryTimeline({ itinerary }) {
  if (!itinerary) return null;

  const items = (itinerary.items || []).filter(
    item => !(item.type === 'transit' && !item.cost && !item.booking_url)
  );

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
      {/* Trip Header */}
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
            <p className="text-2xl font-bold text-ramp-text">{formatCurrency(totalCost, { currency_code: 'USD', currency_symbol: '$' })}</p>
            <p className="text-xs text-ramp-text-tertiary mt-0.5">estimated total</p>
          </div>
        </div>
      </div>

      {/* Timeline Items */}
      <div className="space-y-0">
        {items.map((item, idx) => (
          <TimelineItem
            key={idx}
            item={item}
            index={idx}
            isLast={idx === items.length - 1}
            runningCost={runningCosts[idx]}
          />
        ))}
      </div>

      {/* Total Cost Footer */}
      <div className="mt-2 bg-ramp-surface border border-ramp-border shadow-ramp overflow-hidden">
        <div className="h-0.5 bg-ramp-yellow" />
        <div className="px-6 py-4 flex items-center justify-between">
          <div>
            <p className="text-sm font-semibold text-ramp-text">Total Trip Cost</p>
            <p className="text-xs text-ramp-text-tertiary mt-0.5">All flights, hotels & transit combined</p>
          </div>
          <p className="text-2xl font-bold text-ramp-text">{formatCurrency(totalCost, { currency_code: 'USD', currency_symbol: '$' })}</p>
        </div>
      </div>
    </div>
  );
}

// ── Day-by-Day Activity Timeline ──────────────────────────────

export function DailyItineraryTimeline({ itinerary }) {
  if (!itinerary) return null;

  const items = itinerary.items || [];
  if (items.length === 0) return null;

  // Group items by date
  const dayMap = new Map();
  for (const item of items) {
    const key = item.date || 'unknown';
    if (!dayMap.has(key)) dayMap.set(key, []);
    dayMap.get(key).push(item);
  }

  const sortedDays = [...dayMap.entries()].sort(([a], [b]) => a.localeCompare(b));
  const totalCost = getTotalCostUSD(items, itinerary.total_cost);

  return (
    <div className="animate-slide-up">
      {/* Header */}
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
            </div>
            <div className="flex items-center gap-2 mt-3">
              <span className="text-[10px] px-2 py-0.5 border border-ramp-border text-ramp-text-secondary bg-ramp-surface-alt">
                {sortedDays.length} day{sortedDays.length !== 1 ? 's' : ''}
              </span>
              <span className="text-[10px] px-2 py-0.5 border border-ramp-border text-ramp-text-secondary bg-ramp-surface-alt">
                {items.length} activities
              </span>
            </div>
          </div>
          {totalCost > 0 && (
            <div className="text-right flex-shrink-0">
              <p className="text-xl font-bold text-ramp-text">{formatCurrency(totalCost, { currency_code: 'USD', currency_symbol: '$' })}</p>
              <p className="text-xs text-ramp-text-tertiary mt-0.5">activities est.</p>
            </div>
          )}
        </div>
      </div>

      {/* Days */}
      <div className="space-y-6">
        {sortedDays.map(([dateStr, dayItems], dayIdx) => (
          <div key={dateStr} className="bg-ramp-surface border border-ramp-border shadow-ramp overflow-hidden animate-slide-up" style={{ animationDelay: `${dayIdx * 80}ms` }}>
            <div className="h-0.5 bg-ramp-yellow" />
            {/* Day header */}
            <div className="px-5 py-4 border-b border-ramp-border bg-ramp-surface-alt">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-7 h-7 bg-ramp-text flex items-center justify-center flex-shrink-0">
                    <span className="text-[11px] font-bold text-white">{dayIdx + 1}</span>
                  </div>
                  <div>
                    <p className="text-sm font-bold text-ramp-text">{formatDateShort(dateStr)}</p>
                    <p className="text-[10px] text-ramp-text-tertiary mt-0.5">
                      {/* Show city if known — take from first item with details.city */}
                      {(() => { const city = dayItems.find(i => i.details?.city)?.details?.city; return city ? <span className="font-medium text-ramp-text-secondary">{city} · </span> : null; })()}
                      {dayItems.length} stop{dayItems.length !== 1 ? 's' : ''}
                      {dayItems.some(i => {
                        const c = (i.details?.category || i.subtitle || '').toLowerCase();
                        return c.includes('food') || c.includes('restaurant') || c.includes('lunch') || c.includes('dinner') || c.includes('breakfast') || c.includes('cafe') || c.includes('dining');
                      }) ? ' · includes dining' : ''}
                    </p>
                  </div>
                </div>
                {/* Day cost */}
                {dayItems.reduce((s, i) => s + (i.cost || 0), 0) > 0 && (
                  <p className="text-xs font-semibold text-ramp-text">
                    ~{formatCurrency(dayItems.reduce((s, i) => s + (i.cost || 0), 0), {})}
                  </p>
                )}
              </div>
            </div>

            {/* Activity list for this day */}
            <div className="px-5 pt-4 pb-2">
              {dayItems.map((item, itemIdx) => (
                <DailyActivityCard
                  key={itemIdx}
                  item={item}
                  isLast={itemIdx === dayItems.length - 1}
                />
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Total footer */}
      {totalCost > 0 && (
        <div className="mt-4 bg-ramp-surface border border-ramp-border shadow-ramp overflow-hidden">
          <div className="h-0.5 bg-ramp-yellow" />
          <div className="px-6 py-4 flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold text-ramp-text">Total Activity Cost</p>
              <p className="text-xs text-ramp-text-tertiary mt-0.5">Estimated admissions & dining</p>
            </div>
            <p className="text-xl font-bold text-ramp-text">{formatCurrency(totalCost, { currency_code: 'USD', currency_symbol: '$' })}</p>
          </div>
        </div>
      )}
    </div>
  );
}