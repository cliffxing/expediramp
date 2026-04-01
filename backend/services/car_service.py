"""
Car rental & transit service.

Car rentals: RapidAPI Booking.com real-time search → fallback to booking-redirect links.
Transit: SerpAPI Google Search for real transit pass info → fallback to curated data.
"""

import logging
import hashlib
import requests
import re
import urllib.parse
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

TRANSIT_REFERENCE_LINKS = {
    "chongqing": "https://www.cqmetro.cn/",
    "tokyo": "https://www.tokyometro.jp/en/ticket/travel/index.html",
    "london": "https://tfl.gov.uk/fares/",
    "paris": "https://www.iledefrance-mobilites.fr/en/tickets-fares",
    "new york": "https://new.mta.info/fares",
    "singapore": "https://thesingaporetouristpass.com.sg/",
    "barcelona": "https://www.holabarcelona.com/",
    "osaka": "https://www.osakametro.co.jp/en/tickets/otps/",
    "seoul": "https://www.t-money.co.kr/eng/",
}

CURRENCY_SYMBOLS = {
    "USD": "$",
    "EUR": "EUR",
    "GBP": "GBP",
    "JPY": "JPY",
    "CNY": "RMB",
    "SGD": "SGD",
    "KRW": "KRW",
}


def _currency_symbol(code: str | None) -> str:
    return CURRENCY_SYMBOLS.get((code or "").upper(), (code or "USD").upper())


def _detect_currency(text: str) -> tuple[str, str]:
    lower = (text or "").lower()

    if any(token in lower for token in ("cny", "rmb", "yuan", "renminbi", "元", "￥", "¥")):
        return "CNY", _currency_symbol("CNY")
    if any(token in lower for token in ("jpy", "yen")):
        return "JPY", _currency_symbol("JPY")
    if any(token in lower for token in ("gbp", "pound", "pounds", "£")):
        return "GBP", _currency_symbol("GBP")
    if any(token in lower for token in ("eur", "euro", "euros", "€")):
        return "EUR", _currency_symbol("EUR")
    if any(token in lower for token in ("sgd", "singapore dollar", "singapore dollars")):
        return "SGD", _currency_symbol("SGD")
    if any(token in lower for token in ("krw", "won", "₩")):
        return "KRW", _currency_symbol("KRW")
    return "USD", _currency_symbol("USD")


def _format_price_display(price: float, currency_code: str, currency_symbol: str) -> str:
    if price <= 0:
        return ""
    if currency_code == "USD":
        return f"${price:g}"
    return f"{currency_symbol} {price:g}"


def _best_transit_link(city: str, link: str = "") -> str:
    link = (link or "").strip()
    if link and "google.com/search" not in link:
        return link
    return TRANSIT_REFERENCE_LINKS.get(city.strip().lower(), "")


def _build_car_search_url(city: str, pickup_date: str, dropoff_date: str) -> str:
    try:
        pickup = datetime.strptime(pickup_date, "%Y-%m-%d").strftime("%m/%d/%Y")
        dropoff = datetime.strptime(dropoff_date, "%Y-%m-%d").strftime("%m/%d/%Y")
    except Exception:
        pickup = pickup_date
        dropoff = dropoff_date

    city_enc = urllib.parse.quote(city)
    return (
        f"https://www.expedia.com/carsearch"
        f"?locn={city_enc}&date1={pickup}&date2={dropoff}"
    )


def _normalize_car_booking_url(raw_url: str | None, city: str, pickup_date: str, dropoff_date: str) -> str:
    url = (raw_url or "").strip()
    if not url:
        return _build_car_search_url(city, pickup_date, dropoff_date)

    lowered = url.lower()
    if "booking.com/cars/search" in lowered:
        return _build_car_search_url(city, pickup_date, dropoff_date)

    return url


# ── RapidAPI Booking.com car rental search (PRIMARY) ──────────

def _search_rapidapi_cars(
    city: str,
    pickup_date: str,
    dropoff_date: str,
    car_class: str | None,
    max_results: int,
) -> list[dict]:
    """
    Search for car rentals using the Booking.com RapidAPI (booking-com15).
    Returns real-time results with prices, vehicle details, and booking links.
    """
    if not Config.RAPIDAPI_KEY:
        raise ValueError("RAPIDAPI_KEY not set")

    try:
        days = max(
            (datetime.strptime(dropoff_date, "%Y-%m-%d") - datetime.strptime(pickup_date, "%Y-%m-%d")).days,
            1,
        )
    except Exception:
        days = 3

    # Step 1: Resolve city to a Booking.com location ID
    location_id = _resolve_car_location(city)
    if not location_id:
        logger.warning("Could not resolve car rental location for: %s", city)
        raise ValueError(f"Location not found: {city}")

    # Step 2: Search car rentals
    url = "https://booking-com15.p.rapidapi.com/api/v1/cars/searchCarRental"
    params = {
        "pick_up_location_id": location_id,
        "drop_off_location_id": location_id,
        "pick_up_date": pickup_date,
        "drop_off_date": dropoff_date,
        "pick_up_time": "10:00",
        "drop_off_time": "10:00",
        "currency_code": "USD",
    }
    headers = {
        "X-RapidAPI-Key": Config.RAPIDAPI_KEY,
        "X-RapidAPI-Host": "booking-com15.p.rapidapi.com",
    }

    resp = requests.get(url, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    # Parse results
    results = []
    vehicles = data.get("data", {}).get("search_results", [])
    if not vehicles:
        # Try alternate response structures
        vehicles = data.get("data", [])
        if isinstance(data.get("data"), dict):
            vehicles = data["data"].get("results", data["data"].get("vehicles", []))

    for vehicle in vehicles:
        try:
            # Extract pricing
            price_info = vehicle.get("pricing", vehicle.get("price_info", {}))
            total_price = (
                price_info.get("total_price")
                or price_info.get("price")
                or vehicle.get("price_all_days")
                or vehicle.get("totalPrice")
                or 0
            )
            total_price = float(total_price) if total_price else 0

            price_per_day = round(total_price / max(days, 1), 2) if total_price else 0

            # Extract vehicle info
            vehicle_info = vehicle.get("vehicle_info", vehicle.get("vehicle", {}))
            vehicle_name = (
                vehicle_info.get("v_name")
                or vehicle_info.get("name")
                or vehicle.get("vehicle_name")
                or vehicle.get("name")
                or "Car"
            )
            vehicle_group = (
                vehicle_info.get("group")
                or vehicle_info.get("category")
                or vehicle.get("car_class")
                or vehicle.get("category")
                or "midsize"
            )

            # Map Booking.com groups to our car classes
            group_lower = str(vehicle_group).lower()
            mapped_class = "midsize"
            if any(k in group_lower for k in ("compact", "small", "mini", "economy")):
                mapped_class = "compact"
            elif any(k in group_lower for k in ("full", "large", "standard")):
                mapped_class = "full_size"
            elif any(k in group_lower for k in ("suv", "crossover", "4x4", "off-road")):
                mapped_class = "suv"
            elif any(k in group_lower for k in ("luxury", "premium", "elite")):
                mapped_class = "luxury"
            elif any(k in group_lower for k in ("van", "minivan", "people")):
                mapped_class = "minivan"
            elif any(k in group_lower for k in ("convertible", "cabrio")):
                mapped_class = "convertible"

            # Filter by requested car class if specified
            if car_class and car_class != mapped_class:
                continue

            # Extract supplier info
            supplier = vehicle.get("supplier", vehicle.get("provider", {}))
            supplier_name = (
                supplier.get("name")
                or vehicle.get("supplier_name")
                or vehicle.get("company_name")
                or "Rental Agency"
            )
            supplier_logo = supplier.get("logo_url", supplier.get("logo", ""))

            # Extract image
            image_url = (
                vehicle_info.get("image_url")
                or vehicle_info.get("image")
                or vehicle.get("image_url")
                or vehicle.get("image")
                or ""
            )
            if not image_url:
                image_url = CAR_IMAGES.get(mapped_class, CAR_IMAGES["midsize"])

            # Extract features
            features = []
            transmission = (
                vehicle_info.get("transmission")
                or vehicle.get("transmission")
                or ""
            )
            if transmission:
                features.append(transmission.title())
            if vehicle_info.get("aircon") or vehicle.get("air_conditioning"):
                features.append("A/C")
            seats = vehicle_info.get("seats") or vehicle.get("seats")
            if seats:
                features.append(f"{seats} seats")
            doors = vehicle_info.get("doors") or vehicle.get("doors")
            if doors:
                features.append(f"{doors} doors")
            fuel_policy = vehicle.get("fuel_policy") or vehicle_info.get("fuel_policy")
            if fuel_policy:
                features.append(fuel_policy.replace("_", " ").title())
            if not features:
                features = ["Automatic", "A/C"]

            # Build booking URL
            booking_url = _normalize_car_booking_url((
                vehicle.get("deeplink")
                or vehicle.get("booking_url")
                or vehicle.get("url")
                or ""
            ), city, pickup_date, dropoff_date)

            # Pickup location
            pickup_location = (
                vehicle.get("pick_up_location", {}).get("name")
                or vehicle.get("pickup_location")
                or f"{city} Airport or Downtown"
            )

            results.append({
                "id": hashlib.md5(f"{vehicle_name}-{supplier_name}-{total_price}".encode()).hexdigest()[:12],
                "company": {"name": supplier_name, "logo": supplier_logo},
                "car_class": mapped_class,
                "vehicle": vehicle_name,
                "image_url": image_url,
                "price_per_day": price_per_day,
                "total_price": round(total_price, 2),
                "days": days,
                "pickup_date": pickup_date,
                "dropoff_date": dropoff_date,
                "pickup_location": pickup_location,
                "features": features[:5],
                "booking_url": booking_url,
                "is_estimate": False,
            })

            if len(results) >= max_results:
                break
        except Exception as e:
            logger.debug("Skipping car result due to parse error: %s", e)
            continue

    results.sort(key=lambda x: (x["total_price"] == 0, x["total_price"]))
    return results[:max_results]


def _resolve_car_location(city: str) -> str | None:
    """
    Resolve a city name to a Booking.com car rental location ID.
    Uses the searchDestination endpoint.
    """
    if not Config.RAPIDAPI_KEY:
        return None

    url = "https://booking-com15.p.rapidapi.com/api/v1/cars/searchDestination"
    params = {"query": city}
    headers = {
        "X-RapidAPI-Key": Config.RAPIDAPI_KEY,
        "X-RapidAPI-Host": "booking-com15.p.rapidapi.com",
    }

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        locations = data.get("data", [])
        if not locations:
            return None

        # Prefer airport locations, then city centers
        for loc in locations:
            loc_type = str(loc.get("type", "")).lower()
            if "airport" in loc_type:
                return loc.get("id") or loc.get("location_id")

        # Fall back to first result
        first = locations[0]
        return first.get("id") or first.get("location_id")

    except Exception as e:
        logger.warning("Car location search failed for %s: %s", city, e)
        return None


# ── Fallback: Booking Links Generator ─────────────────────────

def _generate_booking_links(
    city: str,
    pickup_date: str,
    dropoff_date: str,
    car_class: str | None,
    max_results: int,
) -> list[dict]:
    """
    Fallback: Generate booking redirect links to reliable car rental aggregators.
    Used when the RapidAPI Booking.com search is unavailable.
    """
    try:
        d1 = datetime.strptime(pickup_date, "%Y-%m-%d")
        d2 = datetime.strptime(dropoff_date, "%Y-%m-%d")
        days = max((d2 - d1).days, 1)
    except Exception:
        days = 3

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

    booking_url = _build_car_search_url(city, pickup_date, dropoff_date)

    for cls in classes:
        info = estimates[cls]
        avg_daily = round((info["daily"][0] + info["daily"][1]) / 2, 2)
        total_est = round(avg_daily * days, 2)
        vehicle = info["examples"][0]

        results.append({
            "id": hashlib.md5(f"{cls}-{city}-booking".encode()).hexdigest()[:12],
            "company": {"name": "Expedia", "logo": ""},
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
            "booking_url": booking_url,
            "is_estimate": True,
        })

        if len(results) >= max_results:
            break

    results.sort(key=lambda x: x["total_price"])
    return results[:max_results]


# ── Public interface: Car Rentals ─────────────────────────────

def search_car_rentals(
    city: str,
    pickup_date: str,
    dropoff_date: str,
    car_class: str | None = None,
    max_results: int = 5,
) -> list[dict]:
    """
    Search for car rentals.
    Primary: RapidAPI Booking.com real-time search.
    Fallback: Booking redirect links with price estimates.
    """
    # Try RapidAPI Booking.com first
    if Config.RAPIDAPI_KEY:
        try:
            results = _search_rapidapi_cars(city, pickup_date, dropoff_date, car_class, max_results)
            if results:
                logger.info(
                    "RapidAPI car search returned %d results for %s", len(results), city
                )
                return results
            logger.warning("RapidAPI car search returned 0 results for %s, using fallback", city)
        except Exception:
            logger.exception("RapidAPI car search failed for %s, using fallback", city)

    # Fallback to generated booking links
    return _generate_booking_links(city, pickup_date, dropoff_date, car_class, max_results)


# ── SerpAPI Google Search for transit info (PRIMARY) ──────────

def _search_serpapi_transit(city: str) -> list[dict]:
    """
    Use SerpAPI Google Search to find real public transit pass options for a city.
    Searches for transit passes, travel cards, and tourist transport options.
    """
    if not Config.SERPAPI_KEY:
        raise ValueError("SERPAPI_KEY not set")

    # Search for transit passes in the target city
    query = f"{city} transit pass travel card price"
    params = {
        "engine": "google_search",
        "q": query,
        "num": 5,
        "hl": "en",
        "gl": "us",
        "api_key": Config.SERPAPI_KEY,
    }

    resp = requests.get("https://serpapi.com/search.json", params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    results = []

    # Parse organic results for transit information
    organic = data.get("organic_results", [])
    for item in organic[:8]:
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        link = item.get("link", "")

        # Filter for transit-relevant results
        transit_keywords = [
            "pass", "card", "ticket", "metro", "subway", "transit",
            "travel card", "transport", "bus", "rail", "tram",
            "oyster", "suica", "navigo", "t-money", "metrocard",
        ]
        combined = (title + " " + snippet).lower()
        if not any(kw in combined for kw in transit_keywords):
            continue

        # Extract transit pass info from the result
        pass_info = _parse_transit_result(title, snippet, link, city)
        if pass_info:
            results.append(pass_info)
        elif link:
            fallback_info = _fallback_transit_result(title, snippet, link, city)
            if fallback_info:
                results.append(fallback_info)

    # Also check knowledge graph / answer box for quick info
    answer_box = data.get("answer_box", {})
    if answer_box:
        ab_title = answer_box.get("title", "") or answer_box.get("answer", "")
        ab_snippet = answer_box.get("snippet", "") or answer_box.get("description", "")
        ab_link = answer_box.get("link", "")
        if ab_title and any(kw in (ab_title + ab_snippet).lower() for kw in ["transit", "pass", "card", "metro"]):
            pass_info = _parse_transit_result(ab_title, ab_snippet, ab_link, city)
            if pass_info:
                results.insert(0, pass_info)
            elif ab_link:
                fallback_info = _fallback_transit_result(ab_title, ab_snippet, ab_link, city)
                if fallback_info:
                    results.insert(0, fallback_info)

    # Deduplicate by name
    seen = set()
    unique = []
    for r in results:
        key = r["name"].lower()[:30]
        if key not in seen:
            seen.add(key)
            unique.append(r)

    return unique[:5]


def _parse_transit_result(title: str, snippet: str, link: str, city: str) -> dict | None:
    """
    Parse a Google search result into a transit pass object.
    Attempts to extract price, name, and type from the search result.
    """
    import re

    # Try to extract a price from the snippet or title
    price = 0
    price_matches = re.findall(
        r'[\$€£¥]\s*(\d+(?:\.\d{2})?)|(\d+(?:\.\d{2})?)\s*(?:USD|EUR|GBP|dollars?)',
        snippet + " " + title,
        re.IGNORECASE,
    )
    if price_matches:
        for match in price_matches:
            val = match[0] or match[1]
            try:
                p = float(val)
                if 1 <= p <= 500:  # Reasonable transit pass price range
                    price = p
                    break
            except ValueError:
                continue

    # Determine pass type
    pass_type = "transit_card"
    lower = (title + " " + snippet).lower()
    if any(k in lower for k in ["rail pass", "train pass", "jr pass"]):
        pass_type = "rail_pass"
    elif any(k in lower for k in ["metro pass", "subway pass", "unlimited"]):
        pass_type = "metro_pass"
    elif any(k in lower for k in ["day pass", "day ticket", "24-hour", "48-hour", "72-hour"]):
        pass_type = "day_pass"

    # Clean up the title
    name = title.strip()
    # Remove common suffixes that aren't helpful
    for suffix in [" - Google Search", " | Google Maps", " - Wikipedia"]:
        name = name.replace(suffix, "")
    name = name[:80]  # Truncate long titles

    if not name:
        return None

    # Build a useful description from the snippet
    description = snippet[:200].strip() if snippet else f"Public transit option for {city}"

    return {
        "name": name,
        "type": pass_type,
        "price": price,
        "description": description,
        "url": link or f"https://www.google.com/search?q={urllib.parse.quote(city)}+public+transit+pass",
    }


# ── Fallback: Curated transit data ────────────────────────────

def _parse_transit_result_legacy(title: str, snippet: str, link: str, city: str) -> dict | None:
    text = f"{snippet} {title}".strip()
    currency_code, currency_symbol = _detect_currency(text)

    price = 0
    price_patterns = [
        r'(?:rmb|cny|yuan|renminbi|¥|￥|元)\s*(\d+(?:\.\d{1,2})?)',
        r'(\d+(?:\.\d{1,2})?)\s*(?:rmb|cny|yuan|renminbi|元)',
        r'(?:\$|usd)\s*(\d+(?:\.\d{1,2})?)',
        r'(\d+(?:\.\d{1,2})?)\s*(?:usd|eur|gbp|sgd|krw|jpy|dollars?)',
        r'(?:€|£|₩)\s*(\d+(?:\.\d{1,2})?)',
    ]
    for pattern in price_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        try:
            candidate = float(match.group(1))
            if 1 <= candidate <= 500:
                price = candidate
                break
        except ValueError:
            continue

    pass_type = "transit_card"
    lower = (title + " " + snippet).lower()
    if any(k in lower for k in ["rail pass", "train pass", "jr pass"]):
        pass_type = "rail_pass"
    elif any(k in lower for k in ["metro pass", "subway pass", "unlimited"]):
        pass_type = "metro_pass"
    elif any(k in lower for k in ["day pass", "day ticket", "24-hour", "48-hour", "72-hour"]):
        pass_type = "day_pass"

    name = title.strip()
    for suffix in [" - Google Search", " | Google Maps", " - Wikipedia"]:
        name = name.replace(suffix, "")
    name = name[:80]
    if not name:
        return None

    booking_url = _best_transit_link(city, link)
    description = snippet[:200].strip() if snippet else f"Public transit option for {city}"
    return {
        "name": name,
        "type": pass_type,
        "price": price,
        "currency_code": currency_code,
        "currency_symbol": currency_symbol,
        "price_display": _format_price_display(price, currency_code, currency_symbol),
        "description": description,
        "url": booking_url,
        "booking_url": booking_url,
    }


def _fallback_transit_result(title: str, snippet: str, link: str, city: str) -> dict | None:
    name = title.strip() or f"{city} Public Transit"
    if not name:
        return None

    booking_url = _best_transit_link(city, link)
    return {
        "name": name[:80],
        "type": "transit_card",
        "price": 0,
        "currency_code": "USD",
        "currency_symbol": _currency_symbol("USD"),
        "price_display": "",
        "description": snippet[:200].strip() if snippet else f"Public transit information for {city}",
        "url": booking_url,
        "booking_url": booking_url,
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
    "Osaka": [
        {"name": "Osaka Amazing Pass (2-Day)", "type": "metro_pass", "price": 34, "description": "Unlimited subway/bus and free entry to 30+ attractions", "url": "https://www.osp.osaka-info.jp/en/"},
    ],
    "Seoul": [
        {"name": "T-money Card", "type": "transit_card", "price": 3, "description": "Rechargeable card for subway, buses, and taxis", "url": "https://www.t-money.co.kr/eng/"},
        {"name": "Discover Seoul Pass (72h)", "type": "metro_pass", "price": 55, "description": "Free transport + entry to 30+ attractions", "url": "https://www.discoverseoulpass.com/"},
    ],
    "Chongqing": [
        {"name": "Chongqing Public Transit", "type": "transit_card", "price": 20, "currency_code": "CNY", "currency_symbol": "RMB", "description": "Reference transit fare and pass information for Chongqing rail transit and local buses", "url": "https://www.cqmetro.cn/", "booking_url": "https://www.cqmetro.cn/"},
    ],
}


# ── Public interface: Transit ─────────────────────────────────

def search_transit(city: str) -> list[dict]:
    """
    Return public transit options for a city.
    Primary: SerpAPI Google Search for real-time transit pass information.
    Fallback: Curated static data with real URLs.
    """
    # Try SerpAPI search first
    if Config.SERPAPI_KEY:
        try:
            results = _search_serpapi_transit(city)
            if results:
                logger.info(
                    "SerpAPI transit search returned %d results for %s", len(results), city
                )
                return results
            logger.warning("SerpAPI transit search returned 0 results for %s, checking curated data", city)
        except Exception:
            logger.exception("SerpAPI transit search failed for %s, using fallback", city)

    # Fallback to curated data
    options = TRANSIT_OPTIONS.get(city, [])
    if options:
        normalized = []
        for option in options:
            normalized.append({
                **option,
                "currency_code": option.get("currency_code", "USD"),
                "currency_symbol": option.get("currency_symbol", _currency_symbol(option.get("currency_code", "USD"))),
                "price_display": option.get(
                    "price_display",
                    _format_price_display(option.get("price", 0), option.get("currency_code", "USD"), option.get("currency_symbol", _currency_symbol(option.get("currency_code", "USD")))),
                ),
                "booking_url": option.get("booking_url", option.get("url", "")),
            })
        return normalized

    # Last resort: no fabricated search URL
    return [{
        "name": f"{city} Public Transit",
        "type": "transit_card",
        "price": 0,
        "currency_code": "USD",
        "currency_symbol": "$",
        "price_display": "",
        "description": f"Local transit pass for {city}",
        "url": _best_transit_link(city),
        "booking_url": _best_transit_link(city),
    }]
