"""
Flight search service — Duffel API.
Duffel docs: https://duffel.com/docs/api
"""

import logging
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
    if not code:
        return ""
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
            "slices": [
                {
                    "origin": origin,
                    "destination": destination,
                    "departure_date": departure_date
                }
            ],
            "passengers": [{"type": "adult"} for _ in range(passengers)],
            "cabin_class": cabin_map.get(cabin_class, "economy")
        }
    }

    # Create Offer Request
    resp = requests.post("https://api.duffel.com/air/offer_requests", json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    
    offers = resp.json().get("data", {}).get("offers", [])
    
    exclude = set((a.upper() for a in (exclude_airports or [])))
    results = []

    for offer in offers:
        if not offer.get("slices"):
            continue
            
        slice_data = offer["slices"][0]
        segments_raw = slice_data.get("segments", [])

        # Filter out offers with excluded layover airports
        if exclude:
            stops = {s["destination"]["iata_code"] for s in segments_raw[:-1]}
            if stops & exclude:
                continue

        total_duration = _parse_duration(slice_data.get("duration", "PT0M"))
        is_nonstop = len(segments_raw) == 1

        # Build segments
        segments = []
        for seg in segments_raw:
            marketing = seg.get("marketing_carrier", {}) or {}
            segments.append({
                "flight_number": f"{marketing.get('iata_code', '')}{seg.get('marketing_carrier_flight_number', '')}",
                "origin": seg["origin"]["iata_code"],
                "destination": seg["destination"]["iata_code"],
                "departure_time": seg["departing_at"][11:16],  # extract HH:MM
                "arrival_time": seg["arriving_at"][11:16],
                "duration_minutes": _parse_duration(seg.get("duration", "PT0M")),
                "aircraft": seg.get("aircraft", {}).get("name", "Unknown Aircraft"),
            })

        # Build layovers
        layovers = []
        for i in range(len(segments_raw) - 1):
            arr = segments_raw[i]["destination"]
            try:
                arr_dt = datetime.fromisoformat(segments_raw[i]["arriving_at"])
                dep_dt = datetime.fromisoformat(segments_raw[i + 1]["departing_at"])
                lay_mins = int((dep_dt - arr_dt).total_seconds() / 60)
            except Exception:
                lay_mins = 0
                
            layovers.append({
                "airport": arr["iata_code"],
                "airport_name": arr.get("name", arr["iata_code"]),
                "city": arr.get("city_name", arr["iata_code"]),
                "duration_minutes": lay_mins,
            })

        main_carrier = offer.get("owner", {})
        total_price = float(offer.get("total_amount", 0))
        price_per_pax = round(total_price / max(passengers, 1), 2)

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
            "price_per_person": price_per_pax,
            "total_price": total_price,
            "passengers": passengers,
            "departure_date": departure_date,
            "booking_url": f"https://www.kayak.com/flights/{origin}-{destination}/{departure_date}"
        })

    results.sort(key=lambda x: x["total_price"])
    return results[:max_results]


def _mock_flights(origin: str, destination: str, date: str, passengers: int) -> list[dict]:
    """Fallback generator to ensure the UI timeline works perfectly even without an API key."""
    return [{
        "id": "mock_flight_1",
        "airline": {
            "code": "DL",
            "name": "Delta Air Lines",
            "logo": _airline_logo("DL")
        },
        "segments": [{
            "flight_number": "DL102",
            "origin": origin,
            "destination": destination,
            "departure_time": "08:00",
            "arrival_time": "11:30",
            "duration_minutes": 210,
            "aircraft": "Boeing 737"
        }],
        "layovers": [],
        "is_nonstop": True,
        "total_duration_minutes": 210,
        "cabin_class": "economy",
        "price_per_person": 345.0,
        "total_price": 345.0 * passengers,
        "passengers": passengers,
        "departure_date": date,
        "booking_url": f"https://www.kayak.com/flights/{origin}-{destination}/{date}"
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
        except Exception:
            logger.exception("Duffel flight search failed, falling back to mock data.")

    logger.warning("Using mock flight data. To use live data, set DUFFEL_ACCESS_TOKEN in .env")
    return _mock_flights(origin, destination, departure_date, passengers)