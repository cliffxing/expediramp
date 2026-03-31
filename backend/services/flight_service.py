"""
Flight search service using the Duffel Flights API.

Falls back to SerpAPI Google Flights if Duffel keys are missing.

Duffel API docs : https://duffel.com/docs/api/v2/offers
SerpAPI docs    : https://serpapi.com/google-flights-api
"""

import hashlib
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

CABIN_MAP_DUFFEL = {
    "economy": "economy",
    "premium_economy": "premium_economy",
    "business": "business",
    "first": "first",
}


def _airline_logo(code: str) -> str:
    return AIRLINE_LOGOS.get(
        code.upper(),
        f"https://www.gstatic.com/flights/airline_logos/70px/{code.upper()}.png",
    )


def _iso_duration_to_minutes(iso: str) -> int:
    """Convert ISO 8601 duration 'PT14H30M' to total minutes."""
    if not iso:
        return 0
    iso = iso.replace("PT", "")
    hours, minutes = 0, 0
    if "H" in iso:
        parts = iso.split("H")
        hours = int(parts[0])
        iso = parts[1]
    if "M" in iso:
        minutes = int(iso.replace("M", ""))
    return hours * 60 + minutes


# ── Duffel Flight Search ───────────────────────────────────────

def _search_duffel(
    origin: str,
    destination: str,
    departure_date: str,
    cabin_class: str,
    passengers: int,
    max_results: int,
    exclude_airports: list[str] | None,
) -> list[dict]:
    """Search for flights using the Duffel Offers API."""
    from services.duffel_client import duffel_post, duffel_get

    cabin = CABIN_MAP_DUFFEL.get(cabin_class, "economy")
    passenger_list = [{"type": "adult"} for _ in range(passengers)]

    body = {
        "data": {
            "slices": [
                {
                    "origin": origin.upper(),
                    "destination": destination.upper(),
                    "departure_date": departure_date,
                }
            ],
            "passengers": passenger_list,
            "cabin_class": cabin,
            "return_offers": True,
        }
    }

    offer_req = duffel_post("/air/offer_requests", body)
    request_id = offer_req["data"]["id"]

    # Fetch offers sorted by price
    offers_resp = duffel_get(
        "/air/offers",
        {
            "offer_request_id": request_id,
            "limit": min(max_results * 3, 200),
            "sort": "total_amount",
        },
    )
    offers = offers_resp.get("data", [])

    exclude = {a.upper() for a in (exclude_airports or [])}
    results = []

    for offer in offers:
        slices = offer.get("slices", [])
        if not slices:
            continue
        sl = slices[0]
        segments_raw = sl.get("segments", [])

        # Filter excluded airports
        if exclude:
            stops = {seg["destination"]["iata_code"] for seg in segments_raw[:-1]}
            if stops & exclude:
                continue

        # Build segments list
        segments = []
        for seg in segments_raw:
            mc = seg.get("marketing_carrier", {})
            segments.append({
                "flight_number": f"{mc.get('iata_code', '')}{seg.get('marketing_carrier_flight_number', '')}",
                "origin": seg["origin"]["iata_code"],
                "destination": seg["destination"]["iata_code"],
                "departure_time": seg.get("departing_at", "")[-8:-3] if seg.get("departing_at") else "",
                "arrival_time": seg.get("arriving_at", "")[-8:-3] if seg.get("arriving_at") else "",
                "duration_minutes": _iso_duration_to_minutes(seg.get("duration", "")),
                "aircraft": seg.get("aircraft", {}).get("name", "") if seg.get("aircraft") else "",
            })

        # Build layovers
        layovers = []
        for i in range(len(segments_raw) - 1):
            arr_seg = segments_raw[i]
            dep_seg = segments_raw[i + 1]
            try:
                arr_dt = datetime.fromisoformat(arr_seg["arriving_at"])
                dep_dt = datetime.fromisoformat(dep_seg["departing_at"])
                lay_mins = int((dep_dt - arr_dt).total_seconds() / 60)
            except Exception:
                lay_mins = 0
            layovers.append({
                "airport": arr_seg["destination"]["iata_code"],
                "airport_name": arr_seg["destination"].get("name", arr_seg["destination"]["iata_code"]),
                "city": arr_seg["destination"].get("city_name", arr_seg["destination"]["iata_code"]),
                "duration_minutes": lay_mins,
            })

        total_price = float(offer.get("total_amount", 0))
        price_per_person = round(total_price / max(passengers, 1), 2)

        mc_first = segments_raw[0].get("marketing_carrier", {}) if segments_raw else {}
        main_carrier = mc_first.get("iata_code", "")
        carrier_name = mc_first.get("name", main_carrier)
        total_duration = _iso_duration_to_minutes(sl.get("duration", ""))

        results.append({
            "id": offer.get("id", hashlib.md5(str(offer).encode()).hexdigest()[:12]),
            "duffel_offer_id": offer.get("id"),
            "airline": {
                "code": main_carrier,
                "name": carrier_name,
                "logo": _airline_logo(main_carrier),
            },
            "segments": segments,
            "layovers": layovers,
            "is_nonstop": len(segments_raw) == 1,
            "total_duration_minutes": total_duration,
            "cabin_class": cabin_class,
            "price_per_person": price_per_person,
            "total_price": total_price,
            "currency": offer.get("total_currency", "USD"),
            "passengers": passengers,
            "departure_date": departure_date,
            "expires_at": offer.get("expires_at", ""),
            "conditions": offer.get("conditions", {}),
            "booking_url": (
                f"https://www.google.com/travel/flights?q="
                f"{origin}+to+{destination}+{departure_date}"
            ),
        })

        if len(results) >= max_results:
            break

    results.sort(key=lambda x: x["total_price"])
    return results[:max_results]


# ── SerpAPI Google Flights fallback ───────────────────────────

def _search_serpapi(
    origin: str,
    destination: str,
    departure_date: str,
    cabin_class: str,
    passengers: int,
    max_results: int,
    exclude_airports: list[str] | None,
) -> list[dict]:
    cabin_map_serp = {"economy": 1, "premium_economy": 2, "business": 3, "first": 4}
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

    exclude = {a.upper() for a in (exclude_airports or [])}
    results = []

    for group in (data.get("best_flights", []) + data.get("other_flights", [])):
        flights = group.get("flights", [])
        if not flights:
            continue

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
            "duffel_offer_id": None,
            "airline": {
                "code": carrier_code,
                "name": flights[0].get("airline", carrier_code),
                "logo": (
                    _airline_logo(carrier_code)
                    if len(carrier_code) == 2
                    else flights[0].get("airline_logo", "")
                ),
            },
            "segments": segments,
            "layovers": layovers,
            "is_nonstop": len(flights) == 1,
            "total_duration_minutes": group.get("total_duration", 0),
            "cabin_class": cabin_class,
            "price_per_person": round(float(group.get("price", 0)), 2),
            "total_price": total_price,
            "currency": "USD",
            "passengers": passengers,
            "departure_date": departure_date,
            "duffel_offer_id": None,
            "expires_at": "",
            "booking_url": (
                f"https://www.google.com/travel/flights?q="
                f"{origin}+to+{destination}+{departure_date}"
            ),
        })

        if len(results) >= max_results:
            break

    results.sort(key=lambda x: x["total_price"])
    return results


# ── Public Interface ───────────────────────────────────────────

def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    cabin_class: str = "economy",
    passengers: int = 1,
    max_results: int = 5,
    exclude_airports: list[str] | None = None,
) -> list[dict]:
    """Search for flights using Duffel (primary) → SerpAPI (fallback)."""
    origin = origin.upper()
    destination = destination.upper()

    # 1) Try Duffel
    if Config.DUFFEL_ACCESS_TOKEN:
        try:
            return _search_duffel(
                origin, destination, departure_date,
                cabin_class, passengers, max_results, exclude_airports,
            )
        except Exception:
            logger.exception("Duffel flight search failed, trying SerpAPI fallback")

    # 2) Try SerpAPI
    if Config.SERPAPI_KEY:
        try:
            return _search_serpapi(
                origin, destination, departure_date,
                cabin_class, passengers, max_results, exclude_airports,
            )
        except Exception:
            logger.exception("SerpAPI flight search also failed")

    # 3) No API configured
    logger.error("No flight API configured. Set DUFFEL_ACCESS_TOKEN or SERPAPI_KEY in .env")
    return [{
        "id": "no-api",
        "error": "No flight API configured. Please add DUFFEL_ACCESS_TOKEN or SERPAPI_KEY to .env.",
        "airline": {"code": "??", "name": "Not configured", "logo": ""},
        "segments": [],
        "layovers": [],
        "is_nonstop": True,
        "total_duration_minutes": 0,
        "cabin_class": cabin_class,
        "price_per_person": 0,
        "total_price": 0,
        "currency": "USD",
        "passengers": passengers,
        "departure_date": departure_date,
        "duffel_offer_id": None,
        "expires_at": "",
        "booking_url": f"https://www.google.com/travel/flights?q={origin}+to+{destination}+{departure_date}",
    }]
