"""
Car rental & transit service.

Car rentals: RapidAPI Booking.com real-time search → fallback to booking-redirect links.
Transit: SerpAPI Google Search for real transit pass info → fallback to curated data.
All transit prices are converted to USD. Pass quantity is calculated from days_in_city.
"""

import logging
import hashlib
import requests
import re
import math
import urllib.parse
from datetime import datetime

from config import Config

logger = logging.getLogger(__name__)


# ── Car images (royalty-free from Unsplash) ────────────────────

CAR_IMAGES = {
    "compact":     "https://images.unsplash.com/photo-1549317661-bd32c8ce0afa?w=400",
    "midsize":     "https://images.unsplash.com/photo-1590362891991-f776e747a588?w=400",
    "full_size":   "https://images.unsplash.com/photo-1553440569-bcc63803a83d?w=400",
    "suv":         "https://images.unsplash.com/photo-1519641471654-76ce0107ad1b?w=400",
    "luxury":      "https://images.unsplash.com/photo-1555215695-3004980ad54e?w=400",
    "minivan":     "https://images.unsplash.com/photo-1570294646112-27ce4f174e33?w=400",
    "convertible": "https://images.unsplash.com/photo-1544636331-e26879cd4d9b?w=400",
}

TRANSIT_REFERENCE_LINKS = {
    "chongqing": "https://www.cqmetro.cn/",
    "tokyo":     "https://www.tokyometro.jp/en/ticket/travel/index.html",
    "london":    "https://tfl.gov.uk/fares/",
    "paris":     "https://www.iledefrance-mobilites.fr/en/tickets-fares",
    "new york":  "https://new.mta.info/fares",
    "singapore": "https://thesingaporetouristpass.com.sg/",
    "barcelona": "https://www.holabarcelona.com/",
    "osaka":     "https://www.osakametro.co.jp/en/tickets/otps/",
    "seoul":     "https://www.t-money.co.kr/eng/",
}

CURRENCY_SYMBOLS = {
    "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥",
    "CNY": "¥", "SGD": "S$", "KRW": "₩",
}


def _currency_symbol(code: str | None) -> str:
    return CURRENCY_SYMBOLS.get((code or "").upper(), (code or "USD").upper())


def _detect_currency(text: str) -> tuple[str, str]:
    lower = (text or "").lower()
    if any(t in lower for t in ("cny", "rmb", "yuan", "renminbi", "元", "￥", "¥")):
        return "CNY", _currency_symbol("CNY")
    if any(t in lower for t in ("jpy", "yen")):
        return "JPY", _currency_symbol("JPY")
    if any(t in lower for t in ("gbp", "pound", "pounds", "£")):
        return "GBP", _currency_symbol("GBP")
    if any(t in lower for t in ("eur", "euro", "euros", "€")):
        return "EUR", _currency_symbol("EUR")
    if any(t in lower for t in ("sgd", "singapore dollar", "singapore dollars")):
        return "SGD", _currency_symbol("SGD")
    if any(t in lower for t in ("krw", "won", "₩")):
        return "KRW", _currency_symbol("KRW")
    return "USD", _currency_symbol("USD")


def _to_usd(price: float, currency_code: str) -> float:
    """Convert price to USD using live rates with hardcoded fallback."""
    if currency_code == "USD" or price <= 0:
        return price
    try:
        from services.currency_conversion import get_usd_rate
        rate = get_usd_rate(currency_code)
        return round(price * rate, 2)
    except Exception:
        fallback = {
            "EUR": 1.08, "GBP": 1.27, "JPY": 0.0067, "CNY": 0.14,
            "SGD": 0.74, "KRW": 0.00074, "CAD": 0.73, "AUD": 0.65,
        }
        return round(price * fallback.get(currency_code.upper(), 1.0), 2)


def _best_transit_link(city: str, link: str = "") -> str:
    link = (link or "").strip()
    if link and "google.com/search" not in link:
        return link
    return TRANSIT_REFERENCE_LINKS.get(city.strip().lower(), "")


# ── Pass duration & quantity logic ────────────────────────────

# Sentinel: rechargeable cards that cover the entire stay (buy once, top up)
_UNLIMITED_DURATION = 999


def _detect_pass_duration(name: str, pass_type: str) -> int:
    """
    Infer how many days a single pass covers from its name and type.
    Returns _UNLIMITED_DURATION (999) for rechargeable top-up cards.
    """
    lower = name.lower()

    # Explicit month count: "1-Month Pass", "30-Day Pass"
    m = re.search(r'(\d+)\s*-?\s*month', lower)
    if m:
        return int(m.group(1)) * 30

    # Explicit week count: "2-Week Pass"
    m = re.search(r'(\d+)\s*-?\s*week', lower)
    if m:
        return int(m.group(1)) * 7

    # Explicit day count: "7-Day", "5-Day", "3 Day"
    m = re.search(r'(\d+)\s*-?\s*day', lower)
    if m:
        return int(m.group(1))

    # Hour-based: "72-Hour", "24-Hour", "48-Hour"
    m = re.search(r'(\d+)\s*-?\s*hour', lower)
    if m:
        return max(1, math.ceil(int(m.group(1)) / 24))

    # Keyword fallbacks
    if any(k in lower for k in ("weekly", "7 day")):
        return 7
    if any(k in lower for k in ("monthly", "30 day")):
        return 30
    if any(k in lower for k in ("annual", "yearly", "365")):
        return 365

    # Rechargeable cards: buy once, top up as needed — always quantity 1
    if any(k in lower for k in ("oyster", "suica", "pasmo", "t-money", "t money",
                                 "octopus", "navigo easy", "rechargeable")):
        return _UNLIMITED_DURATION

    # Pass type fallbacks
    if pass_type == "rail_pass":
        return 7
    if pass_type == "metro_pass":
        return 7
    if pass_type == "day_pass":
        return 1

    # Unknown — treat as day pass (safe, never under-counts)
    return 1


def _calculate_quantity(days_in_city: int, pass_duration: int) -> int:
    """How many passes are needed to cover the stay?"""
    if pass_duration >= _UNLIMITED_DURATION:
        return 1
    return math.ceil(days_in_city / pass_duration)


def _pass_label(name: str, quantity: int) -> str:
    """E.g. '2× 7-Day Unlimited MetroCard'"""
    return f"{quantity}× {name}" if quantity > 1 else name


def _enrich_with_quantity(result: dict, days_in_city: int) -> dict:
    """
    Attach quantity, total_price, pass_duration_days, and pass_label to a
    raw pass result (price already in USD).
    """
    name = result.get("name", "Transit Pass")
    pass_type = result.get("type", "transit_card")
    price_per_pass = result.get("price", 0)

    duration = _detect_pass_duration(name, pass_type)
    quantity = _calculate_quantity(days_in_city, duration)
    total_price = round(price_per_pass * quantity, 2)

    return {
        **result,
        "price_per_pass": price_per_pass,
        "quantity": quantity,
        # Report actual days covered per pass (cap 999 to days_in_city for display)
        "pass_duration_days": duration if duration < _UNLIMITED_DURATION else days_in_city,
        "days_in_city": days_in_city,
        "total_price": total_price,
        "pass_label": _pass_label(name, quantity),
    }


def _pick_best_pass(options: list[dict], days_in_city: int) -> dict:
    """
    Choose the pass option that minimises total cost for the stay.
    Falls back to the first option if all prices are 0.
    """
    if len(options) == 1:
        return options[0]

    best, best_cost = None, float("inf")
    for opt in options:
        price = opt.get("price", 0)
        if price <= 0:
            continue
        name = opt.get("name", "")
        pass_type = opt.get("type", "transit_card")
        duration = _detect_pass_duration(name, pass_type)
        qty = _calculate_quantity(days_in_city, duration)
        total = price * qty
        if total < best_cost:
            best_cost = total
            best = opt

    return best or options[0]


# ── Car rental helpers ────────────────────────────────────────

def _build_car_search_url(city: str, pickup_date: str, dropoff_date: str) -> str:
    try:
        pickup = datetime.strptime(pickup_date, "%Y-%m-%d").strftime("%m/%d/%Y")
        dropoff = datetime.strptime(dropoff_date, "%Y-%m-%d").strftime("%m/%d/%Y")
    except Exception:
        pickup, dropoff = pickup_date, dropoff_date
    city_enc = urllib.parse.quote(city)
    return f"https://www.expedia.com/carsearch?locn={city_enc}&date1={pickup}&date2={dropoff}"


def _normalize_car_booking_url(raw_url: str | None, city: str, pickup_date: str, dropoff_date: str) -> str:
    url = (raw_url or "").strip()
    if not url or "booking.com/cars/search" in url.lower():
        return _build_car_search_url(city, pickup_date, dropoff_date)
    return url


# ── RapidAPI Booking.com car rental search (PRIMARY) ──────────

def _search_rapidapi_cars(
    city: str, pickup_date: str, dropoff_date: str,
    car_class: str | None, max_results: int,
) -> list[dict]:
    if not Config.RAPIDAPI_KEY:
        raise ValueError("RAPIDAPI_KEY not set")

    try:
        days = max((datetime.strptime(dropoff_date, "%Y-%m-%d") -
                    datetime.strptime(pickup_date, "%Y-%m-%d")).days, 1)
    except Exception:
        days = 3

    location_id = _resolve_car_location(city)
    if not location_id:
        raise ValueError(f"Location not found: {city}")

    url = "https://booking-com15.p.rapidapi.com/api/v1/cars/searchCarRental"
    params = {
        "pick_up_location_id": location_id, "drop_off_location_id": location_id,
        "pick_up_date": pickup_date, "drop_off_date": dropoff_date,
        "pick_up_time": "10:00", "drop_off_time": "10:00", "currency_code": "USD",
    }
    headers = {"X-RapidAPI-Key": Config.RAPIDAPI_KEY, "X-RapidAPI-Host": "booking-com15.p.rapidapi.com"}

    resp = requests.get(url, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    results = []
    vehicles = data.get("data", {}).get("search_results", [])
    if not vehicles:
        vehicles = data.get("data", [])
        if isinstance(data.get("data"), dict):
            vehicles = data["data"].get("results", data["data"].get("vehicles", []))

    for vehicle in vehicles:
        try:
            price_info = vehicle.get("pricing", vehicle.get("price_info", {}))
            total_price = float(
                price_info.get("total_price") or price_info.get("price") or
                price_info.get("price_all_days") or price_info.get("totalPrice") or 0
            )
            price_per_day = round(total_price / max(days, 1), 2) if total_price else 0

            vehicle_info = vehicle.get("vehicle_info", vehicle.get("vehicle", {}))
            vehicle_name = (vehicle_info.get("v_name") or vehicle_info.get("name") or
                            vehicle.get("vehicle_name") or vehicle.get("name") or "Car")
            vehicle_group = (vehicle_info.get("group") or vehicle_info.get("category") or
                             vehicle.get("car_class") or vehicle.get("category") or "midsize")

            gl = str(vehicle_group).lower()
            mapped_class = "midsize"
            if any(k in gl for k in ("compact", "small", "mini", "economy")):   mapped_class = "compact"
            elif any(k in gl for k in ("full", "large", "standard")):           mapped_class = "full_size"
            elif any(k in gl for k in ("suv", "crossover", "4x4", "off-road")): mapped_class = "suv"
            elif any(k in gl for k in ("luxury", "premium", "elite")):          mapped_class = "luxury"
            elif any(k in gl for k in ("van", "minivan", "people")):            mapped_class = "minivan"
            elif any(k in gl for k in ("convertible", "cabrio")):               mapped_class = "convertible"

            if car_class and car_class != mapped_class:
                continue

            supplier = vehicle.get("supplier", vehicle.get("provider", {}))
            supplier_name = (supplier.get("name") or vehicle.get("supplier_name") or
                             vehicle.get("company_name") or "Rental Agency")
            supplier_logo = supplier.get("logo_url", supplier.get("logo", ""))

            image_url = (vehicle_info.get("image_url") or vehicle_info.get("image") or
                         vehicle.get("image_url") or vehicle.get("image") or
                         CAR_IMAGES.get(mapped_class, CAR_IMAGES["midsize"]))

            features = []
            if t := (vehicle_info.get("transmission") or vehicle.get("transmission")):
                features.append(t.title())
            if vehicle_info.get("aircon") or vehicle.get("air_conditioning"):
                features.append("A/C")
            if s := (vehicle_info.get("seats") or vehicle.get("seats")):
                features.append(f"{s} seats")
            if d := (vehicle_info.get("doors") or vehicle.get("doors")):
                features.append(f"{d} doors")
            if fp := (vehicle.get("fuel_policy") or vehicle_info.get("fuel_policy")):
                features.append(fp.replace("_", " ").title())
            if not features:
                features = ["Automatic", "A/C"]

            booking_url = _normalize_car_booking_url(
                vehicle.get("deeplink") or vehicle.get("booking_url") or vehicle.get("url"),
                city, pickup_date, dropoff_date,
            )

            results.append({
                "id": hashlib.md5(f"{vehicle_name}-{supplier_name}-{total_price}".encode()).hexdigest()[:12],
                "company": {"name": supplier_name, "logo": supplier_logo},
                "car_class": mapped_class, "vehicle": vehicle_name, "image_url": image_url,
                "price_per_day": price_per_day, "total_price": round(total_price, 2), "days": days,
                "pickup_date": pickup_date, "dropoff_date": dropoff_date,
                "pickup_location": (vehicle.get("pick_up_location", {}).get("name") or
                                    vehicle.get("pickup_location") or f"{city} Airport or Downtown"),
                "features": features[:5], "booking_url": booking_url, "is_estimate": False,
            })
            if len(results) >= max_results:
                break
        except Exception as e:
            logger.debug("Skipping car result: %s", e)

    results.sort(key=lambda x: (x["total_price"] == 0, x["total_price"]))
    return results[:max_results]


def _resolve_car_location(city: str) -> str | None:
    if not Config.RAPIDAPI_KEY:
        return None
    try:
        resp = requests.get(
            "https://booking-com15.p.rapidapi.com/api/v1/cars/searchDestination",
            params={"query": city},
            headers={"X-RapidAPI-Key": Config.RAPIDAPI_KEY, "X-RapidAPI-Host": "booking-com15.p.rapidapi.com"},
            timeout=15,
        )
        resp.raise_for_status()
        locs = resp.json().get("data", [])
        if not locs:
            return None
        for loc in locs:
            if "airport" in str(loc.get("type", "")).lower():
                return loc.get("id") or loc.get("location_id")
        return locs[0].get("id") or locs[0].get("location_id")
    except Exception as e:
        logger.warning("Car location search failed for %s: %s", city, e)
        return None


def _generate_booking_links(
    city: str, pickup_date: str, dropoff_date: str,
    car_class: str | None, max_results: int,
) -> list[dict]:
    try:
        days = max((datetime.strptime(dropoff_date, "%Y-%m-%d") -
                    datetime.strptime(pickup_date, "%Y-%m-%d")).days, 1)
    except Exception:
        days = 3

    estimates = {
        "compact":     {"daily": (25, 50),   "examples": ["Toyota Corolla", "Honda Civic"]},
        "midsize":     {"daily": (40, 75),   "examples": ["Toyota Camry", "Nissan Altima"]},
        "full_size":   {"daily": (50, 100),  "examples": ["Chevrolet Impala", "Dodge Charger"]},
        "suv":         {"daily": (55, 120),  "examples": ["Toyota RAV4", "Ford Explorer"]},
        "luxury":      {"daily": (100, 250), "examples": ["BMW 5 Series", "Mercedes E-Class"]},
        "minivan":     {"daily": (60, 110),  "examples": ["Chrysler Pacifica", "Toyota Sienna"]},
        "convertible": {"daily": (80, 180),  "examples": ["Ford Mustang Convertible"]},
    }

    classes = [car_class] if car_class and car_class in estimates else ["compact", "midsize", "suv", "full_size"]
    booking_url = _build_car_search_url(city, pickup_date, dropoff_date)
    results = []

    for cls in classes:
        info = estimates[cls]
        avg_daily = round((info["daily"][0] + info["daily"][1]) / 2, 2)
        results.append({
            "id": hashlib.md5(f"{cls}-{city}-booking".encode()).hexdigest()[:12],
            "company": {"name": "Expedia", "logo": ""},
            "car_class": cls, "vehicle": info["examples"][0],
            "image_url": CAR_IMAGES.get(cls, CAR_IMAGES["midsize"]),
            "price_per_day": avg_daily, "total_price": round(avg_daily * days, 2), "days": days,
            "pickup_date": pickup_date, "dropoff_date": dropoff_date,
            "pickup_location": f"{city} Airport or Downtown",
            "features": ["Automatic", "A/C", "GPS Available"],
            "booking_url": booking_url, "is_estimate": True,
        })
        if len(results) >= max_results:
            break

    return sorted(results, key=lambda x: x["total_price"])[:max_results]


# ── Public interface: Car Rentals ─────────────────────────────

def search_car_rentals(
    city: str, pickup_date: str, dropoff_date: str,
    car_class: str | None = None, max_results: int = 5,
) -> list[dict]:
    if Config.RAPIDAPI_KEY:
        try:
            results = _search_rapidapi_cars(city, pickup_date, dropoff_date, car_class, max_results)
            if results:
                return results
        except Exception:
            logger.exception("RapidAPI car search failed for %s", city)
    return _generate_booking_links(city, pickup_date, dropoff_date, car_class, max_results)


# ── SerpAPI transit search ────────────────────────────────────

def _search_serpapi_transit(city: str) -> list[dict]:
    """Returns raw pass options with price in USD (no quantity enrichment yet)."""
    if not Config.SERPAPI_KEY:
        raise ValueError("SERPAPI_KEY not set")

    params = {
        "engine": "google_search",
        "q": f"{city} transit pass travel card price",
        "num": 5, "hl": "en", "gl": "us",
        "api_key": Config.SERPAPI_KEY,
    }
    resp = requests.get("https://serpapi.com/search.json", params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    transit_keywords = [
        "pass", "card", "ticket", "metro", "subway", "transit", "travel card",
        "transport", "bus", "rail", "tram", "oyster", "suica", "navigo", "t-money", "metrocard",
    ]

    results = []
    for item in data.get("organic_results", [])[:8]:
        title, snippet, link = item.get("title",""), item.get("snippet",""), item.get("link","")
        if not any(kw in (title + snippet).lower() for kw in transit_keywords):
            continue
        pi = _parse_transit_result(title, snippet, link, city)
        if pi:
            results.append(pi)
        elif link:
            fi = _fallback_transit_result(title, snippet, link, city)
            if fi:
                results.append(fi)

    ab = data.get("answer_box", {})
    if ab:
        at, as_, al = (ab.get("title","") or ab.get("answer","")), \
                      (ab.get("snippet","") or ab.get("description","")), \
                      ab.get("link","")
        if at and any(kw in (at + as_).lower() for kw in ["transit","pass","card","metro"]):
            pi = _parse_transit_result(at, as_, al, city)
            if pi:
                results.insert(0, pi)
            elif al:
                fi = _fallback_transit_result(at, as_, al, city)
                if fi:
                    results.insert(0, fi)

    # Deduplicate
    seen, unique = set(), []
    for r in results:
        k = r["name"].lower()[:30]
        if k not in seen:
            seen.add(k); unique.append(r)

    # Normalise to USD
    for r in unique:
        cc = r.get("currency_code", "USD")
        if cc != "USD" and r.get("price", 0) > 0:
            r["price"] = _to_usd(r["price"], cc)
            r["currency_code"] = "USD"
            r["currency_symbol"] = "$"

    return unique[:5]


def _parse_transit_result(title: str, snippet: str, link: str, city: str) -> dict | None:
    text = f"{snippet} {title}".strip()
    currency_code, _ = _detect_currency(text)

    price = 0
    for pattern in [
        r'(?:rmb|cny|yuan|renminbi|¥|￥|元)\s*(\d+(?:\.\d{1,2})?)',
        r'(\d+(?:\.\d{1,2})?)\s*(?:rmb|cny|yuan|renminbi|元)',
        r'(?:\$|usd)\s*(\d+(?:\.\d{1,2})?)',
        r'(\d+(?:\.\d{1,2})?)\s*(?:usd|eur|gbp|sgd|krw|jpy|dollars?)',
        r'(?:€|£|₩)\s*(\d+(?:\.\d{1,2})?)',
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                c = float(m.group(1))
                if 1 <= c <= 500:
                    price = c; break
            except ValueError:
                pass

    lower = (title + snippet).lower()
    pass_type = "transit_card"
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

    usd_price = _to_usd(price, currency_code) if price > 0 else 0
    booking_url = _best_transit_link(city, link)
    return {
        "name": name, "type": pass_type, "price": usd_price,
        "currency_code": "USD", "currency_symbol": "$",
        "description": snippet[:200].strip() if snippet else f"Public transit option for {city}",
        "url": booking_url, "booking_url": booking_url,
    }


def _fallback_transit_result(title: str, snippet: str, link: str, city: str) -> dict | None:
    name = (title or "").strip()
    if not name:
        return None
    booking_url = _best_transit_link(city, link)
    return {
        "name": name[:80], "type": "transit_card", "price": 0,
        "currency_code": "USD", "currency_symbol": "$",
        "description": snippet[:200].strip() if snippet else f"Public transit information for {city}",
        "url": booking_url, "booking_url": booking_url,
    }


# ── Curated transit data ───────────────────────────────────────
# All prices in USD per pass. Duration inferred from name via _detect_pass_duration.

TRANSIT_OPTIONS = {
    "Tokyo": [
        {"name": "7-Day Japan Rail Pass",       "type": "rail_pass",    "price": 280, "description": "Unlimited travel on JR lines nationwide",                        "url": "https://www.japan-rail-pass.com"},
        {"name": "Tokyo Metro 72-Hour Pass",     "type": "metro_pass",   "price": 15,  "description": "Unlimited Tokyo Metro and Toei subway rides",                     "url": "https://www.tokyometro.jp/en/ticket/travel/index.html"},
        {"name": "Suica Card",                   "type": "transit_card", "price": 5,   "description": "Rechargeable IC card for trains, buses, and shops",               "url": "https://www.jreast.co.jp/e/pass/suica.html"},
    ],
    "London": [
        {"name": "7-Day Travelcard",             "type": "metro_pass",   "price": 55,  "description": "Unlimited travel Zones 1-4 on Tube, buses, and DLR",             "url": "https://tfl.gov.uk/fares/find-fares/tube-and-rail-fares/caps-and-travelcard-prices"},
        {"name": "Oyster Card",                  "type": "transit_card", "price": 10,  "description": "Capped daily/weekly PAYG fares on Tube, buses, and DLR",          "url": "https://tfl.gov.uk/fares/how-to-pay-and-where-to-buy-tickets-and-oyster/pay-as-you-go/oyster-pay-as-you-go"},
    ],
    "Paris": [
        {"name": "Paris Visite 5-Day Pass",      "type": "metro_pass",   "price": 50,  "description": "Unlimited travel on Metro, RER, buses Zones 1-3",                 "url": "https://www.ratp.fr/en/titres-et-tarifs/paris-visite-travel-pass"},
        {"name": "Navigo Weekly Pass",           "type": "metro_pass",   "price": 30,  "description": "Unlimited weekly travel on all Paris public transit",              "url": "https://www.iledefrance-mobilites.fr"},
    ],
    "New York": [
        {"name": "7-Day Unlimited MetroCard",    "type": "metro_pass",   "price": 34,  "description": "Unlimited subway and local bus rides for 7 days",                 "url": "https://new.mta.info/fares"},
        {"name": "30-Day Unlimited MetroCard",   "type": "metro_pass",   "price": 132, "description": "Unlimited subway and local bus rides for 30 days",                "url": "https://new.mta.info/fares"},
    ],
    "Singapore": [
        {"name": "Singapore Tourist Pass 3-Day", "type": "transit_card", "price": 20,  "description": "Unlimited travel on MRT and public buses for 3 days",             "url": "https://thesingaporetouristpass.com.sg"},
    ],
    "Barcelona": [
        {"name": "Hola Barcelona 5-Day Pass",    "type": "metro_pass",   "price": 48,  "description": "Unlimited public transport including airport train",               "url": "https://www.holabarcelona.com"},
    ],
    "Osaka": [
        {"name": "Osaka Amazing Pass 2-Day",     "type": "metro_pass",   "price": 34,  "description": "Unlimited subway/bus and free entry to 30+ attractions",          "url": "https://www.osp.osaka-info.jp/en/"},
    ],
    "Seoul": [
        {"name": "T-money Card",                 "type": "transit_card", "price": 3,   "description": "Rechargeable card for subway, buses, and taxis",                  "url": "https://www.t-money.co.kr/eng/"},
        {"name": "Discover Seoul Pass 72-Hour",  "type": "metro_pass",   "price": 55,  "description": "Free transport + entry to 30+ attractions for 72 hours",          "url": "https://www.discoverseoulpass.com/"},
    ],
    "Chongqing": [
        {"name": "Chongqing Metro Day Pass",     "type": "day_pass",     "price": 3,   "description": "Day pass for Chongqing metro and rail transit",                   "url": "https://www.cqmetro.cn/", "booking_url": "https://www.cqmetro.cn/"},
    ],
}


# ── Public interface: Transit ─────────────────────────────────

def search_transit(city: str, days_in_city: int = 7) -> list[dict]:
    """
    Return the best transit pass option for a city, with quantity and total_price
    pre-calculated for the traveler's stay length.

    Returned fields per result:
      name            — pass name
      price_per_pass  — cost of one pass (USD)
      pass_duration_days — days covered by one pass
      quantity        — passes needed to cover days_in_city
      total_price     — price_per_pass × quantity  ← use this as the itinerary cost
      pass_label      — e.g. "2× 7-Day Unlimited MetroCard"
      days_in_city    — echoed back for the UI
      booking_url     — link to purchase
    """
    days_in_city = max(1, int(days_in_city))
    raw: list[dict] = []

    # 1. Try SerpAPI
    if Config.SERPAPI_KEY:
        try:
            raw = _search_serpapi_transit(city)
            if raw:
                logger.info("SerpAPI transit: %d results for %s", len(raw), city)
        except Exception:
            logger.exception("SerpAPI transit failed for %s", city)

    # 2. Curated fallback
    if not raw:
        options = TRANSIT_OPTIONS.get(city, [])
        if options:
            raw = [
                {**o, "price": o.get("price", 0), "currency_code": "USD", "currency_symbol": "$",
                 "booking_url": o.get("booking_url", o.get("url", ""))}
                for o in options
            ]
            logger.info("Curated transit data for %s (%d options)", city, len(raw))

    # 3. Nothing found
    if not raw:
        logger.info("No transit data for %s — skipping", city)
        return []

    # Remove zero-price entries that also lack a URL (truly useless)
    raw = [r for r in raw if r.get("price", 0) > 0 or r.get("booking_url")]

    # Pick the cheapest option for this stay, then enrich
    best = _pick_best_pass(raw, days_in_city)
    enriched = _enrich_with_quantity(best, days_in_city)

    logger.info(
        "Transit %s (%dd): %s — %d× %dd pass = $%.2f",
        city, days_in_city, enriched["name"],
        enriched["quantity"], enriched["pass_duration_days"], enriched["total_price"],
    )

    return [enriched]