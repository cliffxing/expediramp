"""
Hotel search service — SerpAPI Google Hotels.
"""

import logging
import hashlib
import re
import requests
import urllib.parse
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)

HOTEL_IMAGES = [
    "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=600",
    "https://images.unsplash.com/photo-1551882547-ff40c63fe5fa?w=600",
    "https://images.unsplash.com/photo-1520250497591-112f2f40a3f4?w=600",
    "https://images.unsplash.com/photo-1582719508461-905c673771fd?w=600",
]


def _parse_price(val) -> float:
    """
    Safely parse a price value that may be a number, a '$X' string, or None.
    Strips currency symbols, commas, and spaces before converting to float.
    Returns 0.0 if the value cannot be parsed.
    """
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    # Strip currency symbols, commas, spaces — keep digits and decimal point only
    cleaned = re.sub(r"[^\d.]", "", str(val))
    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0


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
    try:
        nights = max(
            (
                datetime.strptime(check_out, "%Y-%m-%d")
                - datetime.strptime(check_in, "%Y-%m-%d")
            ).days,
            1,
        )
    except Exception:
        nights = 3

    query = f"{preferred_neighborhood}, {city}" if preferred_neighborhood else city
    city_encoded = urllib.parse.quote(city)

    # Price filters — only include max_price when not luxury (avoid 400s from tight ranges)
    price_floors  = {"budget": 0,   "mid": 100, "upscale": 200, "luxury": 400}
    price_ceilings = {"budget": 200, "mid": 400, "upscale": 800, "luxury": 9999}

    params = {
        "engine": "google_hotels",
        "q": query,
        "check_in_date": check_in,
        "check_out_date": check_out,
        "adults": str(guests),
        "rooms": str(rooms),
        "currency": "USD",
        "api_key": Config.SERPAPI_KEY,
    }

    # Only add price filters for non-luxury (9999 ceiling causes 400)
    min_p = price_floors.get(budget_tier, 0)
    max_p = price_ceilings.get(budget_tier, 9999)
    if min_p > 0:
        params["min_price"] = min_p
    if max_p < 9999:
        params["max_price"] = max_p

    resp = requests.get("https://serpapi.com/search.json", params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    results = []
    for prop in data.get("properties", []):

        # ── Robust price extraction ────────────────────────────
        # SerpAPI may return prices as plain numbers OR formatted strings like
        # "$189" or "189.00". The old code used bare float() which would crash
        # on currency-prefixed strings, silently falling through to the mock
        # fallback. It also had a flawed conditional where total_rate being
        # *present* (even as {}) would suppress the × nights multiplication
        # even when price_str was actually pulled from rate_per_night.
        #
        # Fix: use _parse_price() everywhere, and decide which field to use
        # based on whether the *parsed value* is non-zero, not on key presence.
        total_rate_val  = prop.get("total_rate",    {}).get("extracted_lowest")
        nightly_val     = prop.get("rate_per_night", {}).get("extracted_lowest")

        total_from_total_rate = _parse_price(total_rate_val)
        total_from_nightly    = _parse_price(nightly_val) * nights

        if total_from_total_rate > 0:
            # SerpAPI gave us the whole-stay total directly — use it.
            total_price = total_from_total_rate
        elif total_from_nightly > 0:
            # Only a per-night rate was available — multiply up to the stay total.
            total_price = total_from_nightly
        else:
            # No usable price in the response — skip this property.
            logger.debug(
                "Skipping hotel '%s' — no parseable price in SerpAPI response "
                "(total_rate=%r, rate_per_night=%r)",
                prop.get("name"), total_rate_val, nightly_val,
            )
            continue
        # ── End price extraction ───────────────────────────────

        images = prop.get("images", [])
        image_url = ""
        if images:
            # Prefer thumbnail — less likely to be blocked by CORS / hotlink protection
            image_url = images[0].get("thumbnail") or images[0].get("original_image", "")

        if not image_url:
            image_url = HOTEL_IMAGES[len(results) % len(HOTEL_IMAGES)]

        valid_link = prop.get("link")
        if not valid_link:
            valid_link = (
                f"https://www.expedia.com/Hotel-Search"
                f"?destination={city_encoded}&startDate={check_in}&endDate={check_out}"
            )

        results.append({
            "id": hashlib.md5(prop.get("name", "").encode()).hexdigest()[:12],
            "name": prop.get("name", "Hotel"),
            "city": city,
            "neighborhood": prop.get("neighborhood", preferred_neighborhood or city),
            "stars": prop.get("hotel_class", 3),
            "guest_rating": prop.get("overall_rating", 4.0),
            "image_url": image_url,
            "amenities": prop.get("amenities", [])[:10],
            "price_per_night": round(total_price / max(nights, 1), 2),
            "total_price": round(total_price, 2),
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
    city_encoded = urllib.parse.quote(city)
    return [
        {
            "id": "mock_hotel_1",
            "name": f"The Grand {city.title()} Plaza",
            "city": city,
            "neighborhood": "Downtown",
            "stars": 4,
            "guest_rating": 4.5,
            "image_url": HOTEL_IMAGES[0],
            "amenities": ["Free WiFi", "Pool", "Spa"],
            "price_per_night": 250.0,
            "total_price": 250.0 * nights,
            "nights": nights,
            "rooms": 1,
            "check_in": check_in,
            "check_out": check_out,
            "cancellation_policy": "Free cancellation",
            "booking_url": (
                f"https://www.expedia.com/Hotel-Search"
                f"?destination={city_encoded}&startDate={check_in}&endDate={check_out}"
            ),
        }
    ]


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
    try:
        nights = max(
            (
                datetime.strptime(check_out, "%Y-%m-%d")
                - datetime.strptime(check_in, "%Y-%m-%d")
            ).days,
            1,
        )
    except Exception:
        nights = 3

    if Config.SERPAPI_KEY:
        try:
            return _search_serpapi(
                city, check_in, check_out, guests, rooms,
                budget_tier, preferred_neighborhood, max_results,
            )
        except Exception:
            logger.exception("SerpAPI hotel search failed")

    return _mock_hotels(city, check_in, check_out, nights)