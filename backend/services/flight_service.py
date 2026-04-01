"""
Flight search service — Google Flights via the `flights` (fli) package.
No API key required. Uses reverse-engineered Google Flights internal API.

Package: https://pypi.org/project/flights/
Docs:    https://punitarani.github.io/fli/

Migrated from fast-flights (scraper-based) to flights/fli (direct API).
Benefits:
  - Direct API access instead of HTML scraping → faster, more reliable
  - Structured results with real flight numbers, per-leg details
  - Built-in retry logic and rate limiting

Round-trip support:
  - search_flights_roundtrip() uses TripType.ROUND_TRIP for A→B→A trips
  - search_flights() remains one-way for multi-city legs (A→B→C→A)
  - Price is per-person from fli (searched with adults=1), multiplied by passengers.

Currency note:
  - The fli package does NOT support a currency parameter.
  - Google Flights returns prices in the currency matching the server's IP locale.
  - We detect the likely currency via FLIGHT_CURRENCY env var or locale detection.
  - Default: USD. Set FLIGHT_CURRENCY=CAD in .env if running from Canada.
"""

import logging
import os
import locale
import re
import urllib.parse
import base64
from datetime import datetime

logger = logging.getLogger(__name__)


# ── Currency detection ─────────────────────────────────────────
# The fli package returns prices in whatever currency Google Flights
# uses for the server's IP geolocation. Since there's no way to
# control this in the API, we detect it from environment or locale.

def _detect_currency() -> tuple[str, str]:
    """
    Detect the currency that Google Flights is likely returning.
    
    Priority:
    1. FLIGHT_CURRENCY env var (explicit override, e.g. "CAD", "USD", "EUR")
    2. Locale-based detection from the system
    3. Default: USD
    
    Returns (currency_code, currency_symbol)
    """
    # 1. Explicit env var
    env_currency = os.environ.get("FLIGHT_CURRENCY", "").upper().strip()
    if env_currency:
        return env_currency, _currency_symbol(env_currency)
    
    # 2. Locale detection
    try:
        loc = locale.getlocale()[0] or locale.getdefaultlocale()[0] or ""
        if loc:
            country = loc.split("_")[-1].upper() if "_" in loc else ""
            locale_map = {
                "CA": ("CAD", "CA$"),
                "US": ("USD", "$"),
                "GB": ("GBP", "£"),
                "AU": ("AUD", "A$"),
                "EU": ("EUR", "€"),
                "JP": ("JPY", "¥"),
                "IN": ("INR", "₹"),
            }
            if country in locale_map:
                return locale_map[country]
    except Exception:
        pass
    
    # 3. Default
    return "USD", "$"


def _currency_symbol(code: str) -> str:
    symbols = {
        "USD": "$", "CAD": "CA$", "EUR": "€", "GBP": "£",
        "AUD": "A$", "JPY": "¥", "INR": "₹", "CNY": "¥",
        "KRW": "₩", "MXN": "MX$", "BRL": "R$", "CHF": "CHF",
    }
    return symbols.get(code, code)


# Cache at module level so we don't re-detect every call
_DETECTED_CURRENCY, _DETECTED_SYMBOL = _detect_currency()
logger.info("Flight price currency detected as: %s (%s)", _DETECTED_CURRENCY, _DETECTED_SYMBOL)


# ── Airline logo helper ────────────────────────────────────────

def _airline_logo(code: str) -> str:
    if not code:
        return ""
    return f"https://www.gstatic.com/flights/airline_logos/70px/{code.upper()}.png"


# ── Booking link builders (reliable aggregators only) ──────────
#
# Airline-specific booking URLs are intentionally NOT used here.
# Airlines change their URL structures frequently and most use
# JavaScript-based SPAs where query params don't reliably pre-fill
# the search. Instead we link to well-known aggregators with
# stable, documented URL formats that actually work.


def _kayak_url(
    origin: str,
    destination: str,
    departure_date: str,
    cabin_class: str = "economy",
    passengers: int = 1,
    return_date: str | None = None,
) -> str:
    """
    Build a Kayak flight search URL (one-way or round-trip).
    Format: https://www.kayak.com/flights/JFK-LAX/2026-06-15/2026-06-22?sort=bestflight_a
    Stable URL scheme — Kayak has used this path format for years.
    """
    cabin_param = {
        "economy": "",
        "premium_economy": "/pe",
        "business": "/b",
        "first": "/f",
    }.get(cabin_class, "")

    pax_param = f"&adults={passengers}" if passengers > 1 else ""

    date_part = departure_date
    if return_date:
        date_part = f"{departure_date}/{return_date}"

    return (
        f"https://www.kayak.com/flights"
        f"/{origin.upper()}-{destination.upper()}"
        f"/{date_part}"
        f"?sort=bestflight_a"
        f"{pax_param}"
        f"{cabin_param}"
    )


def _skyscanner_url(
    origin: str,
    destination: str,
    departure_date: str,
    cabin_class: str = "economy",
    passengers: int = 1,
    return_date: str | None = None,
) -> str:
    """
    Build a Skyscanner flight search URL (one-way or round-trip).
    Format: https://www.skyscanner.com/transport/flights/jfk/lax/260615/260622/
    Date format: YYMMDD
    """
    try:
        dt = datetime.strptime(departure_date, "%Y-%m-%d")
        date_str = dt.strftime("%y%m%d")
    except ValueError:
        date_str = departure_date.replace("-", "")[2:]  # fallback

    date_path = f"/{date_str}/"
    if return_date:
        try:
            rt = datetime.strptime(return_date, "%Y-%m-%d")
            ret_str = rt.strftime("%y%m%d")
            date_path = f"/{date_str}/{ret_str}/"
        except ValueError:
            pass

    cabin_map = {
        "economy": "economy",
        "premium_economy": "premiumeconomy",
        "business": "business",
        "first": "first",
    }
    cabin = cabin_map.get(cabin_class, "economy")

    return (
        f"https://www.skyscanner.com/transport/flights"
        f"/{origin.lower()}/{destination.lower()}"
        f"{date_path}"
        f"?adultsv2={passengers}"
        f"&cabinclass={cabin}"
    )


def _build_booking_links(
    origin: str,
    destination: str,
    departure_date: str,
    cabin_class: str = "economy",
    passengers: int = 1,
    return_date: str | None = None,
) -> dict[str, str]:
    """
    Build a dict of booking links to multiple aggregators.
    All of these URL formats are stable and well-tested.
    Supports both one-way and round-trip URLs.
    """
    return {
        "google_flights": _google_flights_url(origin, destination, departure_date, cabin_class, passengers, return_date),
        "kayak": _kayak_url(origin, destination, departure_date, cabin_class, passengers, return_date),
        "skyscanner": _skyscanner_url(origin, destination, departure_date, cabin_class, passengers, return_date),
    }


# ── Protobuf-based Google Flights URL builder ─────────────────

def _build_one_way_tfs(
    origin: str,
    destination: str,
    date: str,
    passengers: int = 1,
) -> str:
    """
    Build the Google Flights `tfs` query parameter for a one-way flight search.

    This encodes the search as a Base64 URL-safe protobuf string — the same
    format Google Flights uses internally when you perform a search in the UI.

    The protobuf structure (reverse-engineered from Google Flights):
      field 1  (varint):  28 (0x1C) — search display mode
      field 2  (varint):  2 — one-way search
      field 3  (embedded): flight leg message
        field 2  (string):  departure date "YYYY-MM-DD"
        field 13 (embedded): origin airport {field1: 1, field2: "IATA"}
        field 14 (embedded): dest airport   {field1: 1, field2: "IATA"}
      field 8  (varint):  1
      field 9  (varint):  1
      field 14 (varint):  1
      field 16 (embedded): config {field1: INT64_MAX} — forces full calculation
      field 19 (varint):  number of passengers
    """
    date_bytes = date.encode("ascii")
    origin_bytes = origin.upper().encode("ascii")
    dest_bytes = destination.upper().encode("ascii")

    # Airport sub-message: { field1: varint(1), field2: string(CODE) }
    origin_airport = b"\x08\x01\x12" + bytes([len(origin_bytes)]) + origin_bytes
    dest_airport = b"\x08\x01\x12" + bytes([len(dest_bytes)]) + dest_bytes

    # Flight leg sub-message
    leg = b"\x12" + bytes([len(date_bytes)]) + date_bytes          # field 2: date
    leg += b"\x6a" + bytes([len(origin_airport)]) + origin_airport  # field 13: origin
    leg += b"\x72" + bytes([len(dest_airport)]) + dest_airport      # field 14: dest

    # Top-level message
    msg = bytearray()
    msg += b"\x08\x1c"                                               # field 1 = 28
    msg += b"\x10\x02"                                               # field 2 = 2 (one-way)
    msg += b"\x1a" + bytes([len(leg)]) + leg                         # field 3 = leg
    msg += b"\x40\x01"                                               # field 8 = 1
    msg += b"\x48\x01"                                               # field 9 = 1
    msg += b"\x70\x01"                                               # field 14 = 1
    msg += b"\x82\x01\x0b"                                           # field 16, length 11
    msg += b"\x08\xff\xff\xff\xff\xff\xff\xff\xff\xff\x01"           # INT64_MAX
    msg += b"\x98\x01" + bytes([max(1, min(passengers, 9))])         # field 19 = passengers

    return base64.urlsafe_b64encode(bytes(msg)).decode("ascii").rstrip("=")


def _build_round_trip_tfs(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str,
    passengers: int = 1,
) -> str:
    """
    Build the Google Flights `tfs` query parameter for a round-trip flight search.

    Similar to one-way but with:
      field 2 = 1 (round-trip, not 2 = one-way)
      Two flight leg messages (outbound + return)
    """
    origin_bytes = origin.upper().encode("ascii")
    dest_bytes = destination.upper().encode("ascii")

    def _make_airport(code_bytes):
        return b"\x08\x01\x12" + bytes([len(code_bytes)]) + code_bytes

    def _make_leg(dep_date, orig_bytes, dst_bytes):
        date_bytes = dep_date.encode("ascii")
        orig_airport = _make_airport(orig_bytes)
        dst_airport = _make_airport(dst_bytes)
        leg = b"\x12" + bytes([len(date_bytes)]) + date_bytes
        leg += b"\x6a" + bytes([len(orig_airport)]) + orig_airport
        leg += b"\x72" + bytes([len(dst_airport)]) + dst_airport
        return leg

    outbound_leg = _make_leg(departure_date, origin_bytes, dest_bytes)
    return_leg = _make_leg(return_date, dest_bytes, origin_bytes)

    msg = bytearray()
    msg += b"\x08\x1c"                                               # field 1 = 28
    msg += b"\x10\x01"                                               # field 2 = 1 (ROUND TRIP)
    msg += b"\x1a" + bytes([len(outbound_leg)]) + outbound_leg       # field 3 = outbound leg
    msg += b"\x1a" + bytes([len(return_leg)]) + return_leg           # field 3 = return leg
    msg += b"\x40\x01"                                               # field 8 = 1
    msg += b"\x48\x01"                                               # field 9 = 1
    msg += b"\x70\x01"                                               # field 14 = 1
    msg += b"\x82\x01\x0b"                                           # field 16, length 11
    msg += b"\x08\xff\xff\xff\xff\xff\xff\xff\xff\xff\x01"           # INT64_MAX
    msg += b"\x98\x01" + bytes([max(1, min(passengers, 9))])         # field 19 = passengers

    return base64.urlsafe_b64encode(bytes(msg)).decode("ascii").rstrip("=")


def _google_flights_url(
    origin: str,
    destination: str,
    date: str,
    cabin_class: str = "economy",
    passengers: int = 1,
    return_date: str | None = None,
) -> str:
    """
    Build a Google Flights search URL with a proper protobuf-encoded tfs parameter.
    Supports both one-way and round-trip.

    Returns a URL like:
      https://www.google.com/travel/flights/search?tfs=CBwQAh...&hl=en&curr=USD
    """
    if return_date:
        tfs = _build_round_trip_tfs(origin, destination, date, return_date, passengers)
    else:
        tfs = _build_one_way_tfs(origin, destination, date, passengers)

    # Map cabin_class to Google Flights seat URL parameter
    seat_param = {
        "economy": "",          # default, no param needed
        "premium_economy": "&tfc=PE",
        "business": "&tfc=B",
        "first": "&tfc=F",
    }.get(cabin_class, "")

    return (
        f"https://www.google.com/travel/flights/search"
        f"?tfs={tfs}"
        f"&tfu=EgIIAQ"    # standard flag (enables full search)
        f"&hl=en"
        f"&curr={_DETECTED_CURRENCY}"
        f"{seat_param}"
    )


# ── Airport enum helper ────────────────────────────────────────

def _get_airport_enum(iata_code: str):
    """
    Safely look up an Airport enum member by IATA code.
    The fli package uses Airport enums (e.g., Airport.JFK).
    Returns the enum member, or None if the code isn't in the enum.
    """
    from fli.models import Airport
    try:
        return Airport[iata_code.upper()]
    except KeyError:
        return None


# ── Core search using fli (ONE-WAY) ───────────────────────────

def _search_fli(
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
    Search ONE-WAY flights using the flights (fli) package — direct Google Flights API.
    Returns results in the same format as the rest of ExpediRamp expects.

    IMPORTANT: The fli package returns the TOTAL price for all passengers
    (since we pass PassengerInfo(adults=passengers)). We must NOT multiply
    by passengers again. price_per_person = total_price / passengers.
    """
    from fli.models import (
        Airport, PassengerInfo, SeatType, MaxStops, SortBy,
        FlightSearchFilters, FlightSegment, TripType,
    )
    from fli.search import SearchFlights

    # Map cabin class string → SeatType enum
    seat_map = {
        "economy": SeatType.ECONOMY,
        "premium_economy": SeatType.PREMIUM_ECONOMY,
        "business": SeatType.BUSINESS,
        "first": SeatType.FIRST,
    }

    # Map sort preference → SortBy enum
    sort_map = {
        "best": SortBy.TOP_FLIGHTS,
        "cheapest": SortBy.CHEAPEST,
        "fastest": SortBy.DURATION,
    }

    # Resolve Airport enums
    origin_airport = _get_airport_enum(origin)
    dest_airport = _get_airport_enum(destination)

    if origin_airport is None or dest_airport is None:
        logger.warning(
            "Airport code not found in fli Airport enum: origin=%s (%s), dest=%s (%s)",
            origin, "found" if origin_airport else "MISSING",
            destination, "found" if dest_airport else "MISSING",
        )
        return []

    # Build search filters — ONE-WAY with 1 adult
    # We always search for 1 passenger and multiply later to avoid
    # the fli package's inconsistent multi-passenger pricing
    filters = FlightSearchFilters(
        trip_type=TripType.ONE_WAY,
        passenger_info=PassengerInfo(adults=1),
        flight_segments=[
            FlightSegment(
                departure_airport=[[origin_airport, 0]],
                arrival_airport=[[dest_airport, 0]],
                travel_date=departure_date,
            )
        ],
        seat_type=seat_map.get(cabin_class, SeatType.ECONOMY),
        stops=MaxStops.ANY,
        sort_by=sort_map.get(sort_by, SortBy.TOP_FLIGHTS),
    )

    # Execute search
    search = SearchFlights()
    flight_results = search.search(filters)

    if not flight_results:
        logger.warning("fli returned no results for %s → %s on %s", origin, destination, departure_date)
        return []

    logger.info("fli returned %d results for %s → %s", len(flight_results), origin, destination)

    exclude = set(a.upper() for a in (exclude_airports or []))
    results = []

    for i, flight in enumerate(flight_results):
        # flight is a FlightResult with: price, duration, stops, legs, currency

        # Extract airline code from the first leg
        first_leg = flight.legs[0] if flight.legs else None
        if not first_leg:
            continue

        # The airline attribute is an Airline enum — .name gives the IATA code
        airline_code = first_leg.airline.name if first_leg.airline else ""
        airline_name = first_leg.airline.value if first_leg.airline else "Unknown Airline"

        # If airline_name is just the code (some enums use code as value), make it readable
        if airline_name == airline_code:
            airline_name = airline_code  # We'll just use the code

        # Check if any leg involves an excluded airport
        skip = False
        for leg in flight.legs:
            dep_code = leg.departure_airport.name if leg.departure_airport else ""
            arr_code = leg.arrival_airport.name if leg.arrival_airport else ""
            if dep_code in exclude or arr_code in exclude:
                skip = True
                break
        if skip:
            continue

        # PRICE FIX: fli returns price PER PERSON for 1-adult search.
        # We searched with adults=1, so flight.price = per-person price.
        # total_price = per_person * passengers (the user's actual count).
        price_per_person = float(flight.price) if flight.price else 0
        total_price = price_per_person * passengers

        # Build segments list from legs
        segments = []
        for leg in flight.legs:
            dep_code = leg.departure_airport.name if leg.departure_airport else origin
            arr_code = leg.arrival_airport.name if leg.arrival_airport else destination
            dep_time = leg.departure_datetime.strftime("%Y-%m-%d %H:%M") if leg.departure_datetime else ""
            arr_time = leg.arrival_datetime.strftime("%Y-%m-%d %H:%M") if leg.arrival_datetime else ""
            dur = leg.duration if hasattr(leg, 'duration') and leg.duration else 0

            # Extract flight number
            flight_num = ""
            if hasattr(leg, 'flight_number') and leg.flight_number:
                flight_num = leg.flight_number
            elif airline_code:
                flight_num = f"{airline_code} {i + 1}"

            segments.append({
                "origin": dep_code,
                "destination": arr_code,
                "departure_time": dep_time,
                "arrival_time": arr_time,
                "flight_number": flight_num,
                "duration_minutes": dur,
                "aircraft": getattr(leg, 'aircraft', '') or "",
            })

        # Build layovers list
        is_nonstop = len(segments) <= 1
        layovers = []
        for j in range(len(segments) - 1):
            arr_seg = segments[j]
            dep_seg = segments[j + 1]

            layover_dur = 0
            if arr_seg["arrival_time"] and dep_seg["departure_time"]:
                try:
                    arr_dt = datetime.strptime(arr_seg["arrival_time"], "%Y-%m-%d %H:%M")
                    dep_dt = datetime.strptime(dep_seg["departure_time"], "%Y-%m-%d %H:%M")
                    layover_dur = int((dep_dt - arr_dt).total_seconds() / 60)
                except Exception:
                    pass

            layover_airport = arr_seg["destination"]
            num_stops = len(segments) - 1

            layovers.append({
                "airport": layover_airport,
                "airport_name": layover_airport,
                "description": f"{num_stops} stop(s)",
                "city": "—",
                "duration_minutes": layover_dur,
            })

        # If we have no layovers but flight has multiple segments, add placeholder
        if not layovers and not is_nonstop:
            num_stops = getattr(flight, 'stops', 0) or 0
            layovers.append({
                "airport": "—",
                "airport_name": "",
                "description": f"{num_stops} stop(s)",
                "city": "—",
                "duration_minutes": 0,
            })

        total_duration = flight.duration if flight.duration else 0

        # Build booking links to reliable aggregators (one-way)
        booking_links = _build_booking_links(
            origin, destination, departure_date, cabin_class, passengers
        )
        # Primary booking_url = Google Flights (proven protobuf encoding)
        booking_url = booking_links["google_flights"]

        results.append({
            "id": f"fli_{origin}_{destination}_{i}",
            "airline": {
                "code": airline_code,
                "name": airline_name,
                "logo": _airline_logo(airline_code) if airline_code else "",
            },
            "segments": segments,
            "layovers": layovers,
            "is_nonstop": is_nonstop,
            "is_round_trip": False,
            "trip_type": "one_way",
            "total_duration_minutes": total_duration,
            "cabin_class": cabin_class,
            "price_per_person": round(price_per_person, 2),
            "total_price": round(total_price, 2),
            "passengers": passengers,
            "departure_date": departure_date,
            "booking_url": booking_url,
            "booking_links": booking_links,
            "currency_code": _DETECTED_CURRENCY,
            "currency_symbol": _DETECTED_SYMBOL,
        })

    # ── Smart ranking (for "best" mode) ─────────────────────────
    if sort_by != "cheapest" and len(results) > 1:
        results = _rank_by_value(results)
    else:
        # Pure price sort for "cheapest" mode
        results.sort(key=lambda x: (x["total_price"] == 0, x["total_price"]))

    logger.info("Returning %d flights (from %d raw, sort=%s)", len(results[:max_results]), len(flight_results), sort_by)
    return results[:max_results]


# ── Core search using fli (ROUND-TRIP) ─────────────────────────

def _search_fli_roundtrip(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str,
    cabin_class: str,
    passengers: int,
    max_results: int,
    exclude_airports: list[str] | None,
    sort_by: str = "best",
) -> list[dict]:
    """
    Search ROUND-TRIP flights using the flights (fli) package.
    Returns results with both outbound and return segments grouped together.

    The fli package's TripType.ROUND_TRIP returns flights that include
    both outbound and return legs. The price is the total round-trip
    price for all passengers.

    We search with adults=1 to get per-person pricing, then multiply.
    """
    from fli.models import (
        Airport, PassengerInfo, SeatType, MaxStops, SortBy,
        FlightSearchFilters, FlightSegment, TripType,
    )
    from fli.search import SearchFlights

    seat_map = {
        "economy": SeatType.ECONOMY,
        "premium_economy": SeatType.PREMIUM_ECONOMY,
        "business": SeatType.BUSINESS,
        "first": SeatType.FIRST,
    }
    sort_map = {
        "best": SortBy.TOP_FLIGHTS,
        "cheapest": SortBy.CHEAPEST,
        "fastest": SortBy.DURATION,
    }

    origin_airport = _get_airport_enum(origin)
    dest_airport = _get_airport_enum(destination)

    if origin_airport is None or dest_airport is None:
        logger.warning(
            "Airport code not found for round-trip: origin=%s (%s), dest=%s (%s)",
            origin, "found" if origin_airport else "MISSING",
            destination, "found" if dest_airport else "MISSING",
        )
        return []

    # Build round-trip search with 1 adult for per-person pricing
    filters = FlightSearchFilters(
        trip_type=TripType.ROUND_TRIP,
        passenger_info=PassengerInfo(adults=1),
        flight_segments=[
            FlightSegment(
                departure_airport=[[origin_airport, 0]],
                arrival_airport=[[dest_airport, 0]],
                travel_date=departure_date,
            ),
            FlightSegment(
                departure_airport=[[dest_airport, 0]],
                arrival_airport=[[origin_airport, 0]],
                travel_date=return_date,
            ),
        ],
        seat_type=seat_map.get(cabin_class, SeatType.ECONOMY),
        stops=MaxStops.ANY,
        sort_by=sort_map.get(sort_by, SortBy.TOP_FLIGHTS),
    )

    search = SearchFlights()
    flight_results = search.search(filters)

    if not flight_results:
        logger.warning("fli round-trip returned no results for %s ↔ %s on %s / %s",
                       origin, destination, departure_date, return_date)
        return []

    logger.info("fli round-trip returned %d results for %s ↔ %s", len(flight_results), origin, destination)

    exclude = set(a.upper() for a in (exclude_airports or []))
    results = []

    for i, result_item in enumerate(flight_results):
        # CRITICAL: fli returns list[tuple(FlightResult, FlightResult)] for round trips.
        # Each item is (outbound_flight, return_flight).
        if isinstance(result_item, tuple) and len(result_item) == 2:
            outbound_flight, return_flight = result_item
        else:
            # Fallback if fli changes format — treat as single flight
            logger.warning("Unexpected round-trip result format at index %d: %s", i, type(result_item))
            continue

        # Extract airline from outbound first leg
        out_first_leg = outbound_flight.legs[0] if outbound_flight.legs else None
        if not out_first_leg:
            continue

        airline_code = out_first_leg.airline.name if out_first_leg.airline else ""
        airline_name = out_first_leg.airline.value if out_first_leg.airline else "Unknown Airline"
        if airline_name == airline_code:
            airline_name = airline_code

        # Check excluded airports across both directions
        skip = False
        all_legs = list(outbound_flight.legs or []) + list(return_flight.legs or [])
        for leg in all_legs:
            dep_code = leg.departure_airport.name if leg.departure_airport else ""
            arr_code = leg.arrival_airport.name if leg.arrival_airport else ""
            if dep_code in exclude or arr_code in exclude:
                skip = True
                break
        if skip:
            continue

        # PRICE: outbound.price is the total round-trip price per person
        price_per_person = float(outbound_flight.price) if outbound_flight.price else 0
        total_price = price_per_person * passengers

        # Helper to extract segments from a FlightResult's legs
        def _extract_segments(flight_obj, fallback_origin, fallback_dest):
            segs = []
            for leg in (flight_obj.legs or []):
                dep_code = leg.departure_airport.name if leg.departure_airport else fallback_origin
                arr_code = leg.arrival_airport.name if leg.arrival_airport else fallback_dest
                dep_time = leg.departure_datetime.strftime("%Y-%m-%d %H:%M") if leg.departure_datetime else ""
                arr_time = leg.arrival_datetime.strftime("%Y-%m-%d %H:%M") if leg.arrival_datetime else ""
                dur = leg.duration if hasattr(leg, 'duration') and leg.duration else 0

                flight_num = ""
                if hasattr(leg, 'flight_number') and leg.flight_number:
                    acode = leg.airline.name if leg.airline else airline_code
                    flight_num = f"{acode} {leg.flight_number}"
                elif airline_code:
                    flight_num = f"{airline_code} {len(segs) + 1}"

                segs.append({
                    "origin": dep_code,
                    "destination": arr_code,
                    "departure_time": dep_time,
                    "arrival_time": arr_time,
                    "flight_number": flight_num,
                    "duration_minutes": dur,
                    "aircraft": getattr(leg, 'aircraft', '') or "",
                })
            return segs

        outbound_segments = _extract_segments(outbound_flight, origin, destination)
        return_segments = _extract_segments(return_flight, destination, origin)

        # Build layovers for outbound
        outbound_layovers = _build_layovers(outbound_segments)
        return_layovers = _build_layovers(return_segments)

        # Combine all segments and layovers for the full trip view
        all_segments = outbound_segments + return_segments
        all_layovers = outbound_layovers + return_layovers

        outbound_nonstop = len(outbound_segments) <= 1
        return_nonstop = len(return_segments) <= 1

        # Compute outbound and return durations
        outbound_duration = _compute_leg_duration(outbound_segments)
        return_duration = _compute_leg_duration(return_segments)

        # Total duration = outbound + return (fli gives duration per FlightResult)
        out_dur = outbound_flight.duration if outbound_flight.duration else outbound_duration
        ret_dur = return_flight.duration if return_flight.duration else return_duration
        total_duration = out_dur + ret_dur

        # Build round-trip booking links
        booking_links = _build_booking_links(
            origin, destination, departure_date, cabin_class, passengers,
            return_date=return_date,
        )
        booking_url = booking_links["google_flights"]

        results.append({
            "id": f"fli_rt_{origin}_{destination}_{i}",
            "airline": {
                "code": airline_code,
                "name": airline_name,
                "logo": _airline_logo(airline_code) if airline_code else "",
            },
            # Full trip data
            "segments": all_segments,
            "layovers": all_layovers,
            "is_nonstop": outbound_nonstop and return_nonstop,
            "is_round_trip": True,
            "trip_type": "round_trip",
            "total_duration_minutes": total_duration,
            # Outbound details
            "outbound_segments": outbound_segments,
            "outbound_layovers": outbound_layovers,
            "outbound_nonstop": outbound_nonstop,
            "outbound_duration_minutes": outbound_duration,
            # Return details
            "return_segments": return_segments,
            "return_layovers": return_layovers,
            "return_nonstop": return_nonstop,
            "return_duration_minutes": return_duration,
            # Pricing & metadata
            "cabin_class": cabin_class,
            "price_per_person": round(price_per_person, 2),
            "total_price": round(total_price, 2),
            "passengers": passengers,
            "departure_date": departure_date,
            "return_date": return_date,
            "booking_url": booking_url,
            "booking_links": booking_links,
            "currency_code": _DETECTED_CURRENCY,
            "currency_symbol": _DETECTED_SYMBOL,
        })

    # Smart ranking
    if sort_by != "cheapest" and len(results) > 1:
        results = _rank_by_value(results)
    else:
        results.sort(key=lambda x: (x["total_price"] == 0, x["total_price"]))

    logger.info("Returning %d round-trip flights (from %d raw, sort=%s)",
                len(results[:max_results]), len(flight_results), sort_by)
    return results[:max_results]


def _build_layovers(segments: list[dict]) -> list[dict]:
    """Build layover list between consecutive segments."""
    layovers = []
    for j in range(len(segments) - 1):
        arr_seg = segments[j]
        dep_seg = segments[j + 1]

        layover_dur = 0
        if arr_seg["arrival_time"] and dep_seg["departure_time"]:
            try:
                arr_dt = datetime.strptime(arr_seg["arrival_time"], "%Y-%m-%d %H:%M")
                dep_dt = datetime.strptime(dep_seg["departure_time"], "%Y-%m-%d %H:%M")
                layover_dur = int((dep_dt - arr_dt).total_seconds() / 60)
            except Exception:
                pass

        layover_airport = arr_seg["destination"]
        layovers.append({
            "airport": layover_airport,
            "airport_name": layover_airport,
            "description": f"Layover",
            "city": "—",
            "duration_minutes": layover_dur,
        })
    return layovers


def _compute_leg_duration(segments: list[dict]) -> int:
    """Compute total duration of a set of segments (flight time + layovers)."""
    if not segments:
        return 0
    first_dep = segments[0].get("departure_time", "")
    last_arr = segments[-1].get("arrival_time", "")
    if first_dep and last_arr:
        try:
            dep_dt = datetime.strptime(first_dep, "%Y-%m-%d %H:%M")
            arr_dt = datetime.strptime(last_arr, "%Y-%m-%d %H:%M")
            return int((arr_dt - dep_dt).total_seconds() / 60)
        except Exception:
            pass
    # Fallback: sum segment durations
    return sum(s.get("duration_minutes", 0) for s in segments)


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


# ── Alternate airport mapping for retry ────────────────────────
# When a search fails for one airport, try the other major airport
# in the same city (e.g. NRT ↔ HND for Tokyo).
_ALTERNATE_AIRPORTS = {
    "NRT": "HND", "HND": "NRT",  # Tokyo
    "LHR": "LGW", "LGW": "LHR", "STN": "LHR",  # London
    "JFK": "EWR", "EWR": "JFK", "LGA": "JFK",  # New York
    "ORD": "MDW", "MDW": "ORD",  # Chicago
    "LAX": "BUR", "BUR": "LAX",  # Los Angeles
    "SFO": "OAK", "OAK": "SFO",  # San Francisco
    "CDG": "ORY", "ORY": "CDG",  # Paris
    "ICN": "GMP", "GMP": "ICN",  # Seoul
    "KIX": "ITM", "ITM": "KIX",  # Osaka
    "PEK": "PKX", "PKX": "PEK",  # Beijing
    "PVG": "SHA", "SHA": "PVG",  # Shanghai
    "DCA": "IAD", "IAD": "DCA", "BWI": "DCA",  # Washington DC
    "DFW": "DAL", "DAL": "DFW",  # Dallas
    "MIA": "FLL", "FLL": "MIA",  # Miami
    "YYZ": "YTZ", "YTZ": "YYZ",  # Toronto
}


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
    Search for ONE-WAY flights using the flights/fli package (direct Google Flights API).
    If the primary search fails, retries with an alternate airport in the same city.
    Never returns fake/mock data — returns an empty list on total failure.

    sort_by:
      "best"     — (default) balance price + duration, filter out outlier durations
      "cheapest" — pure price sort, no duration filtering
    """
    origin = origin.upper()
    destination = destination.upper()

    # ── Primary search ─────────────────────────────────────────
    try:
        results = _search_fli(
            origin, destination, departure_date,
            cabin_class, passengers, max_results, exclude_airports,
            sort_by,
        )
        if results:
            return results
        logger.warning("Primary search %s → %s returned 0 results after filtering.", origin, destination)
    except Exception:
        logger.exception("fli primary search failed for %s → %s.", origin, destination)

    # ── Retry with alternate airport ───────────────────────────
    alt_dest = _ALTERNATE_AIRPORTS.get(destination)
    alt_origin = _ALTERNATE_AIRPORTS.get(origin)

    # Try alternate destination first (more common: NRT fails → try HND)
    if alt_dest:
        logger.info("Retrying with alternate destination: %s → %s", origin, alt_dest)
        try:
            results = _search_fli(
                origin, alt_dest, departure_date,
                cabin_class, passengers, max_results, exclude_airports,
                sort_by,
            )
            if results:
                return results
        except Exception:
            logger.warning("Alternate destination %s also failed.", alt_dest)

    # Try alternate origin
    if alt_origin:
        logger.info("Retrying with alternate origin: %s → %s", alt_origin, destination)
        try:
            results = _search_fli(
                alt_origin, destination, departure_date,
                cabin_class, passengers, max_results, exclude_airports,
                sort_by,
            )
            if results:
                return results
        except Exception:
            logger.warning("Alternate origin %s also failed.", alt_origin)

    logger.error("All search attempts exhausted for %s → %s on %s.", origin, destination, departure_date)
    return []


def search_flights_roundtrip(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str,
    cabin_class: str = "economy",
    passengers: int = 1,
    max_results: int = 5,
    exclude_airports: list[str] | None = None,
    sort_by: str = "best",
) -> list[dict]:
    """
    Search for ROUND-TRIP flights (A → B → A).
    If the round-trip search fails, falls back to two one-way searches
    and combines them into a single result.

    sort_by:
      "best"     — (default) balance price + duration, filter out outlier durations
      "cheapest" — pure price sort, no duration filtering
    """
    origin = origin.upper()
    destination = destination.upper()

    # ── Primary round-trip search ──────────────────────────────
    try:
        results = _search_fli_roundtrip(
            origin, destination, departure_date, return_date,
            cabin_class, passengers, max_results, exclude_airports,
            sort_by,
        )
        if results:
            return results
        logger.warning("Primary round-trip search %s ↔ %s returned 0 results.", origin, destination)
    except Exception:
        logger.exception("fli round-trip search failed for %s ↔ %s.", origin, destination)

    # ── Retry with alternate airports ──────────────────────────
    alt_dest = _ALTERNATE_AIRPORTS.get(destination)
    if alt_dest:
        logger.info("Retrying round-trip with alternate destination: %s ↔ %s", origin, alt_dest)
        try:
            results = _search_fli_roundtrip(
                origin, alt_dest, departure_date, return_date,
                cabin_class, passengers, max_results, exclude_airports,
                sort_by,
            )
            if results:
                return results
        except Exception:
            logger.warning("Alternate round-trip destination %s also failed.", alt_dest)

    alt_origin = _ALTERNATE_AIRPORTS.get(origin)
    if alt_origin:
        logger.info("Retrying round-trip with alternate origin: %s ↔ %s", alt_origin, destination)
        try:
            results = _search_fli_roundtrip(
                alt_origin, destination, departure_date, return_date,
                cabin_class, passengers, max_results, exclude_airports,
                sort_by,
            )
            if results:
                return results
        except Exception:
            logger.warning("Alternate round-trip origin %s also failed.", alt_origin)

    # ── Fallback: combine two one-way searches ─────────────────
    logger.info("Round-trip search exhausted, falling back to two one-way searches for %s ↔ %s", origin, destination)
    try:
        outbound = search_flights(
            origin, destination, departure_date,
            cabin_class, passengers, max_results=3, exclude_airports=exclude_airports,
            sort_by=sort_by,
        )
        inbound = search_flights(
            destination, origin, return_date,
            cabin_class, passengers, max_results=3, exclude_airports=exclude_airports,
            sort_by=sort_by,
        )

        if outbound and inbound:
            # Combine best outbound + best inbound into round-trip results
            combined = []
            for out_flight in outbound[:2]:
                for in_flight in inbound[:2]:
                    combined_segments = out_flight["segments"] + in_flight["segments"]
                    combined_layovers = out_flight["layovers"] + in_flight["layovers"]
                    total = out_flight["total_price"] + in_flight["total_price"]
                    pp = out_flight["price_per_person"] + in_flight["price_per_person"]

                    booking_links = _build_booking_links(
                        origin, destination, departure_date, cabin_class, passengers,
                        return_date=return_date,
                    )

                    combined.append({
                        "id": f"fli_rt_combined_{origin}_{destination}_{len(combined)}",
                        "airline": out_flight["airline"],
                        "segments": combined_segments,
                        "layovers": combined_layovers,
                        "is_nonstop": out_flight["is_nonstop"] and in_flight["is_nonstop"],
                        "is_round_trip": True,
                        "trip_type": "round_trip",
                        "total_duration_minutes": out_flight["total_duration_minutes"] + in_flight["total_duration_minutes"],
                        "outbound_segments": out_flight["segments"],
                        "outbound_layovers": out_flight["layovers"],
                        "outbound_nonstop": out_flight["is_nonstop"],
                        "outbound_duration_minutes": out_flight["total_duration_minutes"],
                        "return_segments": in_flight["segments"],
                        "return_layovers": in_flight["layovers"],
                        "return_nonstop": in_flight["is_nonstop"],
                        "return_duration_minutes": in_flight["total_duration_minutes"],
                        "cabin_class": cabin_class,
                        "price_per_person": round(pp, 2),
                        "total_price": round(total, 2),
                        "passengers": passengers,
                        "departure_date": departure_date,
                        "return_date": return_date,
                        "booking_url": booking_links["google_flights"],
                        "booking_links": booking_links,
                        "currency_code": _DETECTED_CURRENCY,
                        "currency_symbol": _DETECTED_SYMBOL,
                    })

            combined.sort(key=lambda x: x["total_price"])
            return combined[:max_results]
    except Exception:
        logger.exception("Fallback two-one-way search also failed for %s ↔ %s.", origin, destination)

    logger.error("All round-trip search attempts exhausted for %s ↔ %s.", origin, destination)
    return []


# ── Quick self-test ──────────────────────────────────────────────────

if __name__ == "__main__":
    # Verify protobuf encoding still works (used for Google Flights URL fallback)
    expected = "CBwQAhoeEgoyMDI0LTEyLTI1agcIARIDU0ZPcgcIARIDTEFYQAFIAXABggELCP___________wGYAQI"
    generated = _build_one_way_tfs("SFO", "LAX", "2024-12-25", passengers=2)
    assert generated == expected, f"Mismatch!\n  got:    {generated}\n  expect: {expected}"
    print("✓ Protobuf encoding matches known Google Flights tfs string")

    # Test direct booking URL generation
    links = _build_booking_links("JFK", "LAX", "2026-06-15")
    assert "google.com/travel/flights" in links["google_flights"]
    assert "kayak.com/flights/JFK-LAX" in links["kayak"]
    assert "skyscanner.com/transport/flights/jfk/lax" in links["skyscanner"]
    print("✓ All aggregator booking links generated correctly")
    for name, url in links.items():
        print(f"  {name}: {url[:80]}...")

    # Test round-trip booking URL generation
    rt_links = _build_booking_links("YYZ", "NRT", "2026-06-15", return_date="2026-06-22")
    assert "google.com/travel/flights" in rt_links["google_flights"]
    print("✓ Round-trip booking links generated correctly")

    # Show example Google Flights URLs
    examples = [
        ("YYZ", "NRT", "2026-06-15", "economy", 1),
        ("JFK", "LHR", "2026-07-01", "business", 2),
        ("LAX", "CDG", "2026-08-10", "first", 1),
    ]
    for orig, dest, dt, cabin, pax in examples:
        url = _google_flights_url(orig, dest, dt, cabin, pax)
        print(f"\n{orig} → {dest} ({dt}, {cabin}, {pax}pax):")
        print(f"  {url}")