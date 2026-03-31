"""
Hotel search service — Amadeus Hotel Search v3 + Hotel Offers v3.

Falls back to SerpAPI Google Hotels if Amadeus keys are missing.

Amadeus docs : https://developers.amadeus.com/self-service/category/hotels
SerpAPI docs : https://serpapi.com/google-hotels-api
"""

import logging
import hashlib
import requests
from datetime import datetime

from config import Config

logger = logging.getLogger(__name__)

# ── City → IATA mapping (used by Amadeus cityCode param) ──────

CITY_IATA: dict[str, str] = {
    "new york": "NYC", "los angeles": "LAX", "san francisco": "SFO",
    "chicago": "CHI", "miami": "MIA", "london": "LON", "paris": "PAR",
    "tokyo": "TYO", "osaka": "OSA", "seoul": "SEL", "singapore": "SIN",
    "dubai": "DXB", "frankfurt": "FRA", "rome": "ROM", "barcelona": "BCN",
    "sydney": "SYD", "toronto": "YTO", "vancouver": "YVR", "bangkok": "BKK",
    "honolulu": "HNL", "cancun": "CUN", "cancún": "CUN", "atlanta": "ATL",
    "seattle": "SEA", "denver": "DEN", "boston": "BOS", "berlin": "BER",
    "amsterdam": "AMS", "madrid": "MAD", "lisbon": "LIS", "mumbai": "BOM",
    "hong kong": "HKG", "taipei": "TPE", "istanbul": "IST",
}


def _city_code(city: str) -> str:
    return CITY_IATA.get(city.lower().strip(), city[:3].upper())


# ── Unsplash fallback images ──────────────────────────────────

HOTEL_IMAGES = [
    "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=600",
    "https://images.unsplash.com/photo-1551882547-ff40c63fe5fa?w=600",
    "https://images.unsplash.com/photo-1520250497591-112f2f40a3f4?w=600",
    "https://images.unsplash.com/photo-1582719508461-905c673771fd?w=600",
    "https://images.unsplash.com/photo-1564501049412-61c2a3083791?w=600",
    "https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?w=600",
    "https://images.unsplash.com/photo-1571896349842-33c89424de2d?w=600",
    "https://images.unsplash.com/photo-1455587734955-081b22074882?w=600",
    "https://images.unsplash.com/photo-1578683010236-d716f9a3f461?w=600",
    "https://images.unsplash.com/photo-1445019980597-93fa8acb246c?w=600",
]


# ── Amadeus Hotel Search ──────────────────────────────────────

def _search_amadeus(
    city: str,
    check_in: str,
    check_out: str,
    guests: int,
    rooms: int,
    budget_tier: str,
    preferred_neighborhood: str | None,
    max_results: int,
) -> list[dict]:
    from services.amadeus_client import amadeus_get

    city_code = _city_code(city)

    # Calculate nights
    try:
        d1 = datetime.strptime(check_in, "%Y-%m-%d")
        d2 = datetime.strptime(check_out, "%Y-%m-%d")
        nights = max((d2 - d1).days, 1)
    except Exception:
        nights = 3

    # Step 1: Find hotels by city
    hotels_data = amadeus_get(
        "/v1/reference-data/locations/hotels/by-city",
        {"cityCode": city_code},
    )
    hotel_list = hotels_data.get("data", [])[:20]  # cap to avoid rate limits

    if not hotel_list:
        return []

    # Step 2: Get offers for those hotels (batch up to 20)
    hotel_ids = [h["hotelId"] for h in hotel_list[:20]]

    try:
        offers_data = amadeus_get(
            "/v3/shopping/hotel-offers",
            {
                "hotelIds": ",".join(hotel_ids),
                "checkInDate": check_in,
                "checkOutDate": check_out,
                "adults": guests,
                "roomQuantity": rooms,
                "currency": "USD",
            },
        )
    except Exception:
        # v3 might fail on sandbox — try individual calls
        offers_data = {"data": []}
        for hid in hotel_ids[:max_results]:
            try:
                single = amadeus_get(
                    f"/v3/shopping/hotel-offers",
                    {
                        "hotelIds": hid,
                        "checkInDate": check_in,
                        "checkOutDate": check_out,
                        "adults": guests,
                        "roomQuantity": rooms,
                        "currency": "USD",
                    },
                )
                offers_data["data"].extend(single.get("data", []))
            except Exception:
                continue

    # Build result list
    star_filter = {"budget": (1, 3), "mid": (3, 4), "upscale": (4, 5), "luxury": (4, 5)}
    star_lo, star_hi = star_filter.get(budget_tier, (1, 5))

    results = []
    for hotel_offer in offers_data.get("data", []):
        hotel = hotel_offer.get("hotel", {})
        offers = hotel_offer.get("offers", [])
        if not offers:
            continue

        best_offer = offers[0]
        price_info = best_offer.get("price", {})
        total_str = price_info.get("total", "0")
        total_price = float(total_str) if total_str else 0

        rating_raw = hotel.get("rating", "3")
        try:
            stars = int(rating_raw)
        except (ValueError, TypeError):
            stars = 3

        if stars < star_lo or stars > star_hi:
            continue

        nightly = round(total_price / max(nights, 1), 2) if total_price else 0

        # Cancellation policy
        policies = best_offer.get("policies", {})
        cancel = policies.get("cancellation", {})
        cancel_text = "Non-refundable"
        if cancel.get("type") == "FULL_REFUND" or cancel.get("description", {}).get("text"):
            cancel_text = cancel.get("description", {}).get("text", "Free cancellation")

        results.append({
            "id": hotel.get("hotelId", hashlib.md5(str(hotel).encode()).hexdigest()[:12]),
            "name": hotel.get("name", "Hotel"),
            "chain": hotel.get("chainCode", ""),
            "city": city,
            "neighborhood": preferred_neighborhood or hotel.get("address", {}).get("lines", [""])[0] or city,
            "stars": stars,
            "guest_rating": min(stars + 0.5, 5.0),
            "review_count": 0,
            "image_url": HOTEL_IMAGES[len(results) % len(HOTEL_IMAGES)],
            "amenities": [],
            "price_per_night": nightly,
            "total_price": total_price,
            "nights": nights,
            "rooms": rooms,
            "check_in": check_in,
            "check_out": check_out,
            "cancellation_policy": cancel_text,
            "booking_url": (
                f"https://www.google.com/travel/hotels/{city.replace(' ', '+')}?"
                f"dates={check_in}_{check_out}"
            ),
        })

        if len(results) >= max_results:
            break

    results.sort(key=lambda x: x["total_price"])
    return results


# ── SerpAPI Google Hotels fallback ────────────────────────────

def _search_serpapi(
    city: str,
    check_in: str,
    check_out: str,
    guests: int,
    rooms: int,
    budget_tier: str,
    preferred_neighborhood: str | None,
    max_results: int,
) -> list[dict]:
    # Calculate nights
    try:
        d1 = datetime.strptime(check_in, "%Y-%m-%d")
        d2 = datetime.strptime(check_out, "%Y-%m-%d")
        nights = max((d2 - d1).days, 1)
    except Exception:
        nights = 3

    query = f"hotels in {city}"
    if preferred_neighborhood:
        query = f"hotels in {preferred_neighborhood}, {city}"

    min_price_map = {"budget": 0, "mid": 100, "upscale": 200, "luxury": 400}
    max_price_map = {"budget": 120, "mid": 300, "upscale": 600, "luxury": 9999}

    params = {
        "engine": "google_hotels",
        "q": query,
        "check_in_date": check_in,
        "check_out_date": check_out,
        "adults": guests,
        "currency": "USD",
        "min_price": min_price_map.get(budget_tier, 0),
        "max_price": max_price_map.get(budget_tier, 9999),
        "api_key": Config.SERPAPI_KEY,
    }

    resp = requests.get("https://serpapi.com/search.json", params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    results = []
    for prop in data.get("properties", []):
        price_str = prop.get("total_rate", {}).get("extracted_lowest", "")
        if not price_str:
            price_str = prop.get("rate_per_night", {}).get("extracted_lowest", "0")
            total_price = float(price_str) * nights
        else:
            total_price = float(price_str)

        nightly = round(total_price / max(nights, 1), 2)

        images = prop.get("images", [])
        image_url = images[0].get("original_image", "") if images else HOTEL_IMAGES[len(results) % len(HOTEL_IMAGES)]

        results.append({
            "id": hashlib.md5(prop.get("name", "").encode()).hexdigest()[:12],
            "name": prop.get("name", "Hotel"),
            "chain": "",
            "city": city,
            "neighborhood": prop.get("neighborhood", preferred_neighborhood or city),
            "stars": prop.get("hotel_class", 3),
            "guest_rating": prop.get("overall_rating", 4.0),
            "review_count": prop.get("reviews", 0),
            "image_url": image_url,
            "amenities": prop.get("amenities", [])[:10],
            "price_per_night": nightly,
            "total_price": total_price,
            "nights": nights,
            "rooms": rooms,
            "check_in": check_in,
            "check_out": check_out,
            "cancellation_policy": "Check hotel policy",
            "booking_url": prop.get("link", f"https://www.google.com/travel/hotels/{city.replace(' ', '+')}?dates={check_in}_{check_out}"),
        })

        if len(results) >= max_results:
            break

    results.sort(key=lambda x: x["total_price"])
    return results


# ── Public interface ──────────────────────────────────────────

def search_hotels(
    city: str,
    check_in: str,
    check_out: str,
    guests: int = 2,
    rooms: int = 1,
    budget_tier: str = "mid",
    preferred_neighborhood: str | None = None,
    max_results: int = 5,
) -> list[dict]:
    """Search for hotels using the best available API."""

    # 1) Try Amadeus
    if Config.AMADEUS_CLIENT_ID and Config.AMADEUS_CLIENT_SECRET:
        try:
            return _search_amadeus(
                city, check_in, check_out, guests, rooms,
                budget_tier, preferred_neighborhood, max_results,
            )
        except Exception:
            logger.exception("Amadeus hotel search failed, trying SerpAPI fallback")

    # 2) Try SerpAPI
    if Config.SERPAPI_KEY:
        try:
            return _search_serpapi(
                city, check_in, check_out, guests, rooms,
                budget_tier, preferred_neighborhood, max_results,
            )
        except Exception:
            logger.exception("SerpAPI hotel search failed")

    # 3) No API configured
    logger.error(
        "No hotel API configured. Set AMADEUS_CLIENT_ID/SECRET or SERPAPI_KEY in .env"
    )
    return [{
        "id": "no-api",
        "error": "No hotel API configured. Please add API keys to .env.",
        "name": f"No API configured – {city}",
        "chain": "",
        "city": city,
        "neighborhood": city,
        "stars": 0,
        "guest_rating": 0,
        "review_count": 0,
        "image_url": HOTEL_IMAGES[0],
        "amenities": [],
        "price_per_night": 0,
        "total_price": 0,
        "nights": 0,
        "rooms": rooms,
        "check_in": check_in,
        "check_out": check_out,
        "cancellation_policy": "",
        "booking_url": f"https://www.google.com/travel/hotels/{city.replace(' ', '+')}",
    }]
