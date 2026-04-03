"""
Car rental & transit service.

Car rentals: RapidAPI Booking.com real-time search → fallback to booking-redirect links.
Transit: SerpAPI Google Search for real transit pass info → fallback to curated data.
All transit prices are converted to USD. Pass quantity is calculated from days_in_city.
"""

import logging
import hashlib
import requests
import re
import math
import urllib.parse
from datetime import datetime

from config import Config

logger = logging.getLogger(__name__)


# ── Car images (royalty-free from Unsplash) ────────────────────

CAR_IMAGES = {
    "compact":     "https://images.unsplash.com/photo-1549317661-bd32c8ce0afa?w=400",
    "midsize":     "https://images.unsplash.com/photo-1590362891991-f776e747a588?w=400",
    "full_size":   "https://images.unsplash.com/photo-1553440569-bcc63803a83d?w=400",
    "suv":         "https://images.unsplash.com/photo-1519641471654-76ce0107ad1b?w=400",
    "luxury":      "https://images.unsplash.com/photo-1555215695-3004980ad54e?w=400",
    "minivan":     "https://images.unsplash.com/photo-1570294646112-27ce4f174e33?w=400",
    "convertible": "https://images.unsplash.com/photo-1544636331-e26879cd4d9b?w=400",
}

# ── Curated reference links for transit info pages ─────────────
# Used as guaranteed fallback when SerpAPI returns no URL or a Google search URL.
# These are the *official* transit authority pages for each city.
TRANSIT_REFERENCE_LINKS = {
    "chongqing":   "https://www.cqmetro.cn/",
    "tokyo":       "https://www.tokyometro.jp/en/ticket/travel/index.html",
    "london":      "https://tfl.gov.uk/fares/",
    "paris":       "https://www.ratp.fr/en/titres-et-tarifs/tickets-and-fares",
    "new york":    "https://new.mta.info/fares",
    "new york city": "https://new.mta.info/fares",
    "nyc":         "https://new.mta.info/fares",
    "singapore":   "https://thesingaporetouristpass.com.sg/",
    "barcelona":   "https://www.holabarcelona.com/",
    "osaka":       "https://www.osakametro.co.jp/en/tickets/otps/",
    "seoul":       "https://www.t-money.co.kr/eng/",
    "toronto":     "https://www.ttc.ca/fares-and-passes",
    "vancouver":   "https://www.translink.ca/transit-fares",
    "montreal":    "https://www.stm.info/en/info/fares",
    "chicago":     "https://www.transitchicago.com/fares/",
    "boston":      "https://www.mbta.com/fares",
    "washington":  "https://www.wmata.com/fares/",
    "dc":          "https://www.wmata.com/fares/",
    "san francisco": "https://www.bart.gov/tickets",
    "seattle":     "https://kingcountymetro.com/fares/",
    "hong kong":   "https://www.mtr.com.hk/en/customer/tickets/index.html",
    "amsterdam":   "https://www.gvb.nl/en/tickets",
    "berlin":      "https://www.bvg.de/en/tickets",
    "rome":        "https://www.atac.roma.it/en/",
    "madrid":      "https://www.crtm.es/",
    "dubai":       "https://www.rta.ae/wps/portal/rta/ae/public-transport",
}

CURRENCY_SYMBOLS = {
    "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥",
    "CNY": "¥", "SGD": "S$", "KRW": "₩",
}


def _currency_symbol(code: str | None) -> str:
    return CURRENCY_SYMBOLS.get((code or "").upper(), (code or "USD").upper())


def _detect_currency(text: str) -> tuple[str, str]:
    lower = (text or "").lower()
    if any(t in lower for t in ("cny", "rmb", "yuan", "renminbi", "元", "￥", "¥")):
        return "CNY", _currency_symbol("CNY")
    if any(t in lower for t in ("jpy", "yen")):
        return "JPY", _currency_symbol("JPY")
    if any(t in lower for t in ("gbp", "pound", "pounds", "£")):
        return "GBP", _currency_symbol("GBP")
    if any(t in lower for t in ("eur", "euro", "euros", "€")):
        return "EUR", _currency_symbol("EUR")
    if any(t in lower for t in ("sgd", "singapore dollar", "singapore dollars")):
        return "SGD", _currency_symbol("SGD")
    if any(t in lower for t in ("krw", "won", "₩")):
        return "KRW", _currency_symbol("KRW")
    # FIX: Explicitly reject CAD hits — "$" in Canadian context is CAD not USD.
    # The SerpAPI parser already strips CAD via _to_usd, but if the snippet says
    # "CA$" or "CAD" we detect it here so the price gets converted.
    if any(t in lower for t in ("cad", "ca$", "canadian dollar")):
        return "CAD", "CA$"
    return "USD", _currency_symbol("USD")


def _to_usd(price: float, currency_code: str) -> float:
    """Convert price to USD using live rates with hardcoded fallback."""
    if currency_code == "USD" or price <= 0:
        return price
    try:
        from services.currency_conversion import get_usd_rate
        rate = get_usd_rate(currency_code)
        return round(price * rate, 2)
    except Exception:
        fallback = {
            "EUR": 1.08, "GBP": 1.27, "JPY": 0.0067, "CNY": 0.14,
            "SGD": 0.74, "KRW": 0.00074, "CAD": 0.73, "AUD": 0.65,
        }
        return round(price * fallback.get(currency_code.upper(), 1.0), 2)


def _best_transit_link(city: str, link: str = "") -> str:
    """
    Return the best URL for transit info.
    Priority: provided link (if not a raw Google search URL) → curated reference link.
    Always returns a non-empty string for cities we know about.
    """
    link = (link or "").strip()
    # Accept any real URL that isn't a Google search results page
    if link and "google.com/search" not in link and link.startswith("http"):
        return link
    # Fall back to our curated reference link for the city
    city_lower = city.strip().lower()
    return TRANSIT_REFERENCE_LINKS.get(city_lower, "")


# ── Pass duration & quantity logic ────────────────────────────

# Sentinel: rechargeable cards that cover the entire stay (buy once, top up)
_UNLIMITED_DURATION = 999


def _detect_pass_duration(name: str, pass_type: str) -> int:
    """
    Infer how many days a single pass covers from its name and type.
    Returns _UNLIMITED_DURATION (999) for rechargeable top-up cards.
    """
    lower = name.lower()

    # Explicit month count: "1-Month Pass", "30-Day Pass"
    m = re.search(r'(\d+)\s*-?\s*month', lower)
    if m:
        return int(m.group(1)) * 30

    # Explicit week count: "2-Week Pass"
    m = re.search(r'(\d+)\s*-?\s*week', lower)
    if m:
        return int(m.group(1)) * 7

    # Explicit day count: "7-Day", "5-Day", "3 Day"
    m = re.search(r'(\d+)\s*-?\s*day', lower)
    if m:
        return int(m.group(1))

    # Hour-based: "72-Hour", "24-Hour", "48-Hour"
    m = re.search(r'(\d+)\s*-?\s*hour', lower)
    if m:
        return max(1, math.ceil(int(m.group(1)) / 24))

    # Keyword fallbacks
    if any(k in lower for k in ("weekly", "7 day")):
        return 7
    if any(k in lower for k in ("monthly", "30 day")):
        return 30
    if any(k in lower for k in ("annual", "yearly", "365")):
        return 365

    # Rechargeable cards: buy once, top up as needed — always quantity 1
    if any(k in lower for k in ("oyster", "suica", "pasmo", "t-money", "t money",
                                 "octopus", "navigo easy", "rechargeable", "presto")):
        return _UNLIMITED_DURATION

    # Pass type fallbacks
    if pass_type == "rail_pass":
        return 7
    if pass_type == "metro_pass":
        return 7
    if pass_type == "day_pass":
        return 1

    # Unknown — treat as day pass (safe, never under-counts)
    return 1


def _calculate_quantity(days_in_city: int, pass_duration: int) -> int:
    """How many passes are needed to cover the stay?"""
    if pass_duration >= _UNLIMITED_DURATION:
        return 1
    return math.ceil(days_in_city / pass_duration)


def _pass_label(name: str, quantity: int) -> str:
    """E.g. '2× 7-Day Unlimited MetroCard'"""
    return f"{quantity}× {name}" if quantity > 1 else name


def _enrich_with_quantity(result: dict, days_in_city: int) -> dict:
    """
    Attach quantity, total_price, pass_duration_days, and pass_label to a
    raw pass result (price already in USD).
    """
    name = result.get("name", "Transit Pass")
    pass_type = result.get("type", "transit_card")
    price_per_pass = result.get("price", 0)

    duration = _detect_pass_duration(name, pass_type)
    quantity = _calculate_quantity(days_in_city, duration)
    total_price = round(price_per_pass * quantity, 2)

    return {
        **result,
        "price_per_pass": price_per_pass,
        "quantity": quantity,
        # Report actual days covered per pass (cap 999 to days_in_city for display)
        "pass_duration_days": duration if duration < _UNLIMITED_DURATION else days_in_city,
        "days_in_city": days_in_city,
        "total_price": total_price,
        "pass_label": _pass_label(name, quantity),
    }


def _pick_best_pass(options: list[dict], days_in_city: int) -> dict:
    """
    Choose the pass option that minimises total cost for the stay.
    Falls back to the first option if all prices are 0.
    """
    if not options:
        raise ValueError("No options to pick from")

    def total_cost(opt):
        p = opt.get("price", 0)
        if p <= 0:
            return float("inf")
        dur = _detect_pass_duration(opt.get("name", ""), opt.get("type", "transit_card"))
        qty = _calculate_quantity(days_in_city, dur)
        return p * qty

    best = min(options, key=total_cost)
    # If all prices are 0, just return the first (it still has a URL at minimum)
    if best.get("price", 0) <= 0:
        return options[0]
    return best


# ── Curated transit data ───────────────────────────────────────
# All prices in USD. Duration inferred from name via _detect_pass_duration.

TRANSIT_OPTIONS = {
    "Tokyo": [
        {"name": "7-Day Japan Rail Pass",       "type": "rail_pass",    "price": 280, "description": "Unlimited travel on JR lines nationwide",                        "url": "https://www.japan-rail-pass.com"},
        {"name": "Tokyo Metro 72-Hour Pass",     "type": "metro_pass",   "price": 15,  "description": "Unlimited Tokyo Metro and Toei subway rides",                     "url": "https://www.tokyometro.jp/en/ticket/travel/index.html"},
        {"name": "Suica Card",                   "type": "transit_card", "price": 5,   "description": "Rechargeable IC card for trains, buses, and shops",               "url": "https://www.jreast.co.jp/e/pass/suica.html"},
    ],
    "London": [
        {"name": "7-Day Travelcard",             "type": "metro_pass",   "price": 55,  "description": "Unlimited travel Zones 1-4 on Tube, buses, and DLR",             "url": "https://tfl.gov.uk/fares/find-fares/tube-and-rail-fares/caps-and-travelcard-prices"},
        {"name": "Oyster Card",                  "type": "transit_card", "price": 10,  "description": "Capped daily/weekly PAYG fares on Tube, buses, and DLR",          "url": "https://tfl.gov.uk/fares/how-to-pay-and-where-to-buy-tickets-and-oyster/pay-as-you-go/oyster-pay-as-you-go"},
    ],
    "Paris": [
        {"name": "Paris Visite 5-Day Pass",      "type": "metro_pass",   "price": 50,  "description": "Unlimited travel on Metro, RER, buses Zones 1-3",                 "url": "https://www.ratp.fr/en/titres-et-tarifs/paris-visite-travel-pass"},
        {"name": "Navigo Weekly Pass",           "type": "metro_pass",   "price": 30,  "description": "Unlimited weekly travel on all Paris public transit",              "url": "https://www.iledefrance-mobilites.fr"},
    ],
    "New York": [
        {"name": "7-Day Unlimited MetroCard",    "type": "metro_pass",   "price": 34,  "description": "Unlimited subway and local bus rides for 7 days",                 "url": "https://new.mta.info/fares"},
        {"name": "30-Day Unlimited MetroCard",   "type": "metro_pass",   "price": 132, "description": "Unlimited subway and local bus rides for 30 days",                "url": "https://new.mta.info/fares"},
    ],
    "Singapore": [
        {"name": "Singapore Tourist Pass 3-Day", "type": "transit_card", "price": 20,  "description": "Unlimited travel on MRT and public buses for 3 days",             "url": "https://thesingaporetouristpass.com.sg"},
    ],
    "Barcelona": [
        {"name": "Hola Barcelona 5-Day Pass",    "type": "metro_pass",   "price": 48,  "description": "Unlimited public transport including airport rail",                "url": "https://www.holabarcelona.com"},
    ],
    "Osaka": [
        {"name": "Osaka Amazing Pass 2-Day",     "type": "metro_pass",   "price": 34,  "description": "Unlimited subway/bus and free entry to 30+ attractions",          "url": "https://www.osp.osaka-info.jp/en/"},
    ],
    "Seoul": [
        {"name": "T-money Card",                 "type": "transit_card", "price": 3,   "description": "Rechargeable card for subway, buses, and taxis",                  "url": "https://www.t-money.co.kr/eng/"},
        {"name": "Discover Seoul Pass 72-Hour",  "type": "metro_pass",   "price": 55,  "description": "Free transport + entry to 30+ attractions for 72 hours",          "url": "https://www.discoverseoulpass.com/"},
    ],
    "Chongqing": [
        {"name": "Chongqing Metro Day Pass",     "type": "day_pass",     "price": 3,   "description": "Day pass for Chongqing metro and rail transit",                   "url": "https://www.cqmetro.cn/"},
    ],
    # FIX: Toronto added with USD prices and official TTC link
    "Toronto": [
        {"name": "PRESTO Day Pass",              "type": "day_pass",     "price": 10,  "description": "Unlimited TTC subway, bus, and streetcar rides for one day (USD equivalent)", "url": "https://www.ttc.ca/fares-and-passes"},
        {"name": "PRESTO Card",                  "type": "transit_card", "price": 6,   "description": "Reloadable card for TTC with discounted per-ride fares",           "url": "https://www.prestocard.ca/en"},
    ],
    "Vancouver": [
        {"name": "DayPass",                      "type": "day_pass",     "price": 11,  "description": "Unlimited travel on SkyTrain, buses, and SeaBus for one day",     "url": "https://www.translink.ca/transit-fares/transit-fare-options/daypass"},
        {"name": "Compass Card",                 "type": "transit_card", "price": 6,   "description": "Reloadable card for TransLink with tap-to-pay fares",              "url": "https://www.compasscard.ca/"},
    ],
    "Montreal": [
        {"name": "3-Day Tourist Pass",           "type": "metro_pass",   "price": 19,  "description": "Unlimited STM metro and bus rides for 3 consecutive days",        "url": "https://www.stm.info/en/info/fares/tourist"},
        {"name": "Weekly Pass",                  "type": "metro_pass",   "price": 29,  "description": "Unlimited STM metro and bus rides for 7 days",                    "url": "https://www.stm.info/en/info/fares"},
    ],
    "Chicago": [
        {"name": "3-Day Unlimited Ride Pass",    "type": "metro_pass",   "price": 20,  "description": "Unlimited CTA train and bus rides for 3 days",                    "url": "https://www.transitchicago.com/fares/"},
        {"name": "7-Day Unlimited Ride Pass",    "type": "metro_pass",   "price": 28,  "description": "Unlimited CTA train and bus rides for 7 days",                    "url": "https://www.transitchicago.com/fares/"},
    ],
    "Boston": [
        {"name": "7-Day LinkPass",               "type": "metro_pass",   "price": 22,  "description": "Unlimited MBTA subway, bus, and commuter rail Zone 1A for 7 days","url": "https://www.mbta.com/fares/charliecard"},
    ],
    "Washington": [
        {"name": "7-Day Short-Trip Pass",        "type": "metro_pass",   "price": 38,  "description": "Unlimited WMATA Metro rail and bus rides up to $3.85/trip for 7 days", "url": "https://www.wmata.com/fares/"},
    ],
    "San Francisco": [
        {"name": "Clipper Card",                 "type": "transit_card", "price": 3,   "description": "Reloadable card for BART, Muni, and other Bay Area transit",      "url": "https://www.clippercard.com/ClipperWeb/"},
        {"name": "Muni 7-Day Passport",          "type": "metro_pass",   "price": 23,  "description": "Unlimited Muni bus and metro rides for 7 days",                   "url": "https://www.sfmta.com/fares/muni-passports"},
    ],
    "Seattle": [
        {"name": "ORCA Card",                    "type": "transit_card", "price": 3,   "description": "Reloadable card for Link Light Rail, buses, and ferries",         "url": "https://www.orcacard.com/"},
    ],
    "Hong Kong": [
        {"name": "Airport Express Tourist Octopus", "type": "transit_card", "price": 16, "description": "Octopus card with airport express + unlimited MTR/bus rides",   "url": "https://www.mtr.com.hk/en/customer/tickets/index.html"},
    ],
    "Amsterdam": [
        {"name": "Amsterdam & Region Travel Ticket 3-Day", "type": "metro_pass", "price": 32, "description": "Unlimited GVB tram, metro, bus, and night bus for 3 days", "url": "https://www.gvb.nl/en/tickets/amsterdam-travel-ticket"},
    ],
    "Berlin": [
        {"name": "Berlin 7-Day AB Pass",         "type": "metro_pass",   "price": 36,  "description": "Unlimited BVG U-Bahn, S-Bahn, tram, and bus in zones A+B",       "url": "https://www.bvg.de/en/tickets/all-tickets/weekly-ticket"},
    ],
}


# ── Public interface: Transit ─────────────────────────────────

def search_transit(city: str, days_in_city: int = 7) -> list[dict]:
    """
    Return the best transit pass option for a city, with quantity and total_price
    pre-calculated for the traveler's stay length.

    Returned fields per result:
      name            — pass name
      price_per_pass  — cost of one pass (USD)
      pass_duration_days — days covered by one pass
      quantity        — passes needed to cover days_in_city
      total_price     — price_per_pass × quantity  ← use this as the itinerary cost
      pass_label      — e.g. "2× 7-Day Unlimited MetroCard"
      days_in_city    — echoed back for the UI
      booking_url     — link to purchase (always set for known cities)
    """
    days_in_city = max(1, int(days_in_city))
    raw: list[dict] = []

    # 1. Try SerpAPI
    if Config.SERPAPI_KEY:
        try:
            raw = _search_serpapi_transit(city)
            if raw:
                logger.info("SerpAPI transit: %d results for %s", len(raw), city)
        except Exception:
            logger.exception("SerpAPI transit failed for %s", city)

    # 2. Curated fallback
    if not raw:
        options = TRANSIT_OPTIONS.get(city, [])
        if options:
            raw = [
                {**o, "price": o.get("price", 0), "currency_code": "USD", "currency_symbol": "$",
                 "booking_url": o.get("booking_url", o.get("url", ""))}
                for o in options
            ]
            logger.info("Curated transit data for %s (%d options)", city, len(raw))

    # 3. Nothing found
    if not raw:
        logger.info("No transit data for %s — skipping", city)
        return []

    # Remove zero-price entries that also lack a URL (truly useless)
    raw = [r for r in raw if r.get("price", 0) > 0 or r.get("booking_url")]

    # FIX: Guarantee every result has a booking_url by falling back to the
    # curated reference link for the city. This ensures the card is always clickable.
    city_lower = city.strip().lower()
    fallback_url = TRANSIT_REFERENCE_LINKS.get(city_lower, "")
    for r in raw:
        if not r.get("booking_url") and fallback_url:
            r["booking_url"] = fallback_url

    # FIX: Force all prices to USD — SerpAPI may return CAD prices for Canadian cities.
    # The curated data is already in USD, but SerpAPI results need explicit conversion.
    for r in raw:
        cc = r.get("currency_code", "USD")
        if cc != "USD" and r.get("price", 0) > 0:
            r["price"] = _to_usd(r["price"], cc)
            r["currency_code"] = "USD"
            r["currency_symbol"] = "$"

    # Pick the cheapest option for this stay, then enrich
    best = _pick_best_pass(raw, days_in_city)
    enriched = _enrich_with_quantity(best, days_in_city)

    # Ensure the enriched result always has a booking_url
    if not enriched.get("booking_url") and fallback_url:
        enriched["booking_url"] = fallback_url

    logger.info(
        "Transit %s (%dd): %s — %d× %dd pass = $%.2f",
        city, days_in_city, enriched["name"],
        enriched["quantity"], enriched["pass_duration_days"], enriched["total_price"],
    )

    return [enriched]


# ── SerpAPI transit search ─────────────────────────────────────

def _search_serpapi_transit(city: str) -> list[dict]:
    if not Config.SERPAPI_KEY:
        raise ValueError("SERPAPI_KEY not set")

    params = {
        "engine": "google",
        "q": f"{city} transit pass travel card price USD",
        "num": 5, "hl": "en", "gl": "us",
        "api_key": Config.SERPAPI_KEY,
    }
    resp = requests.get("https://serpapi.com/search.json", params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    transit_keywords = [
        "pass", "card", "ticket", "metro", "subway", "transit", "travel card",
        "transport", "bus", "rail", "tram", "oyster", "suica", "navigo", "t-money",
        "metrocard", "presto", "compass", "orca", "clipper",
    ]

    results = []
    for item in data.get("organic_results", [])[:8]:
        title, snippet, link = item.get("title",""), item.get("snippet",""), item.get("link","")
        if not any(kw in (title + snippet).lower() for kw in transit_keywords):
            continue
        pi = _parse_transit_result(title, snippet, link, city)
        if pi:
            results.append(pi)
        elif link:
            fi = _fallback_transit_result(title, snippet, link, city)
            if fi:
                results.append(fi)

    ab = data.get("answer_box", {})
    if ab:
        at = ab.get("title","") or ab.get("answer","")
        as_ = ab.get("snippet","") or ab.get("description","")
        al = ab.get("link","")
        if at and any(kw in (at + as_).lower() for kw in ["transit","pass","card","metro"]):
            pi = _parse_transit_result(at, as_, al, city)
            if pi:
                results.insert(0, pi)
            elif al:
                fi = _fallback_transit_result(at, as_, al, city)
                if fi:
                    results.insert(0, fi)

    # Deduplicate
    seen, unique = set(), []
    for r in results:
        k = r["name"].lower()[:30]
        if k not in seen:
            seen.add(k); unique.append(r)

    # Normalise to USD (handles CAD, EUR, GBP, etc. from SerpAPI snippets)
    for r in unique:
        cc = r.get("currency_code", "USD")
        if cc != "USD" and r.get("price", 0) > 0:
            r["price"] = _to_usd(r["price"], cc)
            r["currency_code"] = "USD"
            r["currency_symbol"] = "$"

    return unique[:5]


def _parse_transit_result(title: str, snippet: str, link: str, city: str) -> dict | None:
    text = f"{snippet} {title}".strip()
    currency_code, _ = _detect_currency(text)

    price = 0
    for pattern in [
        r'(?:rmb|cny|yuan|renminbi|¥|￥|元)\s*(\d+(?:\.\d{1,2})?)',
        r'(\d+(?:\.\d{1,2})?)\s*(?:rmb|cny|yuan|renminbi|元)',
        r'(?:\$|usd)\s*(\d+(?:\.\d{1,2})?)',
        r'(\d+(?:\.\d{1,2})?)\s*(?:usd|eur|gbp|sgd|krw|jpy|dollars?)',
        r'(?:€|£|₩)\s*(\d+(?:\.\d{1,2})?)',
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                c = float(m.group(1))
                if 1 <= c <= 500:
                    price = c; break
            except ValueError:
                pass

    lower = (title + snippet).lower()
    pass_type = "transit_card"
    if any(k in lower for k in ["rail pass", "train pass", "jr pass"]):
        pass_type = "rail_pass"
    elif any(k in lower for k in ["metro pass", "subway pass", "unlimited"]):
        pass_type = "metro_pass"
    elif any(k in lower for k in ["day pass", "day ticket", "24-hour", "48-hour", "72-hour"]):
        pass_type = "day_pass"

    name = title.strip()
    for suffix in [" - Google Search", " | Google Maps", " - Wikipedia"]:
        name = name.replace(suffix, "")
    name = name[:80]
    if not name:
        return None

    usd_price = _to_usd(price, currency_code) if price > 0 else 0
    booking_url = _best_transit_link(city, link)
    return {
        "name": name, "type": pass_type, "price": usd_price,
        "currency_code": "USD", "currency_symbol": "$",
        "description": snippet[:200].strip() if snippet else f"Public transit option for {city}",
        "url": booking_url, "booking_url": booking_url,
    }


def _fallback_transit_result(title: str, snippet: str, link: str, city: str) -> dict | None:
    name = (title or "").strip()
    if not name:
        return None
    booking_url = _best_transit_link(city, link)
    return {
        "name": name[:80], "type": "transit_card", "price": 0,
        "currency_code": "USD", "currency_symbol": "$",
        "description": snippet[:200].strip() if snippet else f"Public transit information for {city}",
        "url": booking_url, "booking_url": booking_url,
    }