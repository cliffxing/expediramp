"""
Hotel search service — SerpAPI Google Hotels.
"""

import logging
import hashlib
import requests
from datetime import datetime

from config import Config

logger = logging.getLogger(__name__)

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

    query = f"hotels in {preferred_neighborhood}, {city}" if preferred_neighborhood else f"hotels in {city}"
    city_encoded = city.replace(" ", "%20")

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
        
        # Prefer SerpAPI's provided Google link, fallback to Expedia
        valid_link = prop.get("link")
        if not valid_link:
            valid_link = f"https://www.expedia.com/Hotel-Search?destination={city_encoded}&startDate={check_in}&endDate={check_out}"

        results.append({
            "id": hashlib.md5(prop.get("name", "").encode()).hexdigest()[:12],
            "name": prop.get("name", "Hotel"),
            "city": city,
            "neighborhood": prop.get("neighborhood", preferred_neighborhood or city),
            "stars": prop.get("hotel_class", 3),
            "guest_rating": prop.get("overall_rating", 4.0),
            "image_url": image_url,
            "amenities": prop.get("amenities", [])[:10],
            "price_per_night": nightly,
            "total_price": total_price,
            "nights": nights,
            "rooms": rooms,
            "check_in": check_in,
            "check_out": check_out,
            "cancellation_policy": "Check hotel policy",
            "booking_url": valid_link,
        })

        if len(results) >= max_results:
            break

    results.sort(key=lambda x: x["total_price"])
    return results


def _mock_hotels(city: str, check_in: str, check_out: str, nights: int) -> list[dict]:
    """Fallback generator to ensure the UI timeline works perfectly even without an API key."""
    city_encoded = city.replace(" ", "%20")
    return [{
        "id": "mock_hotel_1",
        "name": f"The Grand {city.title()} Plaza",
        "city": city,
        "neighborhood": "Downtown",
        "stars": 4,
        "guest_rating": 4.5,
        "image_url": HOTEL_IMAGES[0],
        "amenities": ["Free WiFi", "Pool", "Spa", "Fitness Center", "Restaurant"],
        "price_per_night": 250.0,
        "total_price": 250.0 * nights,
        "nights": nights,
        "rooms": 1,
        "check_in": check_in,
        "check_out": check_out,
        "cancellation_policy": "Free cancellation",
        "booking_url": f"https://www.expedia.com/Hotel-Search?destination={city_encoded}&startDate={check_in}&endDate={check_out}"
    }]


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
    """Search for hotels using SerpAPI or fallback mock data."""
    try:
        d1 = datetime.strptime(check_in, "%Y-%m-%d")
        d2 = datetime.strptime(check_out, "%Y-%m-%d")
        nights = max((d2 - d1).days, 1)
    except Exception:
        nights = 3

    if Config.SERPAPI_KEY:
        try:
            return _search_serpapi(
                city, check_in, check_out, guests, rooms,
                budget_tier, preferred_neighborhood, max_results,
            )
        except Exception:
            logger.exception("SerpAPI hotel search failed, falling back to mock data.")

    logger.warning("Using mock hotel data. To use live data, set SERPAPI_KEY in .env")
    return _mock_hotels(city, check_in, check_out, nights)