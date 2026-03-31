"""
Flight search service.

In production, replace the mock implementation with calls to a real GDS / OTA
API such as Amadeus, Duffel, Kiwi, or Google Flights via SerpAPI.
"""

import random
import hashlib
from datetime import datetime, timedelta

AIRLINES = [
    {"code": "UA", "name": "United Airlines", "logo": "https://logos-world.net/wp-content/uploads/2021/08/United-Airlines-Logo.png"},
    {"code": "DL", "name": "Delta Air Lines", "logo": "https://logos-world.net/wp-content/uploads/2021/08/Delta-Air-Lines-Logo.png"},
    {"code": "AA", "name": "American Airlines", "logo": "https://logos-world.net/wp-content/uploads/2021/08/American-Airlines-Logo.png"},
    {"code": "BA", "name": "British Airways", "logo": "https://logos-world.net/wp-content/uploads/2020/03/British-Airways-Logo.png"},
    {"code": "LH", "name": "Lufthansa", "logo": "https://logos-world.net/wp-content/uploads/2021/08/Lufthansa-Logo.png"},
    {"code": "AF", "name": "Air France", "logo": "https://logos-world.net/wp-content/uploads/2021/08/Air-France-Logo.png"},
    {"code": "NH", "name": "ANA", "logo": "https://logos-world.net/wp-content/uploads/2023/01/All-Nippon-Airways-Logo.png"},
    {"code": "JL", "name": "Japan Airlines", "logo": "https://logos-world.net/wp-content/uploads/2023/01/Japan-Airlines-Logo.png"},
    {"code": "SQ", "name": "Singapore Airlines", "logo": "https://logos-world.net/wp-content/uploads/2020/03/Singapore-Airlines-Logo.png"},
    {"code": "EK", "name": "Emirates", "logo": "https://logos-world.net/wp-content/uploads/2020/03/Emirates-Logo.png"},
    {"code": "AC", "name": "Air Canada", "logo": "https://logos-world.net/wp-content/uploads/2021/08/Air-Canada-Logo.png"},
    {"code": "QF", "name": "Qantas", "logo": "https://logos-world.net/wp-content/uploads/2023/01/Qantas-Logo.png"},
]

AIRPORTS = {
    "JFK": {"city": "New York", "name": "John F. Kennedy International"},
    "LAX": {"city": "Los Angeles", "name": "Los Angeles International"},
    "ORD": {"city": "Chicago", "name": "O'Hare International"},
    "SFO": {"city": "San Francisco", "name": "San Francisco International"},
    "MIA": {"city": "Miami", "name": "Miami International"},
    "LHR": {"city": "London", "name": "Heathrow"},
    "CDG": {"city": "Paris", "name": "Charles de Gaulle"},
    "NRT": {"city": "Tokyo", "name": "Narita International"},
    "HND": {"city": "Tokyo", "name": "Haneda"},
    "KIX": {"city": "Osaka", "name": "Kansai International"},
    "ICN": {"city": "Seoul", "name": "Incheon International"},
    "SIN": {"city": "Singapore", "name": "Changi"},
    "DXB": {"city": "Dubai", "name": "Dubai International"},
    "FRA": {"city": "Frankfurt", "name": "Frankfurt Airport"},
    "SYD": {"city": "Sydney", "name": "Kingsford Smith"},
    "YYZ": {"city": "Toronto", "name": "Pearson International"},
    "YVR": {"city": "Vancouver", "name": "Vancouver International"},
    "FCO": {"city": "Rome", "name": "Leonardo da Vinci–Fiumicino"},
    "BCN": {"city": "Barcelona", "name": "Josep Tarradellas Barcelona-El Prat"},
    "BKK": {"city": "Bangkok", "name": "Suvarnabhumi"},
    "HNL": {"city": "Honolulu", "name": "Daniel K. Inouye International"},
    "CUN": {"city": "Cancún", "name": "Cancún International"},
    "ATL": {"city": "Atlanta", "name": "Hartsfield-Jackson Atlanta International"},
    "SEA": {"city": "Seattle", "name": "Seattle-Tacoma International"},
    "DEN": {"city": "Denver", "name": "Denver International"},
    "BOS": {"city": "Boston", "name": "Logan International"},
}

HUB_CONNECTIONS = {
    "UA": ["ORD", "SFO", "IAH", "EWR", "DEN"],
    "DL": ["ATL", "DTW", "MSP", "SLC", "SEA"],
    "AA": ["DFW", "CLT", "MIA", "PHX", "ORD"],
    "BA": ["LHR"],
    "LH": ["FRA", "MUC"],
    "AF": ["CDG"],
    "NH": ["NRT", "HND"],
    "JL": ["NRT", "HND"],
    "SQ": ["SIN"],
    "EK": ["DXB"],
    "AC": ["YYZ", "YVR"],
    "QF": ["SYD", "MEL"],
}


def _flight_id(origin, dest, airline, date_str):
    raw = f"{origin}-{dest}-{airline}-{date_str}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def _random_time(hour_min=6, hour_max=22):
    h = random.randint(hour_min, hour_max)
    m = random.choice([0, 15, 30, 45])
    return f"{h:02d}:{m:02d}"


def _add_hours(time_str, hours):
    h, m = map(int, time_str.split(":"))
    total = h * 60 + m + int(hours * 60)
    new_h = (total // 60) % 24
    new_m = total % 60
    days = total // (24 * 60)
    suffix = "" if days == 0 else f" +{days}d"
    return f"{new_h:02d}:{new_m:02d}{suffix}"


def _estimate_flight_hours(origin, dest):
    domestic_pairs = {frozenset(a) for a in [
        ("JFK", "LAX"), ("JFK", "SFO"), ("JFK", "ORD"), ("LAX", "SFO"),
        ("JFK", "MIA"), ("ORD", "LAX"), ("ORD", "SFO"), ("ATL", "JFK"),
        ("SEA", "LAX"), ("SEA", "SFO"), ("DEN", "JFK"), ("BOS", "JFK"),
        ("JFK", "HNL"), ("LAX", "HNL"), ("SFO", "HNL"),
    ]}
    pair = frozenset([origin, dest])
    if pair in domestic_pairs:
        if "HNL" in pair:
            return random.uniform(5.0, 6.5)
        return random.uniform(2.5, 5.5)
    # International heuristic
    return random.uniform(7.0, 14.0)


def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    cabin_class: str = "economy",
    passengers: int = 1,
    max_results: int = 5,
    exclude_airports: list[str] | None = None,
) -> list[dict]:
    """Return mock flight search results."""
    origin = origin.upper()
    destination = destination.upper()
    exclude = set(a.upper() for a in (exclude_airports or []))

    results = []
    chosen_airlines = random.sample(AIRLINES, min(max_results + 2, len(AIRLINES)))

    for airline in chosen_airlines:
        if len(results) >= max_results:
            break

        is_nonstop = random.random() < 0.4
        depart_time = _random_time()
        flight_hours = _estimate_flight_hours(origin, destination)

        segments = []
        if is_nonstop:
            arrive_time = _add_hours(depart_time, flight_hours)
            segments.append({
                "flight_number": f"{airline['code']}{random.randint(100,9999)}",
                "origin": origin,
                "destination": destination,
                "departure_time": depart_time,
                "arrival_time": arrive_time,
                "duration_minutes": int(flight_hours * 60),
                "aircraft": random.choice(["Boeing 777-300ER", "Airbus A350-900", "Boeing 787-9", "Airbus A330-300"]),
            })
            total_duration = int(flight_hours * 60)
            layovers = []
        else:
            # Pick a connection hub
            hubs = HUB_CONNECTIONS.get(airline["code"], ["ORD", "LAX", "LHR"])
            valid_hubs = [h for h in hubs if h not in exclude and h != origin and h != destination]
            if not valid_hubs:
                valid_hubs = [h for h in ["ORD", "LAX", "LHR", "FRA"] if h not in exclude and h != origin and h != destination]
            if not valid_hubs:
                continue

            hub = random.choice(valid_hubs)
            leg1_hours = _estimate_flight_hours(origin, hub) * 0.5
            layover_hours = random.uniform(1.0, 3.5)
            leg2_hours = _estimate_flight_hours(hub, destination) * 0.5

            leg1_arrive = _add_hours(depart_time, leg1_hours)
            leg2_depart_raw = _add_hours(depart_time, leg1_hours + layover_hours)
            leg2_arrive = _add_hours(depart_time, leg1_hours + layover_hours + leg2_hours)

            segments = [
                {
                    "flight_number": f"{airline['code']}{random.randint(100,9999)}",
                    "origin": origin,
                    "destination": hub,
                    "departure_time": depart_time,
                    "arrival_time": leg1_arrive,
                    "duration_minutes": int(leg1_hours * 60),
                    "aircraft": random.choice(["Boeing 737-800", "Airbus A320neo", "Boeing 787-9"]),
                },
                {
                    "flight_number": f"{airline['code']}{random.randint(100,9999)}",
                    "origin": hub,
                    "destination": destination,
                    "departure_time": leg2_depart_raw,
                    "arrival_time": leg2_arrive,
                    "duration_minutes": int(leg2_hours * 60),
                    "aircraft": random.choice(["Boeing 777-300ER", "Airbus A350-900", "Boeing 787-9"]),
                },
            ]
            total_duration = int((leg1_hours + layover_hours + leg2_hours) * 60)
            hub_info = AIRPORTS.get(hub, {"city": hub, "name": hub})
            layovers = [{
                "airport": hub,
                "airport_name": hub_info["name"],
                "city": hub_info["city"],
                "duration_minutes": int(layover_hours * 60),
            }]

        # Pricing
        base_prices = {"economy": (250, 1200), "premium_economy": (500, 2000), "business": (1500, 6000), "first": (4000, 15000)}
        lo, hi = base_prices.get(cabin_class, (250, 1200))
        price_per_pax = round(random.uniform(lo, hi), 2)

        results.append({
            "id": _flight_id(origin, destination, airline["code"], departure_date),
            "airline": airline,
            "segments": segments,
            "layovers": layovers,
            "is_nonstop": is_nonstop,
            "total_duration_minutes": total_duration,
            "cabin_class": cabin_class,
            "price_per_person": price_per_pax,
            "total_price": round(price_per_pax * passengers, 2),
            "passengers": passengers,
            "departure_date": departure_date,
            "booking_url": f"https://www.google.com/travel/flights?q={origin}+to+{destination}+{departure_date}",
        })

    results.sort(key=lambda x: x["total_price"])
    return results
