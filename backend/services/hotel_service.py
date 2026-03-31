"""
Hotel search service using the Duffel Stays API.

Falls back to SerpAPI Google Hotels if Duffel keys are missing.

Duffel Stays docs : https://duffel.com/docs/api/v2/stays
SerpAPI docs      : https://serpapi.com/google-hotels-api
"""

import hashlib
import logging
import requests
from datetime import datetime

from config import Config

logger = logging.getLogger(__name__)

# ── City → lat/lng for Duffel radius search ──────────────────
# Duffel Stays uses lat/lng + radius, not city codes.

CITY_COORDS: dict[str, tuple[float, float]] = {
    "new york": (40.7128, -74.0060),
    "los angeles": (34.0522, -118.2437),
    "san francisco": (37.7749, -122.4194),
    "chicago": (41.8781, -87.6298),
    "miami": (25.7617, -80.1918),
    "london": (51.5074, -0.1278),
    "paris": (48.8566, 2.3522),
    "tokyo": (35.6762, 139.6503),
    "osaka": (34.6937, 135.5023),
    "seoul": (37.5665, 126.9780),
    "singapore": (1.3521, 103.8198),
    "dubai": (25.2048, 55.2708),
    "frankfurt": (50.1109, 8.6821),
    "rome": (41.9028, 12.4964),
    "barcelona": (41.3851, 2.1734),
    "sydney": (-33.8688, 151.2093),
    "toronto": (43.6532, -79.3832),
    "vancouver": (49.2827, -123.1207),
    "bangkok": (13.7563, 100.5018),
    "honolulu": (21.3069, -157.8583),
    "cancun": (21.1619, -86.8515),
    "atlanta": (33.7490, -84.3880),
    "seattle": (47.6062, -122.3321),
    "denver": (39.7392, -104.9903),
    "boston": (42.3601, -71.0589),
    "berlin": (52.5200, 13.4050),
    "amsterdam": (52.3676, 4.9041),
    "madrid": (40.4168, -3.7038),
    "lisbon": (38.7169, -9.1399),
    "mumbai": (19.0760, 72.8777),
    "hong kong": (22.3193, 114.1694),
    "taipei": (25.0330, 121.5654),
    "istanbul": (41.0082, 28.9784),
    "las vegas": (36.1699, -115.1398),
    "orlando": (28.5383, -81.3792),
    "new orleans": (29.9511, -90.0715),
    "washington": (38.9072, -77.0369),
    "philadelphia": (39.9526, -75.1652),
    "phoenix": (33.4484, -112.0740),
    "san diego": (32.7157, -117.1611),
    "dallas": (32.7767, -96.7970),
    "houston": (29.7604, -95.3698),
}

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


def _get_coords(city: str) -> tuple[float, float] | None:
    return CITY_COORDS.get(city.lower().strip())


def _nights(check_in: str, check_out: str) -> int:
    try:
        d1 = datetime.strptime(check_in, "%Y-%m-%d")
        d2 = datetime.strptime(check_out, "%Y-%m-%d")
        return max((d2 - d1).days, 1)
    except Exception:
        return 3


# ── Duffel Stays Search ───────────────────────────────────────

def _search_duffel(
    city: str,
    check_in: str,
    check_out: str,
    guests: int,
    rooms: int,
    budget_tier: str,
    preferred_neighborhood: str | None,
    max_results: int,
) -> list[dict]:
    """Search for hotels using the Duffel Stays API."""
    from services.duffel_client import duffel_post

    coords = _get_coords(city)
    if not coords:
        raise ValueError(
            f"No coordinates found for city '{city}'. "
            "Try a major city name like 'Paris' or 'Tokyo'."
        )

    lat, lng = coords
    n_nights = _nights(check_in, check_out)

    # Duffel Stays search request
    body = {
        "data": {
            "rooms": rooms,
            "location": {
                "geographic_coordinates": {
                    "latitude": lat,
                    "longitude": lng,
                    "radius": 10,   # km radius around city center
                }
            },
            "check_in_date": check_in,
            "check_out_date": check_out,
            "guests": [{"type": "adult"} for _ in range(guests)],
        }
    }

    resp = duffel_post("/stays/search", body)
    search_id = resp["data"]["id"]
    results_raw = resp["data"].get("results", [])

    # Budget tier → star rating filter
    star_filter = {
        "budget": (1, 3),
        "mid": (3, 4),
        "upscale": (4, 5),
        "luxury": (5, 5),
    }
    star_lo, star_hi = star_filter.get(budget_tier, (1, 5))

    results = []
    for prop in results_raw:
        accommodation = prop.get("accommodation", {})
        cheapest_rate = prop.get("cheapest_rate_total_amount")
        cheapest_currency = prop.get("cheapest_rate_currency", "USD")

        total_price = float(cheapest_rate) if cheapest_rate else 0.0
        nightly = round(total_price / n_nights, 2) if n_nights and total_price else 0.0

        rating = accommodation.get("rating")  # 1-5 star integer
        try:
            stars = int(rating) if rating else 3
        except (ValueError, TypeError):
            stars = 3

        if stars < star_lo or stars > star_hi:
            continue

        # Photos
        photos = accommodation.get("photos", [])
        image_url = (
            photos[0].get("url", HOTEL_IMAGES[len(results) % len(HOTEL_IMAGES)])
            if photos
            else HOTEL_IMAGES[len(results) % len(HOTEL_IMAGES)]
        )

        # Amenities
        amenities_raw = accommodation.get("amenities", [])
        amenities = [a.get("description", a.get("type", "")) for a in amenities_raw[:10]]

        # Review score
        review = accommodation.get("review_score")
        guest_rating = float(review) if review else round(3.5 + stars * 0.2, 1)

        # Chain / brand
        chain = accommodation.get("chain", {})
        chain_name = chain.get("name", "") if isinstance(chain, dict) else ""

        # Location
        location = accommodation.get("location", {})
        address = location.get("address", {})
        neighborhood = (
            preferred_neighborhood
            or address.get("city_name", city)
        )

        results.append({
            "id": prop.get("id", hashlib.md5(str(prop).encode()).hexdigest()[:12]),
            "duffel_accommodation_id": accommodation.get("id"),
            "duffel_search_id": search_id,
            "name": accommodation.get("name", "Hotel"),
            "chain": chain_name,
            "city": city,
            "neighborhood": neighborhood,
            "stars": stars,
            "guest_rating": guest_rating,
            "review_count": 0,
            "image_url": image_url,
            "amenities": amenities,
            "price_per_night": nightly,
            "total_price": total_price,
            "currency": cheapest_currency,
            "nights": n_nights,
            "rooms": rooms,
            "check_in": check_in,
            "check_out": check_out,
            "cancellation_policy": "Check hotel policy",
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
    n_nights = _nights(check_in, check_out)

    query = f"hotels in {preferred_neighborhood + ', ' + city if preferred_neighborhood else city}"
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
            total_price = float(price_str) * n_nights
        else:
            total_price = float(price_str)

        nightly = round(total_price / max(n_nights, 1), 2)
        images = prop.get("images", [])
        image_url = (
            images[0].get("original_image", "")
            if images
            else HOTEL_IMAGES[len(results) % len(HOTEL_IMAGES)]
        )

        results.append({
            "id": hashlib.md5(prop.get("name", "").encode()).hexdigest()[:12],
            "duffel_accommodation_id": None,
            "duffel_search_id": None,
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
            "currency": "USD",
            "nights": n_nights,
            "rooms": rooms,
            "check_in": check_in,
            "check_out": check_out,
            "cancellation_policy": "Check hotel policy",
            "booking_url": prop.get(
                "link",
                f"https://www.google.com/travel/hotels/{city.replace(' ', '+')}?dates={check_in}_{check_out}",
            ),
        })

        if len(results) >= max_results:
            break

    results.sort(key=lambda x: x["total_price"])
    return results


# ── Public Interface ──────────────────────────────────────────

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
    """Search for hotels using Duffel Stays (primary) → SerpAPI (fallback)."""

    # 1) Try Duffel Stays
    if Config.DUFFEL_ACCESS_TOKEN:
        try:
            return _search_duffel(
                city, check_in, check_out, guests, rooms,
                budget_tier, preferred_neighborhood, max_results,
            )
        except Exception:
            logger.exception("Duffel hotel search failed, trying SerpAPI fallback")

    # 2) Try SerpAPI
    if Config.SERPAPI_KEY:
        try:
            return _search_serpapi(
                city, check_in, check_out, guests, rooms,
                budget_tier, preferred_neighborhood, max_results,
            )
        except Exception:
            logger.exception("SerpAPI hotel search also failed")

    # 3) No API configured
    logger.error("No hotel API configured. Set DUFFEL_ACCESS_TOKEN or SERPAPI_KEY in .env")
    return [{
        "id": "no-api",
        "error": "No hotel API configured. Please add DUFFEL_ACCESS_TOKEN or SERPAPI_KEY to .env.",
        "name": f"Not configured – {city}",
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
        "currency": "USD",
        "nights": _nights(check_in, check_out),
        "rooms": rooms,
        "check_in": check_in,
        "check_out": check_out,
        "cancellation_policy": "",
        "booking_url": f"https://www.google.com/travel/hotels/{city.replace(' ', '+')}",
    }]
