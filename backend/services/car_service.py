"""
Car rental & transit service.

Car rentals: uses SerpAPI Google Rental Cars if available, otherwise generates
booking-redirect links to Kayak, Google, and Rentalcars.com.

Transit: curated static data for major cities with real URLs.
"""

import logging
import hashlib
import requests
from datetime import datetime

from config import Config

logger = logging.getLogger(__name__)


# ── Car images (royalty-free from Unsplash) ────────────────────

CAR_IMAGES = {
    "compact": "https://images.unsplash.com/photo-1549317661-bd32c8ce0afa?w=400",
    "midsize": "https://images.unsplash.com/photo-1590362891991-f776e747a588?w=400",
    "full_size": "https://images.unsplash.com/photo-1553440569-bcc63803a83d?w=400",
    "suv": "https://images.unsplash.com/photo-1519641471654-76ce0107ad1b?w=400",
    "luxury": "https://images.unsplash.com/photo-1555215695-3004980ad54e?w=400",
    "minivan": "https://images.unsplash.com/photo-1570294646112-27ce4f174e33?w=400",
    "convertible": "https://images.unsplash.com/photo-1544636331-e26879cd4d9b?w=400",
}


# ── SerpAPI Google Rental Cars ────────────────────────────────

def _search_serpapi(
    city: str,
    pickup_date: str,
    dropoff_date: str,
    car_class: str | None,
    max_results: int,
) -> list[dict]:
    try:
        d1 = datetime.strptime(pickup_date, "%Y-%m-%d")
        d2 = datetime.strptime(dropoff_date, "%Y-%m-%d")
        days = max((d2 - d1).days, 1)
    except Exception:
        days = 3

    params = {
        "engine": "google_hotels",  # SerpAPI doesn't have a dedicated cars engine
        "q": f"car rental in {city}",
        "api_key": Config.SERPAPI_KEY,
    }

    # SerpAPI doesn't have a dedicated car rental engine, so we generate
    # booking redirect URLs to real aggregators instead.
    raise NotImplementedError("SerpAPI cars not available; use booking redirects")


def _generate_booking_links(
    city: str,
    pickup_date: str,
    dropoff_date: str,
    car_class: str | None,
    max_results: int,
) -> list[dict]:
    """
    Generate booking redirect links to major car rental aggregators.
    These link directly to search results on Kayak, Google, etc.
    """
    try:
        d1 = datetime.strptime(pickup_date, "%Y-%m-%d")
        d2 = datetime.strptime(dropoff_date, "%Y-%m-%d")
        days = max((d2 - d1).days, 1)
    except Exception:
        days = 3

    city_slug = city.lower().replace(" ", "-")
    city_enc = city.replace(" ", "+")

    # Price estimates by class (realistic ranges)
    estimates = {
        "compact": {"daily": (25, 50), "examples": ["Toyota Corolla", "Honda Civic", "Hyundai Elantra"]},
        "midsize": {"daily": (40, 75), "examples": ["Toyota Camry", "Nissan Altima", "Kia K5"]},
        "full_size": {"daily": (50, 100), "examples": ["Chevrolet Impala", "Dodge Charger", "Chrysler 300"]},
        "suv": {"daily": (55, 120), "examples": ["Toyota RAV4", "Ford Explorer", "Jeep Grand Cherokee"]},
        "luxury": {"daily": (100, 250), "examples": ["BMW 5 Series", "Mercedes E-Class", "Audi A6"]},
        "minivan": {"daily": (60, 110), "examples": ["Chrysler Pacifica", "Toyota Sienna"]},
        "convertible": {"daily": (80, 180), "examples": ["Ford Mustang Convertible", "Chevrolet Camaro"]},
    }

    classes = [car_class] if car_class and car_class in estimates else ["compact", "midsize", "suv", "full_size"]
    results = []

    aggregators = [
        {
            "name": "Kayak",
            "url": f"https://www.kayak.com/cars/{city_slug}/{pickup_date}/{dropoff_date}",
        },
        {
            "name": "Google",
            "url": f"https://www.google.com/travel/cars?q={city_enc}&pickup={pickup_date}&dropoff={dropoff_date}",
        },
        {
            "name": "Rentalcars.com",
            "url": f"https://www.rentalcars.com/search-results?location={city_enc}&puDate={pickup_date}&doDate={dropoff_date}",
        },
    ]

    for cls in classes:
        info = estimates[cls]
        avg_daily = round((info["daily"][0] + info["daily"][1]) / 2, 2)
        total_est = round(avg_daily * days, 2)
        vehicle = info["examples"][0]

        for agg in aggregators[:1]:  # one result per class
            results.append({
                "id": hashlib.md5(f"{cls}-{city}-{agg['name']}".encode()).hexdigest()[:12],
                "company": {"name": agg["name"], "logo": ""},
                "car_class": cls,
                "vehicle": vehicle,
                "image_url": CAR_IMAGES.get(cls, CAR_IMAGES["midsize"]),
                "price_per_day": avg_daily,
                "total_price": total_est,
                "days": days,
                "pickup_date": pickup_date,
                "dropoff_date": dropoff_date,
                "pickup_location": f"{city} Airport or Downtown",
                "features": ["Automatic", "A/C", "GPS Available"],
                "booking_url": agg["url"],
                "is_estimate": True,
            })

        if len(results) >= max_results:
            break

    results.sort(key=lambda x: x["total_price"])
    return results[:max_results]


# ── Public interface ──────────────────────────────────────────

def search_car_rentals(
    city: str,
    pickup_date: str,
    dropoff_date: str,
    car_class: str | None = None,
    max_results: int = 5,
) -> list[dict]:
    """Search for car rentals. Returns booking redirect links with price estimates."""
    return _generate_booking_links(city, pickup_date, dropoff_date, car_class, max_results)


# ── Transit (curated static data with real URLs) ──────────────

TRANSIT_OPTIONS = {
    "Tokyo": [
        {"name": "7-Day Japan Rail Pass", "type": "rail_pass", "price": 280, "description": "Unlimited travel on JR lines nationwide", "url": "https://www.japan-rail-pass.com"},
        {"name": "Tokyo Metro 72-Hour Pass", "type": "metro_pass", "price": 15, "description": "Unlimited Tokyo Metro and Toei subway rides", "url": "https://www.tokyometro.jp/en/ticket/travel/index.html"},
        {"name": "Suica/Pasmo Card", "type": "transit_card", "price": 5, "description": "Rechargeable IC card for trains, buses, and shops", "url": "https://www.jreast.co.jp/e/pass/suica.html"},
    ],
    "London": [
        {"name": "Oyster Card (7-Day)", "type": "transit_card", "price": 45, "description": "Zones 1-2 weekly cap on Tube, buses, and DLR", "url": "https://tfl.gov.uk/fares/how-to-pay-and-where-to-buy-tickets-and-oyster/pay-as-you-go/oyster-pay-as-you-go"},
        {"name": "London Travelcard (7-Day)", "type": "metro_pass", "price": 55, "description": "Unlimited travel Zones 1-4", "url": "https://tfl.gov.uk/fares/find-fares/tube-and-rail-fares/caps-and-travelcard-prices"},
    ],
    "Paris": [
        {"name": "Paris Visite (5-Day)", "type": "metro_pass", "price": 50, "description": "Unlimited travel on Metro, RER, buses Zones 1-3", "url": "https://www.ratp.fr/en/titres-et-tarifs/paris-visite-travel-pass"},
        {"name": "Navigo Easy Card", "type": "transit_card", "price": 2, "description": "Rechargeable card for single tickets and day passes", "url": "https://www.iledefrance-mobilites.fr"},
    ],
    "New York": [
        {"name": "7-Day Unlimited MetroCard", "type": "metro_pass", "price": 34, "description": "Unlimited subway and local bus rides", "url": "https://new.mta.info/fares"},
    ],
    "Singapore": [
        {"name": "Singapore Tourist Pass (3-Day)", "type": "transit_card", "price": 20, "description": "Unlimited travel on MRT and public buses", "url": "https://thesingaporetouristpass.com.sg"},
    ],
    "Barcelona": [
        {"name": "Hola Barcelona (5-Day)", "type": "metro_pass", "price": 48, "description": "Unlimited public transport including airport train", "url": "https://www.holabarcelona.com"},
    ],
    "Osaka": [
        {"name": "Osaka Amazing Pass (2-Day)", "type": "metro_pass", "price": 34, "description": "Unlimited subway/bus and free entry to 30+ attractions", "url": "https://www.osp.osaka-info.jp/en/"},
    ],
    "Seoul": [
        {"name": "T-money Card", "type": "transit_card", "price": 3, "description": "Rechargeable card for subway, buses, and taxis", "url": "https://www.t-money.co.kr/eng/"},
        {"name": "Discover Seoul Pass (72h)", "type": "metro_pass", "price": 55, "description": "Free transport + entry to 30+ attractions", "url": "https://www.discoverseoulpass.com/"},
    ],
}


def search_transit(city: str) -> list[dict]:
    """Return public transit options for a city."""
    options = TRANSIT_OPTIONS.get(city, [])
    if not options:
        return [{
            "name": f"{city} Public Transit",
            "type": "transit_card",
            "price": 20,
            "description": f"Local transit pass for {city}",
            "url": f"https://www.google.com/search?q={city.replace(' ', '+')}+public+transit+pass",
        }]
    return options
