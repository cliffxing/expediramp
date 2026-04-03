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
# Used as guaranteed fallback when SerpAPI returns no URL or a bad one.
TRANSIT_REFERENCE_LINKS = {
    "beijing":       "https://www.bjsubway.com/en/",
    "shanghai":      "https://www.shmetro.com/",
    "chengdu":       "https://www.cdmetro.cn/",
    "chongqing":     "https://www.cqmetro.cn/",
    "guangzhou":     "https://www.gzmtr.com/",
    "shenzhen":      "https://www.szmc.net/",
    "xian":          "https://www.xianmetro.com/",
    "xi'an":         "https://www.xianmetro.com/",
    "hangzhou":      "https://www.hzmetro.com/",
    "wuhan":         "https://www.whmetro.com/",
    "tokyo":         "https://www.tokyometro.jp/en/ticket/travel/index.html",
    "osaka":         "https://www.osakametro.co.jp/en/tickets/otps/",
    "kyoto":         "https://www2.city.kyoto.lg.jp/kotsu/webguide/en/",
    "london":        "https://tfl.gov.uk/fares/",
    "paris":         "https://www.ratp.fr/en/titres-et-tarifs/tickets-and-fares",
    "berlin":        "https://www.bvg.de/en/tickets",
    "amsterdam":     "https://www.gvb.nl/en/tickets",
    "rome":          "https://www.atac.roma.it/en/",
    "madrid":        "https://www.crtm.es/",
    "barcelona":     "https://www.holabarcelona.com/",
    "new york":      "https://new.mta.info/fares",
    "new york city": "https://new.mta.info/fares",
    "nyc":           "https://new.mta.info/fares",
    "chicago":       "https://www.transitchicago.com/fares/",
    "boston":        "https://www.mbta.com/fares",
    "washington":    "https://www.wmata.com/fares/",
    "dc":            "https://www.wmata.com/fares/",
    "san francisco": "https://www.bart.gov/tickets",
    "seattle":       "https://kingcountymetro.com/fares/",
    "toronto":       "https://www.ttc.ca/fares-and-passes",
    "vancouver":     "https://www.translink.ca/transit-fares",
    "montreal":      "https://www.stm.info/en/info/fares",
    "singapore":     "https://thesingaporetouristpass.com.sg/",
    "hong kong":     "https://www.mtr.com.hk/en/customer/tickets/index.html",
    "seoul":         "https://www.t-money.co.kr/eng/",
    "dubai":         "https://www.rta.ae/wps/portal/rta/ae/public-transport",
}

CURRENCY_SYMBOLS = {
    "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥",
    "CNY": "¥", "SGD": "S$", "KRW": "₩",
}

# ── Domains that are Q&A / forum / aggregator sites ───────────
# SerpAPI sometimes returns these for transit queries — they produce
# misleading pass names ("What is the cost of...") and unreliable prices.
_JUNK_DOMAINS = {
    "quora.com", "reddit.com", "tripadvisor.com", "yahoo.com",
    "answers.com", "wikianswers.com", "ask.com", "stackexchange.com",
    "travel.stackexchange.com", "expat.com", "expatexchange.com",
    "lonelyplanet.com", "wikitravel.org", "wikivoyage.org",
}


def _is_junk_url(url: str) -> bool:
    """Return True if the URL is from a Q&A, forum, or travel guide site."""
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc.lower().lstrip("www.")
        return any(host == d or host.endswith("." + d) for d in _JUNK_DOMAINS)
    except Exception:
        return False


# ── Curated transit data ───────────────────────────────────────
# All prices in USD. Duration inferred from name via _detect_pass_duration.

TRANSIT_OPTIONS = {
    "Tokyo": [
        {"name": "Tokyo Metro 72-Hour Pass",     "type": "metro_pass",   "price": 15,  "description": "Unlimited Tokyo Metro and Toei subway rides for 72 hours",        "url": "https://www.tokyometro.jp/en/ticket/travel/index.html"},
        {"name": "Suica Card",                   "type": "transit_card", "price": 5,   "description": "Rechargeable IC card for trains, buses, and shops",               "url": "https://www.jreast.co.jp/e/pass/suica.html"},
        {"name": "7-Day Japan Rail Pass",        "type": "rail_pass",    "price": 280, "description": "Unlimited travel on JR lines nationwide for 7 days",              "url": "https://www.japan-rail-pass.com"},
    ],
    "Osaka": [
        {"name": "Osaka Amazing Pass 2-Day",     "type": "metro_pass",   "price": 34,  "description": "Unlimited subway/bus and free entry to 30+ attractions",          "url": "https://www.osp.osaka-info.jp/en/"},
        {"name": "ICOCA Card",                   "type": "transit_card", "price": 5,   "description": "Rechargeable IC card for Osaka metro, buses, and JR",             "url": "https://www.westjr.co.jp/global/en/travel/icoca/"},
    ],
    "Kyoto": [
        {"name": "Kyoto Bus 1-Day Pass",         "type": "day_pass",     "price": 7,   "description": "Unlimited rides on Kyoto city buses for one day",                 "url": "https://www2.city.kyoto.lg.jp/kotsu/webguide/en/"},
        {"name": "ICOCA Card",                   "type": "transit_card", "price": 5,   "description": "Rechargeable IC card for Kyoto metro, buses, and JR",             "url": "https://www.westjr.co.jp/global/en/travel/icoca/"},
    ],
    "London": [
        {"name": "7-Day Travelcard Zones 1-2",   "type": "metro_pass",   "price": 55,  "description": "Unlimited travel on Tube, buses, DLR, and Overground Zones 1-2",  "url": "https://tfl.gov.uk/fares/find-fares/tube-and-rail-fares/caps-and-travelcard-prices"},
        {"name": "Oyster Card",                  "type": "transit_card", "price": 10,  "description": "Pay-as-you-go with daily/weekly fare caps on all TfL services",   "url": "https://tfl.gov.uk/fares/how-to-pay-and-where-to-buy-tickets-and-oyster/pay-as-you-go/oyster-pay-as-you-go"},
    ],
    "Paris": [
        {"name": "Navigo Weekly Pass",           "type": "metro_pass",   "price": 30,  "description": "Unlimited weekly travel on all Paris Metro, RER, buses, and trams", "url": "https://www.iledefrance-mobilites.fr"},
        {"name": "Paris Visite 5-Day Pass",      "type": "metro_pass",   "price": 50,  "description": "Unlimited travel on Metro, RER, buses Zones 1-3 for 5 days",      "url": "https://www.ratp.fr/en/titres-et-tarifs/paris-visite-travel-pass"},
    ],
    "Berlin": [
        {"name": "Berlin 7-Day AB Pass",         "type": "metro_pass",   "price": 36,  "description": "Unlimited BVG U-Bahn, S-Bahn, tram, and bus in zones A+B",       "url": "https://www.bvg.de/en/tickets/all-tickets/weekly-ticket"},
        {"name": "Berlin Welcome Card 3-Day",    "type": "metro_pass",   "price": 29,  "description": "Unlimited public transit + museum discounts for 3 days",          "url": "https://www.visitberlin.de/en/berlin-welcome-card"},
    ],
    "Amsterdam": [
        {"name": "Amsterdam & Region Travel Ticket 3-Day", "type": "metro_pass", "price": 32, "description": "Unlimited GVB tram, metro, bus, and night bus for 3 days", "url": "https://www.gvb.nl/en/tickets/amsterdam-travel-ticket"},
        {"name": "OV-chipkaart",                 "type": "transit_card", "price": 8,   "description": "Rechargeable card for all Dutch public transport",                 "url": "https://www.ov-chipkaart.nl/"},
    ],
    "Rome": [
        {"name": "Rome 72-Hour Pass",            "type": "metro_pass",   "price": 18,  "description": "Unlimited metro, buses, and trams in Rome for 72 hours",          "url": "https://www.atac.roma.it/en/"},
        {"name": "Rome 48-Hour Pass",            "type": "metro_pass",   "price": 12,  "description": "Unlimited metro, buses, and trams in Rome for 48 hours",          "url": "https://www.atac.roma.it/en/"},
    ],
    "Madrid": [
        {"name": "Madrid Tourist Travel Pass 7-Day", "type": "metro_pass", "price": 35, "description": "Unlimited metro, bus, and commuter rail Zone A for 7 days",      "url": "https://www.metromadrid.es/en/tickets"},
    ],
    "Barcelona": [
        {"name": "Hola Barcelona 5-Day Pass",    "type": "metro_pass",   "price": 48,  "description": "Unlimited public transport including Aerobus and airport rail",   "url": "https://www.holabarcelona.com"},
        {"name": "T-Casual 10-Trip Card",        "type": "transit_card", "price": 12,  "description": "10-trip card for metro, buses, and trams in Zone 1",              "url": "https://www.tmb.cat/en/barcelona-transport/t-casual"},
    ],
    "New York": [
        {"name": "7-Day Unlimited MetroCard",    "type": "metro_pass",   "price": 34,  "description": "Unlimited NYC subway and local bus rides for 7 days",             "url": "https://new.mta.info/fares"},
        {"name": "30-Day Unlimited MetroCard",   "type": "metro_pass",   "price": 132, "description": "Unlimited NYC subway and local bus rides for 30 days",            "url": "https://new.mta.info/fares"},
    ],
    "Chicago": [
        {"name": "3-Day Unlimited Ride Pass",    "type": "metro_pass",   "price": 20,  "description": "Unlimited CTA 'L' train and bus rides for 3 days",               "url": "https://www.transitchicago.com/fares/"},
        {"name": "7-Day Unlimited Ride Pass",    "type": "metro_pass",   "price": 28,  "description": "Unlimited CTA 'L' train and bus rides for 7 days",               "url": "https://www.transitchicago.com/fares/"},
    ],
    "Boston": [
        {"name": "7-Day LinkPass",               "type": "metro_pass",   "price": 22,  "description": "Unlimited MBTA subway, bus, and commuter rail Zone 1A for 7 days","url": "https://www.mbta.com/fares/charliecard"},
    ],
    "Washington": [
        {"name": "7-Day Short-Trip SmarTrip Pass","type": "metro_pass",  "price": 38,  "description": "Unlimited WMATA Metro rail and bus rides up to $3.85/trip for 7 days", "url": "https://www.wmata.com/fares/"},
    ],
    "San Francisco": [
        {"name": "Muni 7-Day Passport",          "type": "metro_pass",   "price": 23,  "description": "Unlimited Muni bus and metro rides for 7 days",                   "url": "https://www.sfmta.com/fares/muni-passports"},
        {"name": "Clipper Card",                 "type": "transit_card", "price": 3,   "description": "Reloadable card for BART, Muni, and other Bay Area transit",      "url": "https://www.clippercard.com/ClipperWeb/"},
    ],
    "Seattle": [
        {"name": "ORCA Card",                    "type": "transit_card", "price": 3,   "description": "Reloadable card for Link Light Rail, buses, and ferries",         "url": "https://www.orcacard.com/"},
    ],
    "Toronto": [
        {"name": "PRESTO Day Pass",              "type": "day_pass",     "price": 10,  "description": "Unlimited TTC subway, bus, and streetcar rides for one day",      "url": "https://www.ttc.ca/fares-and-passes"},
        {"name": "PRESTO Card",                  "type": "transit_card", "price": 6,   "description": "Reloadable card for TTC with discounted per-ride fares",           "url": "https://www.prestocard.ca/en"},
    ],
    "Vancouver": [
        {"name": "TransLink DayPass",            "type": "day_pass",     "price": 11,  "description": "Unlimited travel on SkyTrain, buses, and SeaBus for one day",     "url": "https://www.translink.ca/transit-fares/transit-fare-options/daypass"},
        {"name": "Compass Card",                 "type": "transit_card", "price": 6,   "description": "Reloadable card for TransLink with tap-to-pay fares",              "url": "https://www.compasscard.ca/"},
    ],
    "Montreal": [
        {"name": "STM 3-Day Tourist Pass",       "type": "metro_pass",   "price": 19,  "description": "Unlimited STM metro and bus rides for 3 consecutive days",        "url": "https://www.stm.info/en/info/fares/tourist"},
        {"name": "STM Weekly Pass",              "type": "metro_pass",   "price": 29,  "description": "Unlimited STM metro and bus rides for 7 days",                    "url": "https://www.stm.info/en/info/fares"},
    ],
    "Singapore": [
        {"name": "Singapore Tourist Pass 3-Day", "type": "transit_card", "price": 20,  "description": "Unlimited travel on MRT, LRT, and public buses for 3 days",      "url": "https://thesingaporetouristpass.com.sg"},
    ],
    "Hong Kong": [
        {"name": "Airport Express Tourist Octopus", "type": "transit_card", "price": 16, "description": "Octopus card with airport express bonus + unlimited MTR/bus",    "url": "https://www.mtr.com.hk/en/customer/tickets/index.html"},
    ],
    "Seoul": [
        {"name": "T-money Card",                 "type": "transit_card", "price": 3,   "description": "Rechargeable card for subway, buses, and taxis in Seoul",         "url": "https://www.t-money.co.kr/eng/"},
        {"name": "Discover Seoul Pass 72-Hour",  "type": "metro_pass",   "price": 55,  "description": "Unlimited transport + free entry to 30+ attractions for 72 hours","url": "https://www.discoverseoulpass.com/"},
    ],
    "Dubai": [
        {"name": "Nol Red Ticket",               "type": "transit_card", "price": 3,   "description": "Pay-per-ride card for Dubai Metro, tram, and buses",              "url": "https://www.rta.ae/wps/portal/rta/ae/public-transport"},
        {"name": "Nol Silver Card",              "type": "transit_card", "price": 5,   "description": "Rechargeable card for all RTA public transport",                  "url": "https://www.rta.ae/wps/portal/rta/ae/public-transport"},
    ],
    # ── Chinese cities — metro day passes ~2-3 CNY/¥ ≈ $0.40-1 USD per trip ──
    "Beijing": [
        {"name": "Beijing Subway Day Pass",      "type": "day_pass",     "price": 4,   "description": "Unlimited Beijing subway rides for one day (¥28 CNY)",            "url": "https://www.bjsubway.com/en/"},
        {"name": "Beijing Transit IC Card",      "type": "transit_card", "price": 3,   "description": "Rechargeable card for subway and buses, flat ¥3 CNY per ride",    "url": "https://www.bjsubway.com/en/"},
    ],
    "Shanghai": [
        {"name": "Shanghai Metro Day Pass",      "type": "day_pass",     "price": 4,   "description": "Unlimited Shanghai Metro rides for one day (¥28 CNY)",            "url": "https://www.shmetro.com/"},
        {"name": "Shanghai Public Transportation Card", "type": "transit_card", "price": 3, "description": "Rechargeable card for metro and buses in Shanghai",           "url": "https://www.shmetro.com/"},
    ],
    "Chengdu": [
        {"name": "Chengdu Metro Day Pass",       "type": "day_pass",     "price": 3,   "description": "Unlimited Chengdu Metro rides for one day (¥20 CNY)",            "url": "https://www.cdmetro.cn/"},
        {"name": "Chengdu Transit Card",         "type": "transit_card", "price": 2,   "description": "Rechargeable card for Chengdu Metro and buses, ¥2 CNY per ride", "url": "https://www.cdmetro.cn/"},
    ],
    "Chongqing": [
        {"name": "Chongqing Metro Day Pass",     "type": "day_pass",     "price": 3,   "description": "Unlimited Chongqing Rail Transit rides for one day (¥20 CNY)",   "url": "https://www.cqmetro.cn/"},
        {"name": "Chongqing Transit Card",       "type": "transit_card", "price": 2,   "description": "Rechargeable card for Chongqing metro and buses, ¥2 CNY per ride","url": "https://www.cqmetro.cn/"},
    ],
    "Guangzhou": [
        {"name": "Guangzhou Metro Day Pass",     "type": "day_pass",     "price": 4,   "description": "Unlimited Guangzhou Metro rides for one day (¥26 CNY)",           "url": "https://www.gzmtr.com/"},
        {"name": "Yang Cheng Tong Card",         "type": "transit_card", "price": 3,   "description": "Rechargeable card for Guangzhou Metro and buses",                 "url": "https://www.gzmtr.com/"},
    ],
    "Shenzhen": [
        {"name": "Shenzhen Metro Day Pass",      "type": "day_pass",     "price": 4,   "description": "Unlimited Shenzhen Metro rides for one day (¥26 CNY)",            "url": "https://www.szmc.net/"},
        {"name": "Shenzhen Tong Card",           "type": "transit_card", "price": 3,   "description": "Rechargeable card for Shenzhen Metro, buses, and taxis",          "url": "https://www.szmc.net/"},
    ],
    "Xi'an": [
        {"name": "Xi'an Metro Day Pass",         "type": "day_pass",     "price": 3,   "description": "Unlimited Xi'an Metro rides for one day (¥20 CNY)",              "url": "https://www.xianmetro.com/"},
        {"name": "Xi'an Transit Card",           "type": "transit_card", "price": 2,   "description": "Rechargeable card for Xi'an Metro and buses",                     "url": "https://www.xianmetro.com/"},
    ],
    "Hangzhou": [
        {"name": "Hangzhou Metro Day Pass",      "type": "day_pass",     "price": 3,   "description": "Unlimited Hangzhou Metro rides for one day (¥20 CNY)",            "url": "https://www.hzmetro.com/"},
    ],
    "Wuhan": [
        {"name": "Wuhan Metro Day Pass",         "type": "day_pass",     "price": 3,   "description": "Unlimited Wuhan Metro rides for one day (¥20 CNY)",               "url": "https://www.whmetro.com/"},
    ],
}

# ── City name normalization for curated lookup ────────────────
# Maps lowercase variants → canonical key in TRANSIT_OPTIONS
_CITY_ALIASES = {
    "new york city": "New York",
    "nyc":           "New York",
    "xian":          "Xi'an",
    "xi an":         "Xi'an",
    "washington dc": "Washington",
    "washington d.c.": "Washington",
    "dc":            "Washington",
    "sf":            "San Francisco",
}


def _normalize_city(city: str) -> str:
    """Return the canonical city name for curated data lookup."""
    key = city.strip().lower()
    return _CITY_ALIASES.get(key, city.strip().title())


# ── Public interface: Transit ─────────────────────────────────

def search_transit(city: str, days_in_city: int = 7) -> list[dict]:
    """
    Return the best transit pass option for a city.

    Returned fields per result:
      name            — pass name
      pass_duration_days — days covered by one pass
      pass_label      — e.g. "7-Day Unlimited MetroCard"
      days_in_city    — echoed back for the UI
      booking_url     — link to purchase
    """
    days_in_city = max(1, int(days_in_city))
    raw: list[dict] = []

    canonical_city = _normalize_city(city)

    # 1. Try SerpAPI — but ONLY use results that pass quality checks
    if Config.SERPAPI_KEY:
        try:
            serpapi_results = _search_serpapi_transit(city)
            # Filter: require price in (0, 80] USD — anything above $80/pass is almost
            # certainly a monthly/annual price or a parsing error (the most expensive
            # tourist transit pass in the world is under $80/pass). Also reject
            # question-titled results (Quora-style) and junk domains.
            quality = [
                r for r in serpapi_results
                if 0 < r.get("price", 0) <= 80
                and r.get("name", "")
                and not r["name"].lower().startswith("what ")
                and not r["name"].lower().startswith("how ")
                and not r["name"].lower().startswith("why ")
                and not r["name"].lower().startswith("where ")
                and not _is_junk_url(r.get("booking_url", ""))
            ]
            if quality:
                raw = quality
                logger.info("SerpAPI transit (quality-filtered): %d results for %s", len(raw), city)
            else:
                logger.info("SerpAPI transit returned no quality results for %s — using curated", city)
        except Exception:
            logger.exception("SerpAPI transit failed for %s", city)

    # 2. Curated fallback — always used when SerpAPI gives nothing useful
    if not raw:
        options = TRANSIT_OPTIONS.get(canonical_city, [])
        if options:
            raw = [
                {**o, "price": o.get("price", 0), "currency_code": "USD", "currency_symbol": "$",
                 "booking_url": o.get("booking_url", o.get("url", ""))}
                for o in options
            ]
            logger.info("Curated transit data for %s (%d options)", canonical_city, len(raw))

    # 3. Nothing found
    if not raw:
        logger.info("No transit data for %s — skipping", city)
        return []

    # Remove entries that have no price AND no URL (truly useless)
    raw = [r for r in raw if r.get("price", 0) > 0 or r.get("booking_url")]

    # Ensure every result has a booking_url from our reference table
    city_lower = canonical_city.strip().lower()
    fallback_url = TRANSIT_REFERENCE_LINKS.get(city_lower, "")
    for r in raw:
        if not r.get("booking_url") and fallback_url:
            r["booking_url"] = fallback_url
        # If booking_url is a junk domain, replace it with the reference link
        if r.get("booking_url") and _is_junk_url(r["booking_url"]) and fallback_url:
            r["booking_url"] = fallback_url

    # Force all prices to USD
    for r in raw:
        cc = r.get("currency_code", "USD")
        if cc != "USD" and r.get("price", 0) > 0:
            r["price"] = _to_usd(r["price"], cc)
            r["currency_code"] = "USD"
            r["currency_symbol"] = "$"

    # Sanity-cap: discard any result whose per-pass price is implausibly high.
    # If we have curated data for this city, prefer it over anything above $80.
    raw_after_cap = [r for r in raw if r.get("price", 0) <= 80 or r.get("price", 0) == 0]
    curated_exists = bool(TRANSIT_OPTIONS.get(canonical_city))
    if not raw_after_cap and curated_exists:
        # All SerpAPI results were implausible — fall through to curated below
        raw = []
    elif raw_after_cap:
        raw = raw_after_cap
    # (if no curated data exists, keep the original raw so we at least have something)

    # Re-apply curated fallback if SerpAPI was wiped by the sanity cap
    if not raw:
        options = TRANSIT_OPTIONS.get(canonical_city, [])
        if options:
            raw = [
                {**o, "price": o.get("price", 0), "currency_code": "USD", "currency_symbol": "$",
                 "booking_url": o.get("booking_url", o.get("url", ""))}
                for o in options
            ]
            logger.info("Post-cap curated fallback for %s (%d options)", canonical_city, len(raw))

    if not raw:
        return []

    # If we still have zero-price entries, try to fill from curated estimates
    curated_options = TRANSIT_OPTIONS.get(canonical_city, [])
    for r in raw:
        if r.get("price", 0) <= 0 and curated_options:
            # Use the cheapest curated option's price as a best-guess estimate
            cheapest = min(curated_options, key=lambda o: o.get("price", 999))
            r["price"] = cheapest.get("price", 0)
            r["price_is_estimate"] = True
            logger.info("Applied curated price estimate ($%.2f) to '%s' for %s",
                        r["price"], r.get("name", ""), city)

    # Remove anything still at $0 with no URL
    raw = [r for r in raw if r.get("price", 0) > 0 or r.get("booking_url")]
    if not raw:
        return []

    best = _pick_best_pass(raw, days_in_city)
    enriched = _enrich_with_quantity(best, days_in_city)

    if not enriched.get("booking_url") and fallback_url:
        enriched["booking_url"] = fallback_url

    logger.info(
        "Transit %s (%dd): %s",
        city, days_in_city, enriched["name"],
    )

    return [enriched]


# ── SerpAPI transit search ─────────────────────────────────────

def _search_serpapi_transit(city: str) -> list[dict]:
    if not Config.SERPAPI_KEY:
        raise ValueError("SERPAPI_KEY not set")

    params = {
        "engine": "google",
        "q": f"{city} metro transit pass tourist card price",
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

    # Answer box first — most reliable
    ab = data.get("answer_box", {})
    if ab:
        at = ab.get("title", "") or ab.get("answer", "")
        as_ = ab.get("snippet", "") or ab.get("description", "")
        al = ab.get("link", "")
        if at and any(kw in (at + as_).lower() for kw in ["transit", "pass", "card", "metro", "subway"]):
            if not _is_junk_url(al):
                pi = _parse_transit_result(at, as_, al, city)
                if pi:
                    results.insert(0, pi)

    for item in data.get("organic_results", [])[:8]:
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        link = item.get("link", "")

        # Skip junk domains immediately
        if _is_junk_url(link):
            continue

        # Skip titles that look like questions (these are Quora/forum titles)
        if re.match(r'^(what|how|why|where|when|is|are|does|do)\b', title.strip(), re.IGNORECASE):
            continue

        if not any(kw in (title + snippet).lower() for kw in transit_keywords):
            continue

        pi = _parse_transit_result(title, snippet, link, city)
        if pi:
            results.append(pi)
        elif link:
            fi = _fallback_transit_result(title, snippet, link, city)
            if fi:
                results.append(fi)

    # Deduplicate by name
    seen, unique = set(), []
    for r in results:
        k = r["name"].lower()[:30]
        if k not in seen:
            seen.add(k)
            unique.append(r)

    # Normalize to USD
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
                    price = c
                    break
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
    for suffix in [" - Google Search", " | Google Maps", " - Wikipedia", " - Rome2Rio"]:
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
    Priority: provided link (if not a Google search URL and not a junk domain)
              → curated reference link.
    """
    link = (link or "").strip()
    if (link
            and link.startswith("http")
            and "google.com/search" not in link
            and not _is_junk_url(link)):
        return link
    city_lower = city.strip().lower()
    return TRANSIT_REFERENCE_LINKS.get(city_lower, "")


# ── Pass duration & quantity logic ────────────────────────────

_UNLIMITED_DURATION = 999


def _detect_pass_duration(name: str, pass_type: str) -> int:
    """
    Infer how many days a single pass covers from its name and type.
    Returns _UNLIMITED_DURATION (999) for rechargeable top-up cards.
    """
    lower = name.lower()

    # Rechargeable cards — single purchase covers entire stay
    if pass_type == "transit_card" or any(k in lower for k in
            ["ic card", "oyster", "suica", "pasmo", "t-money", "octopus", "presto",
             "compass card", "orca card", "clipper card", "nol card", "opal card",
             "rechargeable", "top-up", "topup", "pay-as-you-go", "payg",
             "yang cheng tong", "public transportation card", "transit card",
             "transit ic", "ic card"]):
        return _UNLIMITED_DURATION

    # Named durations
    for n, days in [("30-day", 30), ("monthly", 30), ("week", 7), ("7-day", 7),
                    ("72-hour", 3), ("3-day", 3), ("48-hour", 2), ("2-day", 2),
                    ("24-hour", 1), ("1-day", 1), ("day pass", 1), ("daily", 1)]:
        if n in lower:
            return days

    # Pass type defaults
    defaults = {"rail_pass": 7, "metro_pass": 3, "day_pass": 1, "transit_card": _UNLIMITED_DURATION}
    return defaults.get(pass_type, 1)


def _calculate_quantity(days_in_city: int, pass_duration_days: int) -> int:
    """How many passes are needed to cover days_in_city?"""
    if pass_duration_days >= _UNLIMITED_DURATION:
        return 1
    return math.ceil(days_in_city / pass_duration_days)


def _enrich_with_quantity(option: dict, days_in_city: int) -> dict:
    """Add pass_label to a transit option."""
    name = option.get("name", "Transit Pass")
    pass_type = option.get("type", "transit_card")

    duration = _detect_pass_duration(name, pass_type)
    actual_duration = duration if duration < _UNLIMITED_DURATION else days_in_city

    return {
        **option,
        "pass_duration_days": actual_duration,
        "pass_label":        name,
        "days_in_city":      days_in_city,
        "booking_url":       option.get("booking_url", option.get("url", "")),
        "currency_code":     "USD",
        "currency_symbol":   "$",
    }


def _pick_best_pass(options: list[dict], days_in_city: int) -> dict:
    """
    Pick the option with the lowest total_price for the given stay length.
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
    if best.get("price", 0) <= 0:
        return options[0]
    return best