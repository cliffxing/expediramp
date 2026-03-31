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
"""

import logging
import re
import urllib.parse
import base64
from datetime import datetime

logger = logging.getLogger(__name__)


# ── Airline logo helper ────────────────────────────────────────

def _airline_logo(code: str) -> str:
    if not code:
        return ""
    return f"https://www.gstatic.com/flights/airline_logos/70px/{code.upper()}.png"


# ── Direct airline booking URL helper ──────────────────────────

_AIRLINE_BOOKING_URLS: dict[str, str] = {
    # North America
    "AA": "https://www.aa.com/booking/search?locale=en_US&pax=1&adult=1&type=OneWay&searchType=Award&from={origin}&to={dest}&depart={date}&cabin=",
    "DL": "https://www.delta.com/flight-search/book-a-flight?cacheKeySuffix=a&tripType=ONE_WAY&action=findFlights&from={origin}&to={dest}&departureDate={date}&paxCount=1",
    "UA": "https://www.united.com/ual/en/us/flight-search/book-a-flight/results/awd?f={origin}&t={dest}&d={date}&tt=1&at=1&sc=7&px=1&taxng=1&newHP=True&clm=7&st=bestmatches&tqp=A",
    "WN": "https://www.southwest.com/air/booking/select.html?originationAirportCode={origin}&destinationAirportCode={dest}&departureDate={date}&adultPassengersCount=1&returnDate=",
    "B6": "https://www.jetblue.com/booking/flights?from={origin}&to={dest}&depart={date}&isMultiCity=false&noOfRoute=1&lang=en&adults=1&children=0&infants=0",
    "AS": "https://www.alaskaair.com/planbook/shoppingstart?prior=as&A=1&prior=as&FT=ow&O={origin}&D={dest}&OD={date}",
    "AC": "https://www.aircanada.com/booking/search?tripType=O&ADT=1&org0={origin}&dest0={dest}&departDate0={date}&lang=en-CA",
    "WS": "https://www.westjet.com/search?type=ow&orig={origin}&dest={dest}&depart={date}&adult=1",
    # Europe
    "BA": "https://www.britishairways.com/travel/book/public/en_us?from={origin}&to={dest}&depDate={date}&cabin=M&adultCount=1&youngAdultCount=0&childCount=0&infantCount=0&tripType=oneWay",
    "LH": "https://www.lufthansa.com/us/en/flight-search?searchType=ONEWAY&pax=1ADT&origin={origin}&destination={dest}&outDate={date}",
    "AF": "https://www.airfrance.us/search/offer?pax=1:0:0:0:0:0:0:0&cabinClass=ECONOMY&activeConnection=0&connections={origin}-A>{dest}-A:{date}",
    "KL": "https://www.klm.us/search/offer?pax=1:0:0:0:0:0:0:0&cabinClass=ECONOMY&activeConnection=0&connections={origin}-A>{dest}-A:{date}",
    # Middle East
    "EK": "https://www.emirates.com/flights/search?from={origin}&to={dest}&departDate={date}&adult=1&child=0&infant=0&class=Economy",
    "QR": "https://www.qatarairways.com/en/booking/book-flights.html?from={origin}&to={dest}&departing={date}&adults=1&children=0&infants=0&trip=O&class=E",
    "EY": "https://www.etihad.com/en/fly-etihad/book/flight-search-results?ow=true&origin={origin}&destination={dest}&departureDate={date}&adults=1",
    "TK": "https://www.turkishairlines.com/en-int/flights/?origin={origin}&destination={dest}&departureDate={date}&adult=1",
    # Asia Pacific
    "SQ": "https://www.singaporeair.com/en_UK/plan-and-book/booking/?from={origin}&to={dest}&departDate={date}&cabinClass=Y&adults=1",
    "CX": "https://www.cathaypacific.com/cx/en_US/book-a-trip/flight-search.html?origin={origin}&destination={dest}&departure={date}&cabin=economy&adults=1",
    "JL": "https://www.jal.co.jp/en/inter/booking/?from={origin}&to={dest}&date={date}&adult=1",
    "NH": "https://www.ana.co.jp/en/us/book-plan/booking/search/?from={origin}&to={dest}&date={date}&adult=1",
    "QF": "https://www.qantas.com/au/en/book-a-trip/flights.html?from={origin}&to={dest}&date={date}&adult=1&cabin=economy",
    "KE": "https://www.koreanair.com/booking/search?tripType=OW&from={origin}&to={dest}&departure={date}&adults=1",
}


def _try_direct_booking_url(
    airline_code: str,
    origin: str,
    destination: str,
    departure_date: str,
) -> str | None:
    """
    Attempt to build a direct airline booking URL for the given flight.
    Returns None if we don't have a template for this airline.

    NOTE: These URLs pre-fill the airline's own search page with the route/date.
    They are NOT guaranteed to deep-link to a specific flight — the user will
    still need to select the exact flight on the airline's site. But it's a
    better experience than a generic Google Flights link.
    """
    template = _AIRLINE_BOOKING_URLS.get(airline_code.upper())
    if not template:
        return None
    try:
        return template.format(
            origin=origin.upper(),
            dest=destination.upper(),
            date=departure_date,
        )
    except (KeyError, IndexError):
        return None


# ── Protobuf-based Google Flights URL builder (kept as fallback) ──

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


def _google_flights_url(
    origin: str,
    destination: str,
    date: str,
    cabin_class: str = "economy",
    passengers: int = 1,
) -> str:
    """
    Build a Google Flights search URL with a proper protobuf-encoded tfs parameter.

    Returns a URL like:
      https://www.google.com/travel/flights/search?tfs=CBwQAh...&hl=en&curr=USD

    This opens Google Flights pre-filled with the exact route, date, and class
    so the user's specific flight appears at/near the top of the results page.
    """
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
        f"&curr=USD"
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


# ── Core search using fli ─────────────────────────────────────

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
    Search flights using the flights (fli) package — direct Google Flights API.
    Returns results in the same format as the rest of ExpediRamp expects.
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

    # Build search filters
    filters = FlightSearchFilters(
        trip_type=TripType.ONE_WAY,
        passenger_info=PassengerInfo(adults=passengers),
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

    # Build the fallback Google Flights URL
    google_url = _google_flights_url(origin, destination, departure_date, cabin_class, passengers)

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

        # Skip if price is missing/zero (bad data)
        price = float(flight.price) if flight.price else 0
        total_price = price * passengers

        # Build segments list from legs
        segments = []
        for leg in flight.legs:
            dep_code = leg.departure_airport.name if leg.departure_airport else origin
            arr_code = leg.arrival_airport.name if leg.arrival_airport else destination
            dep_time = leg.departure_datetime.strftime("%Y-%m-%d %H:%M") if leg.departure_datetime else ""
            arr_time = leg.arrival_datetime.strftime("%Y-%m-%d %H:%M") if leg.arrival_datetime else ""

            segments.append({
                "flight_number": f"{leg.airline.name} {leg.flight_number}" if leg.airline and leg.flight_number else airline_name,
                "origin": dep_code,
                "destination": arr_code,
                "departure_time": dep_time,
                "arrival_time": arr_time,
                "duration_minutes": leg.duration if leg.duration else 0,
                "aircraft": "",
            })

        # Build layover info if there are stops
        layovers = []
        num_stops = flight.stops if flight.stops else 0
        is_nonstop = (num_stops == 0)

        if num_stops > 0 and len(flight.legs) > 1:
            # Calculate layover durations between consecutive legs
            for j in range(len(flight.legs) - 1):
                current_leg = flight.legs[j]
                next_leg = flight.legs[j + 1]

                layover_airport = current_leg.arrival_airport.name if current_leg.arrival_airport else "—"
                layover_minutes = 0

                if current_leg.arrival_datetime and next_leg.departure_datetime:
                    delta = next_leg.departure_datetime - current_leg.arrival_datetime
                    layover_minutes = max(int(delta.total_seconds() / 60), 0)

                layovers.append({
                    "airport": layover_airport,
                    "airport_name": layover_airport,
                    "city": "—",
                    "duration_minutes": layover_minutes,
                })
        elif num_stops > 0:
            # We know there are stops but don't have detailed leg info
            layovers.append({
                "airport": "—",
                "airport_name": f"{num_stops} stop(s)",
                "city": "—",
                "duration_minutes": 0,
            })

        total_duration = flight.duration if flight.duration else 0

        # Try to get a direct airline booking link; fall back to Google Flights
        booking_url = _try_direct_booking_url(
            airline_code, origin, destination, departure_date
        ) or google_url

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
            "total_duration_minutes": total_duration,
            "cabin_class": cabin_class,
            "price_per_person": round(price, 2),
            "total_price": round(total_price, 2),
            "passengers": passengers,
            "departure_date": departure_date,
            "booking_url": booking_url,
        })

    # ── Smart ranking (for "best" mode) ─────────────────────────
    if sort_by != "cheapest" and len(results) > 1:
        results = _rank_by_value(results)
    else:
        # Pure price sort for "cheapest" mode
        results.sort(key=lambda x: (x["total_price"] == 0, x["total_price"]))

    logger.info("Returning %d flights (from %d raw, sort=%s)", len(results[:max_results]), len(flight_results), sort_by)
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
    Search for flights using the flights/fli package (direct Google Flights API).
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


# ── Quick self-test ──────────────────────────────────────────────────

if __name__ == "__main__":
    # Verify protobuf encoding still works (used for Google Flights URL fallback)
    expected = "CBwQAhoeEgoyMDI0LTEyLTI1agcIARIDU0ZPcgcIARIDTEFYQAFIAXABggELCP___________wGYAQI"
    generated = _build_one_way_tfs("SFO", "LAX", "2024-12-25", passengers=2)
    assert generated == expected, f"Mismatch!\n  got:    {generated}\n  expect: {expected}"
    print("✓ Protobuf encoding matches known Google Flights tfs string")

    # Test direct booking URL generation
    url = _try_direct_booking_url("DL", "JFK", "LAX", "2026-06-15")
    assert url is not None and "delta.com" in url
    print(f"✓ Direct booking URL: {url[:80]}...")

    # Test that unknown airline falls back to None
    assert _try_direct_booking_url("XX", "JFK", "LAX", "2026-06-15") is None
    print("✓ Unknown airline returns None (will fall back to Google Flights)")

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