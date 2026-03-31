"""
Flight search service — Google Flights via fast-flights package.
No API key required. Scrapes Google Flights using protobuf URL encoding.

Package: https://pypi.org/project/fast-flights/
"""

import logging
import re
import urllib.parse
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Airline logo helper ────────────────────────────────────────

def _airline_logo(code: str) -> str:
    if not code:
        return ""
    return f"https://www.gstatic.com/flights/airline_logos/70px/{code.upper()}.png"


def _parse_duration_str(duration_str: str) -> int:
    """
    Parse a human-readable duration string like '5 hr 30 min', '2 hr', '45 min'
    into total minutes.
    """
    if not duration_str:
        return 0

    hours = 0
    minutes = 0

    hr_match = re.search(r'(\d+)\s*hr', duration_str, re.IGNORECASE)
    min_match = re.search(r'(\d+)\s*min', duration_str, re.IGNORECASE)

    if hr_match:
        hours = int(hr_match.group(1))
    if min_match:
        minutes = int(min_match.group(1))

    return (hours * 60) + minutes


def _extract_airline_code(airline_name: str) -> str:
    """
    Try to extract an IATA airline code from the flight name string.
    fast-flights returns names like 'Delta Air Lines', 'United Airlines', etc.
    We maintain a mapping for common airlines.
    """
    airline_codes = {
        "delta": "DL", "united": "UA", "american": "AA",
        "southwest": "WN", "jetblue": "B6", "alaska": "AS",
        "spirit": "NK", "frontier": "F9", "hawaiian": "HA",
        "air canada": "AC", "westjet": "WS",
        "british airways": "BA", "lufthansa": "LH",
        "air france": "AF", "klm": "KL", "emirates": "EK",
        "qatar": "QR", "turkish": "TK", "singapore": "SQ",
        "cathay pacific": "CX", "cathay": "CX",
        "japan airlines": "JL", "jal": "JL",
        "ana": "NH", "all nippon": "NH",
        "korean air": "KE", "asiana": "OZ",
        "eva air": "BR", "china airlines": "CI",
        "china eastern": "MU", "china southern": "CZ",
        "air china": "CA", "hainan": "HU",
        "qantas": "QF", "virgin atlantic": "VS",
        "virgin australia": "VA", "air new zealand": "NZ",
        "swiss": "LX", "austrian": "OS",
        "iberia": "IB", "tap": "TP", "finnair": "AY",
        "sas": "SK", "norwegian": "DY", "icelandair": "FI",
        "aer lingus": "EI", "ryanair": "FR", "easyjet": "U2",
        "wizz air": "W6", "vueling": "VY",
        "aeromexico": "AM", "latam": "LA", "avianca": "AV",
        "copa": "CM", "azul": "AD", "gol": "G3",
        "etihad": "EY", "saudia": "SV", "oman air": "WY",
        "thai": "TG", "malaysia airlines": "MH",
        "garuda": "GA", "philippine airlines": "PR",
        "cebu pacific": "5J", "airasia": "AK",
        "scoot": "TR", "jetstar": "JQ",
        "indigo": "6E", "air india": "AI",
        "starlux": "JX", "peach": "MM",
        "zipair": "ZG", "flair": "F8",
        "sun country": "SY", "allegiant": "G4",
        "breeze": "MX", "play": "OG",
        "condor": "DE", "eurowings": "EW",
        "lot": "LO", "tarom": "RO",
        "aegean": "A3", "olympic": "OA",
        "royal air maroc": "AT", "ethiopian": "ET",
        "kenya airways": "KQ", "south african": "SA",
    }

    name_lower = airline_name.lower().strip()
    for key, code in airline_codes.items():
        if key in name_lower:
            return code

    return ""


def _google_flights_url(origin: str, destination: str, date: str) -> str:
    """Build a Google Flights search URL for booking."""
    query = urllib.parse.quote(f"Flights from {origin} to {destination} on {date}")
    return f"https://www.google.com/travel/flights?q={query}"


def _search_fast_flights(
    origin: str,
    destination: str,
    departure_date: str,
    cabin_class: str,
    passengers: int,
    max_results: int,
    exclude_airports: list[str] | None,
    sort_by: str = "best",
) -> list[dict]:
    """
    Search flights using the fast-flights package (Google Flights scraper).
    Returns results in the same format as the old Duffel integration.
    """
    from fast_flights import FlightData, Passengers, get_flights

    seat_map = {
        "economy": "economy",
        "premium_economy": "premium-economy",
        "business": "business",
        "first": "first",
    }

    result = get_flights(
        flight_data=[
            FlightData(
                date=departure_date,
                from_airport=origin,
                to_airport=destination,
            )
        ],
        trip="one-way",
        seat=seat_map.get(cabin_class, "economy"),
        passengers=Passengers(adults=passengers),
    )

    if not result or not result.flights:
        logger.warning("fast-flights returned no results for %s → %s on %s", origin, destination, departure_date)
        return []

    logger.info("fast-flights returned %d raw results for %s → %s", len(result.flights), origin, destination)
    booking_url = _google_flights_url(origin, destination, departure_date)
    exclude = set(a.upper() for a in (exclude_airports or []))
    results = []

    for i, flight in enumerate(result.flights):
        # Parse airline info from the flight name
        airline_name = (flight.name or "").strip()
        airline_code = _extract_airline_code(airline_name) if airline_name else ""

        # Skip truly empty results (no name AND no price)
        if not airline_name and not flight.price:
            logger.debug("Skipping flight %d: completely empty result", i)
            continue

        if not airline_name:
            airline_name = "Airline"

        # Parse price
        price = 0
        if flight.price:
            price_str = str(flight.price)
            price_clean = re.sub(r'[^\d.]', '', price_str)
            try:
                price = float(price_clean)
            except ValueError:
                price = 0

        total_price = price * passengers

        # Parse duration
        total_duration = _parse_duration_str(flight.duration or "")

        # Parse stops
        num_stops = flight.stops or 0
        if isinstance(num_stops, str):
            if "nonstop" in num_stops.lower() or num_stops == "0":
                num_stops = 0
            else:
                stop_match = re.search(r'(\d+)', num_stops)
                num_stops = int(stop_match.group(1)) if stop_match else 0

        is_nonstop = num_stops == 0

        # Parse departure and arrival times
        dep_time = flight.departure or ""
        arr_time = flight.arrival or ""

        # Don't fabricate flight numbers — fast-flights doesn't provide them.
        # Use the airline name as the identifier shown in the UI detail view.
        segments = [{
            "flight_number": airline_name,
            "origin": origin,
            "destination": destination,
            "departure_time": dep_time,
            "arrival_time": arr_time,
            "duration_minutes": total_duration,
            "aircraft": "",
        }]

        # Build layover info if there are stops
        layovers = []
        if num_stops > 0:
            layovers.append({
                "airport": "—",
                "airport_name": f"{num_stops} stop(s)",
                "city": "—",
                "duration_minutes": 0,
            })

        results.append({
            "id": f"ff_{origin}_{destination}_{i}",
            "airline": {
                "code": airline_code,
                "name": airline_name,
                "logo": _airline_logo(airline_code) if airline_code else "",
            },
            "segments": segments,
            "layovers": layovers,
            "is_nonstop": is_nonstop,
            "total_duration_minutes": total_duration,
            "cabin_class": cabin_class,
            "price_per_person": round(price, 2),
            "total_price": round(total_price, 2),
            "passengers": passengers,
            "departure_date": departure_date,
            "booking_url": booking_url,
        })

    # ── Smart ranking: balance price and duration ──────────────────
    # Filter out duration outliers (e.g. 33hr flight when 14hr exists)
    # unless the user specifically asked for cheapest-only via sort_by.

    if sort_by != "cheapest" and len(results) > 1:
        results = _rank_by_value(results)
    else:
        # Pure price sort for "cheapest" mode
        results.sort(key=lambda x: (x["total_price"] == 0, x["total_price"]))

    logger.info("Returning %d flights (from %d raw, sort=%s)", len(results[:max_results]), len(result.flights), sort_by)
    return results[:max_results]


def _rank_by_value(flights: list[dict]) -> list[dict]:
    """
    Rank flights by a combined value score that balances price and duration.
    Filters out extreme-duration outliers first, then scores the rest.

    Logic:
    1. Find the shortest flight duration among all results.
    2. Remove flights whose duration exceeds 1.8x the shortest (outliers).
       - But never remove ALL flights — keep at least the shortest.
    3. Score remaining flights: 60% price rank + 40% duration rank.
       Lowest score = best value.
    """
    # Separate zero-price (bad data) from valid flights
    valid = [f for f in flights if f["total_price"] > 0]
    zero_price = [f for f in flights if f["total_price"] == 0]

    if not valid:
        return flights  # nothing to rank

    # Step 1: find shortest duration (ignoring 0-duration which means unknown)
    durations = [f["total_duration_minutes"] for f in valid if f["total_duration_minutes"] > 0]
    if durations:
        shortest = min(durations)
        # Step 2: filter outliers — anything over 1.8x the shortest is unreasonable
        max_reasonable = shortest * 1.8

        reasonable = [f for f in valid
                      if f["total_duration_minutes"] == 0  # unknown duration — keep it
                      or f["total_duration_minutes"] <= max_reasonable]

        # Safety net: if filtering removed everything, keep the top 3 shortest
        if not reasonable:
            reasonable = sorted(valid, key=lambda x: x["total_duration_minutes"])[:3]

        valid = reasonable

    # Step 3: score by combined price + duration rank
    n = len(valid)
    if n == 1:
        return valid + zero_price

    # Rank by price (lower = better)
    by_price = sorted(range(n), key=lambda i: valid[i]["total_price"])
    price_rank = [0] * n
    for rank, idx in enumerate(by_price):
        price_rank[idx] = rank

    # Rank by duration (lower = better), treat 0 as worst
    by_duration = sorted(range(n), key=lambda i: (
        valid[i]["total_duration_minutes"] == 0,  # unknown last
        valid[i]["total_duration_minutes"]
    ))
    duration_rank = [0] * n
    for rank, idx in enumerate(by_duration):
        duration_rank[idx] = rank

    # Combined score: 60% price, 40% duration
    scores = [0.6 * price_rank[i] + 0.4 * duration_rank[i] for i in range(n)]

    # Sort by score (lowest = best value)
    ranked = sorted(zip(scores, valid), key=lambda x: x[0])
    return [f for _, f in ranked] + zero_price


def _mock_flights(origin: str, destination: str, date: str, passengers: int) -> list[dict]:
    query = urllib.parse.quote(f"Flights from {origin} to {destination} on {date}")
    return [{
        "id": "mock_flight_1",
        "airline": {"code": "DL", "name": "Delta Air Lines", "logo": _airline_logo("DL")},
        "segments": [{
            "flight_number": "DL102", "origin": origin, "destination": destination,
            "departure_time": "08:00", "arrival_time": "11:30", "duration_minutes": 210, "aircraft": "Boeing 737"
        }],
        "layovers": [], "is_nonstop": True, "total_duration_minutes": 210,
        "cabin_class": "economy", "price_per_person": 345.0, "total_price": 345.0 * passengers,
        "passengers": passengers, "departure_date": date,
        "booking_url": f"https://www.google.com/travel/flights?q={query}"
    }]


def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    cabin_class: str = "economy",
    passengers: int = 1,
    max_results: int = 5,
    exclude_airports: list[str] | None = None,
    sort_by: str = "best",
) -> list[dict]:
    """
    Search for flights using fast-flights (Google Flights scraper) or fallback mock data.

    sort_by:
      "best"     — (default) balance price + duration, filter out outlier durations
      "cheapest" — pure price sort, no duration filtering
    """
    origin = origin.upper()
    destination = destination.upper()

    try:
        return _search_fast_flights(
            origin, destination, departure_date,
            cabin_class, passengers, max_results, exclude_airports,
            sort_by,
        )
    except Exception:
        logger.exception("fast-flights search failed, falling back to mock data.")

    logger.warning("Using mock flight data.")
    return _mock_flights(origin, destination, departure_date, passengers)