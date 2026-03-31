"""
Flight search service — Amadeus Flight Offers Search v2.

Falls back to SerpAPI Google Flights if Amadeus keys are missing.

Amadeus docs : https://developers.amadeus.com/self-service/category/flights/api-doc/flight-offers-search
SerpAPI docs : https://serpapi.com/google-flights-api
"""

import logging
import hashlib
import requests
from datetime import datetime

from config import Config

logger = logging.getLogger(__name__)

# ── Airline logo helper ────────────────────────────────────────

AIRLINE_LOGOS: dict[str, str] = {
    "UA": "https://www.gstatic.com/flights/airline_logos/70px/UA.png",
    "DL": "https://www.gstatic.com/flights/airline_logos/70px/DL.png",
    "AA": "https://www.gstatic.com/flights/airline_logos/70px/AA.png",
    "BA": "https://www.gstatic.com/flights/airline_logos/70px/BA.png",
    "LH": "https://www.gstatic.com/flights/airline_logos/70px/LH.png",
    "AF": "https://www.gstatic.com/flights/airline_logos/70px/AF.png",
    "NH": "https://www.gstatic.com/flights/airline_logos/70px/NH.png",
    "JL": "https://www.gstatic.com/flights/airline_logos/70px/JL.png",
    "SQ": "https://www.gstatic.com/flights/airline_logos/70px/SQ.png",
    "EK": "https://www.gstatic.com/flights/airline_logos/70px/EK.png",
    "AC": "https://www.gstatic.com/flights/airline_logos/70px/AC.png",
    "QF": "https://www.gstatic.com/flights/airline_logos/70px/QF.png",
    "TK": "https://www.gstatic.com/flights/airline_logos/70px/TK.png",
    "KL": "https://www.gstatic.com/flights/airline_logos/70px/KL.png",
    "CX": "https://www.gstatic.com/flights/airline_logos/70px/CX.png",
    "QR": "https://www.gstatic.com/flights/airline_logos/70px/QR.png",
    "WN": "https://www.gstatic.com/flights/airline_logos/70px/WN.png",
    "B6": "https://www.gstatic.com/flights/airline_logos/70px/B6.png",
    "AS": "https://www.gstatic.com/flights/airline_logos/70px/AS.png",
    "NK": "https://www.gstatic.com/flights/airline_logos/70px/NK.png",
    "F9": "https://www.gstatic.com/flights/airline_logos/70px/F9.png",
    "VS": "https://www.gstatic.com/flights/airline_logos/70px/VS.png",
    "IB": "https://www.gstatic.com/flights/airline_logos/70px/IB.png",
    "AZ": "https://www.gstatic.com/flights/airline_logos/70px/AZ.png",
    "SK": "https://www.gstatic.com/flights/airline_logos/70px/SK.png",
    "AY": "https://www.gstatic.com/flights/airline_logos/70px/AY.png",
    "LX": "https://www.gstatic.com/flights/airline_logos/70px/LX.png",
    "OS": "https://www.gstatic.com/flights/airline_logos/70px/OS.png",
    "KE": "https://www.gstatic.com/flights/airline_logos/70px/KE.png",
    "OZ": "https://www.gstatic.com/flights/airline_logos/70px/OZ.png",
}


def _airline_logo(code: str) -> str:
    """Return a Google Flights airline logo URL for any IATA code."""
    return AIRLINE_LOGOS.get(
        code.upper(),
        f"https://www.gstatic.com/flights/airline_logos/70px/{code.upper()}.png",
    )


def _parse_duration(iso: str) -> int:
    """Convert ISO-8601 duration like 'PT14H30M' to total minutes."""
    iso = iso.replace("PT", "")
    hours = 0
    minutes = 0
    if "H" in iso:
        parts = iso.split("H")
        hours = int(parts[0])
        iso = parts[1]
    if "M" in iso:
        minutes = int(iso.replace("M", ""))
    return hours * 60 + minutes


CABIN_MAP = {
    "economy": "ECONOMY",
    "premium_economy": "PREMIUM_ECONOMY",
    "business": "BUSINESS",
    "first": "FIRST",
}


# ── Amadeus Flight Offers Search ───────────────────────────────

def _search_amadeus(
    origin: str,
    destination: str,
    departure_date: str,
    cabin_class: str,
    passengers: int,
    max_results: int,
    exclude_airports: list[str] | None,
) -> list[dict]:
    from services.amadeus_client import amadeus_get

    params = {
        "originLocationCode": origin,
        "destinationLocationCode": destination,
        "departureDate": departure_date,
        "adults": passengers,
        "max": min(max_results, 10),
        "currencyCode": "USD",
    }
    cabin = CABIN_MAP.get(cabin_class)
    if cabin:
        params["travelClass"] = cabin

    data = amadeus_get("/v2/shopping/flight-offers", params)
    offers = data.get("data", [])
    dicts = data.get("dictionaries", {})
    carrier_names = dicts.get("carriers", {})

    exclude = set((a.upper() for a in (exclude_airports or [])))
    results = []

    for offer in offers:
        # Each offer has 1+ itineraries; we only care about the outbound (index 0)
        itin = offer.get("itineraries", [{}])[0]
        segments_raw = itin.get("segments", [])

        # Filter out offers with excluded layover airports
        if exclude:
            stops = {s["arrival"]["iataCode"] for s in segments_raw[:-1]}
            if stops & exclude:
                continue

        total_duration = _parse_duration(itin.get("duration", "PT0M"))
        is_nonstop = len(segments_raw) == 1

        # Build segments
        segments = []
        for seg in segments_raw:
            carrier_code = seg.get("carrierCode", "")
            segments.append({
                "flight_number": f"{carrier_code}{seg.get('number', '')}",
                "origin": seg["departure"]["iataCode"],
                "destination": seg["arrival"]["iataCode"],
                "departure_time": seg["departure"].get("at", "")[-8:-3],  # HH:MM
                "arrival_time": seg["arrival"].get("at", "")[-8:-3],
                "duration_minutes": _parse_duration(seg.get("duration", "PT0M")),
                "aircraft": seg.get("aircraft", {}).get("code", ""),
            })

        # Build layovers
        layovers = []
        for i in range(len(segments_raw) - 1):
            arr = segments_raw[i]["arrival"]
            dep = segments_raw[i + 1]["departure"]
            try:
                arr_dt = datetime.fromisoformat(arr["at"])
                dep_dt = datetime.fromisoformat(dep["at"])
                lay_mins = int((dep_dt - arr_dt).total_seconds() / 60)
            except Exception:
                lay_mins = 0
            layovers.append({
                "airport": arr["iataCode"],
                "airport_name": arr.get("terminal", arr["iataCode"]),
                "city": arr["iataCode"],
                "duration_minutes": lay_mins,
            })

        # Price
        price_info = offer.get("price", {})
        total_price = float(price_info.get("grandTotal", 0))
        price_per_pax = round(total_price / max(passengers, 1), 2)

        main_carrier = segments_raw[0].get("carrierCode", "")

        results.append({
            "id": offer.get("id", hashlib.md5(str(offer).encode()).hexdigest()[:12]),
            "airline": {
                "code": main_carrier,
                "name": carrier_names.get(main_carrier, main_carrier),
                "logo": _airline_logo(main_carrier),
            },
            "segments": segments,
            "layovers": layovers,
            "is_nonstop": is_nonstop,
            "total_duration_minutes": total_duration,
            "cabin_class": cabin_class,
            "price_per_person": price_per_pax,
            "total_price": total_price,
            "passengers": passengers,
            "departure_date": departure_date,
            "booking_url": (
                f"https://www.google.com/travel/flights?q="
                f"{origin}+to+{destination}+{departure_date}"
            ),
        })

    results.sort(key=lambda x: x["total_price"])
    return results[:max_results]


# ── SerpAPI Google Flights fallback ────────────────────────────

def _search_serpapi(
    origin: str,
    destination: str,
    departure_date: str,
    cabin_class: str,
    passengers: int,
    max_results: int,
    exclude_airports: list[str] | None,
) -> list[dict]:
    cabin_map_serp = {
        "economy": 1,
        "premium_economy": 2,
        "business": 3,
        "first": 4,
    }
    params = {
        "engine": "google_flights",
        "departure_id": origin,
        "arrival_id": destination,
        "outbound_date": departure_date,
        "adults": passengers,
        "travel_class": cabin_map_serp.get(cabin_class, 1),
        "currency": "USD",
        "api_key": Config.SERPAPI_KEY,
    }
    resp = requests.get("https://serpapi.com/search.json", params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    exclude = set((a.upper() for a in (exclude_airports or [])))
    results = []

    for group in (data.get("best_flights", []) + data.get("other_flights", [])):
        flights = group.get("flights", [])
        if not flights:
            continue

        # Check exclusions
        stop_codes = {f.get("arrival_airport", {}).get("id", "") for f in flights[:-1]}
        if stop_codes & exclude:
            continue

        segments = []
        for f in flights:
            segments.append({
                "flight_number": f"{f.get('airline', '')}{f.get('flight_number', '')}",
                "origin": f.get("departure_airport", {}).get("id", ""),
                "destination": f.get("arrival_airport", {}).get("id", ""),
                "departure_time": f.get("departure_airport", {}).get("time", ""),
                "arrival_time": f.get("arrival_airport", {}).get("time", ""),
                "duration_minutes": f.get("duration", 0),
                "aircraft": f.get("airplane", ""),
            })

        layovers_raw = group.get("layovers", [])
        layovers = [
            {
                "airport": lo.get("id", ""),
                "airport_name": lo.get("name", ""),
                "city": lo.get("id", ""),
                "duration_minutes": lo.get("duration", 0),
            }
            for lo in layovers_raw
        ]

        total_price = float(group.get("price", 0)) * passengers
        carrier_code = flights[0].get("airline", "")

        results.append({
            "id": hashlib.md5(str(group).encode()).hexdigest()[:12],
            "airline": {
                "code": carrier_code,
                "name": flights[0].get("airline", carrier_code),
                "logo": _airline_logo(carrier_code) if len(carrier_code) == 2 else (
                    flights[0].get("airline_logo", "")
                ),
            },
            "segments": segments,
            "layovers": layovers,
            "is_nonstop": len(flights) == 1,
            "total_duration_minutes": group.get("total_duration", 0),
            "cabin_class": cabin_class,
            "price_per_person": round(float(group.get("price", 0)), 2),
            "total_price": total_price,
            "passengers": passengers,
            "departure_date": departure_date,
            "booking_url": (
                f"https://www.google.com/travel/flights?q="
                f"{origin}+to+{destination}+{departure_date}"
            ),
        })

        if len(results) >= max_results:
            break

    results.sort(key=lambda x: x["total_price"])
    return results


# ── Public interface ───────────────────────────────────────────

def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    cabin_class: str = "economy",
    passengers: int = 1,
    max_results: int = 5,
    exclude_airports: list[str] | None = None,
) -> list[dict]:
    """Search for flights using the best available API."""
    origin = origin.upper()
    destination = destination.upper()

    # 1) Try Amadeus
    if Config.AMADEUS_CLIENT_ID and Config.AMADEUS_CLIENT_SECRET:
        try:
            return _search_amadeus(
                origin, destination, departure_date,
                cabin_class, passengers, max_results, exclude_airports,
            )
        except Exception:
            logger.exception("Amadeus flight search failed, trying SerpAPI fallback")

    # 2) Try SerpAPI
    if Config.SERPAPI_KEY:
        try:
            return _search_serpapi(
                origin, destination, departure_date,
                cabin_class, passengers, max_results, exclude_airports,
            )
        except Exception:
            logger.exception("SerpAPI flight search failed")

    # 3) No API configured
    logger.error(
        "No flight API configured. Set AMADEUS_CLIENT_ID/SECRET or SERPAPI_KEY in .env"
    )
    return [{
        "id": "no-api",
        "error": "No flight API configured. Please add Amadeus or SerpAPI keys to .env.",
        "airline": {"code": "??", "name": "Not configured", "logo": ""},
        "segments": [],
        "layovers": [],
        "is_nonstop": True,
        "total_duration_minutes": 0,
        "cabin_class": cabin_class,
        "price_per_person": 0,
        "total_price": 0,
        "passengers": passengers,
        "departure_date": departure_date,
        "booking_url": f"https://www.google.com/travel/flights?q={origin}+to+{destination}+{departure_date}",
    }]
