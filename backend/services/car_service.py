"""
Car rental & transit service.

In production, integrate with Kayak, Rentalcars.com, or Rome2Rio.
"""

import random
import hashlib


CAR_COMPANIES = [
    {"name": "Enterprise", "logo": "https://logos-world.net/wp-content/uploads/2022/01/Enterprise-Rent-A-Car-Logo.png"},
    {"name": "Hertz", "logo": "https://logos-world.net/wp-content/uploads/2021/08/Hertz-Logo.png"},
    {"name": "Avis", "logo": "https://logos-world.net/wp-content/uploads/2021/11/Avis-Logo.png"},
    {"name": "Budget", "logo": "https://logos-world.net/wp-content/uploads/2022/01/Budget-Rent-a-Car-Logo.png"},
    {"name": "National", "logo": "https://logos-world.net/wp-content/uploads/2022/01/National-Car-Rental-Logo.png"},
    {"name": "Sixt", "logo": "https://logos-world.net/wp-content/uploads/2022/01/Sixt-Logo.png"},
]

CAR_CLASSES = {
    "compact": {"examples": ["Toyota Corolla", "Honda Civic", "Hyundai Elantra"], "daily_range": (30, 60), "image": "https://images.unsplash.com/photo-1549317661-bd32c8ce0afa?w=400"},
    "midsize": {"examples": ["Toyota Camry", "Nissan Altima", "Honda Accord"], "daily_range": (45, 85), "image": "https://images.unsplash.com/photo-1590362891991-f776e747a588?w=400"},
    "full_size": {"examples": ["Chevrolet Impala", "Dodge Charger", "Chrysler 300"], "daily_range": (55, 110), "image": "https://images.unsplash.com/photo-1553440569-bcc63803a83d?w=400"},
    "suv": {"examples": ["Toyota RAV4", "Ford Explorer", "Jeep Grand Cherokee"], "daily_range": (65, 140), "image": "https://images.unsplash.com/photo-1519641471654-76ce0107ad1b?w=400"},
    "luxury": {"examples": ["BMW 5 Series", "Mercedes E-Class", "Audi A6"], "daily_range": (120, 280), "image": "https://images.unsplash.com/photo-1555215695-3004980ad54e?w=400"},
    "minivan": {"examples": ["Chrysler Pacifica", "Toyota Sienna", "Honda Odyssey"], "daily_range": (70, 130), "image": "https://images.unsplash.com/photo-1570294646112-27ce4f174e33?w=400"},
    "convertible": {"examples": ["Ford Mustang Convertible", "Chevrolet Camaro", "BMW 4 Series"], "daily_range": (90, 200), "image": "https://images.unsplash.com/photo-1544636331-e26879cd4d9b?w=400"},
}

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
}


def _rental_id(company, car_class, city):
    raw = f"{company}-{car_class}-{city}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def search_car_rentals(
    city: str,
    pickup_date: str,
    dropoff_date: str,
    car_class: str | None = None,
    max_results: int = 5,
) -> list[dict]:
    """Return mock car rental results."""
    try:
        d1 = __import__("datetime").datetime.strptime(pickup_date, "%Y-%m-%d")
        d2 = __import__("datetime").datetime.strptime(dropoff_date, "%Y-%m-%d")
        days = max((d2 - d1).days, 1)
    except Exception:
        days = 3

    classes = [car_class] if car_class and car_class in CAR_CLASSES else list(CAR_CLASSES.keys())
    results = []

    for cls in classes:
        info = CAR_CLASSES[cls]
        companies = random.sample(CAR_COMPANIES, min(2, len(CAR_COMPANIES)))
        for company in companies:
            if len(results) >= max_results:
                break
            daily = round(random.uniform(*info["daily_range"]), 2)
            vehicle = random.choice(info["examples"])
            results.append({
                "id": _rental_id(company["name"], cls, city),
                "company": company,
                "car_class": cls,
                "vehicle": vehicle,
                "image_url": info["image"],
                "price_per_day": daily,
                "total_price": round(daily * days, 2),
                "days": days,
                "pickup_date": pickup_date,
                "dropoff_date": dropoff_date,
                "pickup_location": f"{city} Airport" if random.random() < 0.6 else f"Downtown {city}",
                "features": random.sample(["Automatic", "GPS", "Bluetooth", "Backup Camera", "Heated Seats", "Apple CarPlay", "Cruise Control"], 4),
                "booking_url": f"https://www.kayak.com/cars/{city.replace(' ', '-')}/{pickup_date}/{dropoff_date}",
            })
        if len(results) >= max_results:
            break

    results.sort(key=lambda x: x["total_price"])
    return results[:max_results]


def search_transit(city: str) -> list[dict]:
    """Return public transit options for a city."""
    options = TRANSIT_OPTIONS.get(city, [])
    if not options:
        return [{"name": f"{city} Public Transit", "type": "transit_card", "price": 20, "description": f"Local transit pass for {city}", "url": f"https://www.google.com/search?q={city.replace(' ', '+')}+public+transit+pass"}]
    return options
