"""
Hotel search service.

In production, replace with Booking.com, Hotels.com, Expedia, or Google Hotels API.
"""

import random
import hashlib

HOTEL_CHAINS = [
    "Marriott", "Hilton", "Hyatt", "IHG", "Accor",
    "Four Seasons", "Ritz-Carlton", "W Hotels", "Westin",
    "Sheraton", "Holiday Inn", "Courtyard", "Hampton Inn",
    "Fairmont", "Mandarin Oriental", "Park Hyatt", "Andaz",
    "Ace Hotel", "The Standard", "Kimpton", "Boutique Local",
]

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

AMENITIES_POOL = [
    "Free Wi-Fi", "Pool", "Gym", "Spa", "Restaurant",
    "Bar/Lounge", "Room Service", "Business Center", "Concierge",
    "Airport Shuttle", "Parking", "Pet Friendly", "Breakfast Included",
    "Rooftop Terrace", "Ocean View", "City View", "Balcony",
    "Kitchen/Kitchenette", "Laundry Service", "EV Charging",
]

CITY_NEIGHBORHOODS = {
    "New York": ["Midtown Manhattan", "SoHo", "Upper East Side", "Chelsea", "Tribeca", "Financial District"],
    "Los Angeles": ["Hollywood", "Santa Monica", "Beverly Hills", "Downtown LA", "Venice Beach", "West Hollywood"],
    "London": ["Westminster", "Mayfair", "Covent Garden", "South Kensington", "Shoreditch", "Soho"],
    "Paris": ["Le Marais", "Saint-Germain", "Champs-Élysées", "Montmartre", "Latin Quarter", "Opéra"],
    "Tokyo": ["Shinjuku", "Shibuya", "Ginza", "Roppongi", "Asakusa", "Akihabara"],
    "Osaka": ["Namba", "Umeda", "Shinsaibashi", "Tennoji", "Dotonbori"],
    "Barcelona": ["Gothic Quarter", "Eixample", "La Barceloneta", "Gràcia", "El Born"],
    "Rome": ["Centro Storico", "Trastevere", "Monti", "Prati", "Testaccio"],
    "Dubai": ["Downtown Dubai", "Dubai Marina", "Jumeirah", "Palm Jumeirah", "Business Bay"],
    "Singapore": ["Marina Bay", "Orchard Road", "Chinatown", "Clarke Quay", "Sentosa"],
    "Sydney": ["The Rocks", "Darling Harbour", "Bondi Beach", "Surry Hills", "Circular Quay"],
    "Miami": ["South Beach", "Brickell", "Wynwood", "Downtown Miami", "Coconut Grove"],
    "San Francisco": ["Union Square", "Fisherman's Wharf", "SOMA", "Nob Hill", "Mission District"],
    "Chicago": ["The Loop", "Magnificent Mile", "River North", "Lincoln Park", "Wicker Park"],
    "Bangkok": ["Sukhumvit", "Silom", "Old City", "Riverside", "Siam"],
    "Seoul": ["Gangnam", "Myeongdong", "Hongdae", "Itaewon", "Insadong"],
    "Cancún": ["Hotel Zone", "Downtown Cancún", "Puerto Morelos", "Playa del Carmen"],
    "Honolulu": ["Waikiki", "Ala Moana", "Diamond Head", "Kailua"],
    "Toronto": ["Downtown Core", "Yorkville", "Entertainment District", "Distillery District"],
    "Vancouver": ["Downtown", "Gastown", "Yaletown", "Kitsilano", "West End"],
    "Denver": ["LoDo", "Capitol Hill", "Cherry Creek", "RiNo"],
    "Seattle": ["Downtown", "Capitol Hill", "Pike Place", "Belltown", "Ballard"],
    "Boston": ["Back Bay", "Beacon Hill", "Seaport District", "Cambridge"],
    "Atlanta": ["Midtown", "Buckhead", "Downtown", "Virginia-Highland"],
    "Frankfurt": ["Altstadt", "Sachsenhausen", "Bahnhofsviertel", "Westend"],
}


def _hotel_id(name, city):
    raw = f"{name}-{city}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def search_hotels(
    city: str,
    check_in: str,
    check_out: str,
    guests: int = 2,
    rooms: int = 1,
    budget_tier: str = "mid",        # "budget", "mid", "upscale", "luxury"
    preferred_neighborhood: str | None = None,
    max_results: int = 5,
) -> list[dict]:
    """Return mock hotel search results."""
    price_ranges = {
        "budget": (60, 150),
        "mid": (120, 300),
        "upscale": (250, 550),
        "luxury": (450, 1500),
    }
    star_ranges = {
        "budget": (2, 3),
        "mid": (3, 4),
        "upscale": (4, 5),
        "luxury": (4, 5),
    }

    lo, hi = price_ranges.get(budget_tier, (120, 300))
    star_lo, star_hi = star_ranges.get(budget_tier, (3, 4))

    neighborhoods = CITY_NEIGHBORHOODS.get(city, ["City Center", "Downtown", "Near Airport"])
    if preferred_neighborhood:
        neighborhoods = [preferred_neighborhood] + [n for n in neighborhoods if n != preferred_neighborhood]

    # Calculate nights
    try:
        d1 = __import__("datetime").datetime.strptime(check_in, "%Y-%m-%d")
        d2 = __import__("datetime").datetime.strptime(check_out, "%Y-%m-%d")
        nights = max((d2 - d1).days, 1)
    except Exception:
        nights = 3

    results = []
    used_chains = random.sample(HOTEL_CHAINS, min(max_results + 2, len(HOTEL_CHAINS)))

    for i, chain in enumerate(used_chains):
        if len(results) >= max_results:
            break

        stars = random.randint(star_lo, star_hi)
        nightly = round(random.uniform(lo, hi), 2)
        neighborhood = neighborhoods[i % len(neighborhoods)]
        amenities = sorted(random.sample(AMENITIES_POOL, random.randint(5, 10)))
        rating = round(random.uniform(3.8, 4.9), 1)

        results.append({
            "id": _hotel_id(chain, city),
            "name": f"{chain} {city}" if "Boutique" not in chain else f"The {neighborhood.split()[0]} House",
            "chain": chain,
            "city": city,
            "neighborhood": neighborhood,
            "stars": stars,
            "guest_rating": rating,
            "review_count": random.randint(200, 5000),
            "image_url": random.choice(HOTEL_IMAGES),
            "amenities": amenities,
            "price_per_night": nightly,
            "total_price": round(nightly * nights * rooms, 2),
            "nights": nights,
            "rooms": rooms,
            "check_in": check_in,
            "check_out": check_out,
            "cancellation_policy": random.choice(["Free cancellation until 24h before", "Non-refundable", "Free cancellation until 48h before"]),
            "booking_url": f"https://www.google.com/travel/hotels/{city.replace(' ', '+')}?dates={check_in}_{check_out}",
        })

    results.sort(key=lambda x: x["total_price"])
    return results
