"""
Flight search service — Duffel API.
Duffel docs: https://duffel.com/docs/api
"""

import logging
import requests
import urllib.parse
from datetime import datetime

from config import Config

logger = logging.getLogger(__name__)

# ── Airline logo helper ────────────────────────────────────────

def _airline_logo(code: str) -> str:
    if not code:
        return ""
    return f"https://www.gstatic.com/flights/airline_logos/70px/{code.upper()}.png"

def _parse_duration(iso: str) -> int:
    """Convert ISO-8601 duration like 'P1DT14H30M' or 'PT8H' to total minutes."""
    if not iso:
        return 0
    
    iso = iso.upper().replace("P", "")
    days = hours = minutes = 0
    
    if "D" in iso:
        parts = iso.split("D")
        days = int(parts[0] or 0)
        iso = parts[1]
        
    iso = iso.replace("T", "")
    
    if "H" in iso:
        parts = iso.split("H")
        hours = int(parts[0] or 0)
        iso = parts[1]
        
    if "M" in iso:
        parts = iso.split("M")
        minutes = int(parts[0] or 0)
        
    return (days * 24 * 60) + (hours * 60) + minutes

def _search_duffel(
    origin: str,
    destination: str,
    departure_date: str,
    cabin_class: str,
    passengers: int,
    max_results: int,
    exclude_airports: list[str] | None,
) -> list[dict]:
    headers = {
        "Authorization": f"Bearer {Config.DUFFEL_ACCESS_TOKEN}",
        "Duffel-Version": "v2",
        "Content-Type": "application/json",
    }
    
    cabin_map = {
        "economy": "economy",
        "premium_economy": "premium_economy",
        "business": "business",
        "first": "first"
    }
    
    payload = {
        "data": {
            "slices": [{"origin": origin, "destination": destination, "departure_date": departure_date}],
            "passengers": [{"type": "adult"} for _ in range(passengers)],
            "cabin_class": cabin_map.get(cabin_class, "economy")
        }
    }

    resp = requests.post("https://api.duffel.com/air/offer_requests", json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    
    offers = resp.json().get("data", {}).get("offers", [])
    exclude = set((a.upper() for a in (exclude_airports or [])))
    results = []

    for offer in offers:
        if not offer.get("slices"): continue
        slice_data = offer["slices"][0]
        segments_raw = slice_data.get("segments", [])

        if exclude:
            stops = {s["destination"]["iata_code"] for s in segments_raw[:-1]}
            if stops & exclude: continue

        total_duration = _parse_duration(slice_data.get("duration", "PT0M"))
        is_nonstop = len(segments_raw) == 1

        segments = []
        for seg in segments_raw:
            marketing = seg.get("marketing_carrier", {}) or {}
            
            # Safely handle if aircraft is entirely null
            aircraft_data = seg.get("aircraft") or {}
            
            segments.append({
                "flight_number": f"{marketing.get('iata_code', '')}{seg.get('marketing_carrier_flight_number', '')}",
                "origin": seg["origin"]["iata_code"],
                "destination": seg["destination"]["iata_code"],
                "departure_time": seg["departing_at"][11:16],
                "arrival_time": seg["arriving_at"][11:16],
                "duration_minutes": _parse_duration(seg.get("duration", "PT0M")),
                "aircraft": aircraft_data.get("name", "Unknown Aircraft"),
            })

        layovers = []
        for i in range(len(segments_raw) - 1):
            arr = segments_raw[i]["destination"]
            try:
                arr_dt = datetime.fromisoformat(segments_raw[i]["arriving_at"])
                dep_dt = datetime.fromisoformat(segments_raw[i + 1]["departing_at"])
                lay_mins = int((dep_dt - arr_dt).total_seconds() / 60)
            except Exception: lay_mins = 0
                
            layovers.append({
                "airport": arr["iata_code"],
                "airport_name": arr.get("name", arr["iata_code"]),
                "city": arr.get("city_name", arr["iata_code"]),
                "duration_minutes": lay_mins,
            })

        main_carrier = offer.get("owner", {})
        total_price = float(offer.get("total_amount", 0))

        # Duffel does not provide redirect URLs. Using foolproof Google Flights links based on exact params.
        query = urllib.parse.quote(f"Flights from {origin} to {destination} on {departure_date}")
        google_flights_url = f"https://www.google.com/travel/flights?q={query}"

        results.append({
            "id": offer.get("id"),
            "airline": {
                "code": main_carrier.get("iata_code", ""),
                "name": main_carrier.get("name", "Airline"),
                "logo": _airline_logo(main_carrier.get("iata_code", "")),
            },
            "segments": segments,
            "layovers": layovers,
            "is_nonstop": is_nonstop,
            "total_duration_minutes": total_duration,
            "cabin_class": cabin_class,
            "price_per_person": round(total_price / max(passengers, 1), 2),
            "total_price": total_price,
            "passengers": passengers,
            "departure_date": departure_date,
            "booking_url": google_flights_url
        })

    results.sort(key=lambda x: x["total_price"])
    return results[:max_results]


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
) -> list[dict]:
    """Search for flights using Duffel or fallback mock data."""
    origin = origin.upper()
    destination = destination.upper()

    if Config.DUFFEL_ACCESS_TOKEN:
        try:
            return _search_duffel(
                origin, destination, departure_date,
                cabin_class, passengers, max_results, exclude_airports,
            )
        except requests.exceptions.HTTPError as e:
            # This will print the exact reason Duffel rejected the request
            logger.error(f"Duffel API rejected the request: {e.response.text}")
        except Exception:
            logger.exception("Duffel flight search failed, falling back to mock data.")

    logger.warning("Using mock flight data. To use live data, set DUFFEL_ACCESS_TOKEN in .env")
    return _mock_flights(origin, destination, departure_date, passengers)