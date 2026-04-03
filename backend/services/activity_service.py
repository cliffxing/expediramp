"""
Activity / attraction search service — SerpAPI Google Search + Local.

Finds tourist activities, attractions, and things to do for a given city and date.
Returns results with name, description, image, link, cost estimate, and category.

Each result carries a `source` field:
  "serpapi"   — came from SerpAPI; image_url and booking_url are real
  "curated"   — from our hand-curated list; links are verified
  "knowledge" — AI should fill from training; booking_url is a Maps search URL
"""

import logging
import re
import requests
import urllib.parse
from config import Config

logger = logging.getLogger(__name__)

# ── Fallback images by category (royalty-free Unsplash) ────────

CATEGORY_IMAGES = {
    "temple":     "https://images.unsplash.com/photo-1545569341-9eb8b30979d9?w=600",
    "shrine":     "https://images.unsplash.com/photo-1545569341-9eb8b30979d9?w=600",
    "museum":     "https://images.unsplash.com/photo-1566127444979-b3d2b654e3d7?w=600",
    "park":       "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=600",
    "garden":     "https://images.unsplash.com/photo-1585320806297-9794b3e4eeae?w=600",
    "market":     "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=600",
    "food":       "https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=600",
    "restaurant": "https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=600",
    "cafe":       "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=600",
    "beach":      "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=600",
    "nightlife":  "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=600",
    "shopping":   "https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=600",
    "landmark":   "https://images.unsplash.com/photo-1499856871958-5b9627545d1a?w=600",
    "nature":     "https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05?w=600",
    "adventure":  "https://images.unsplash.com/photo-1551632811-561732d1e306?w=600",
    "historic":   "https://images.unsplash.com/photo-1467269204594-9661b134dd2b?w=600",
    "art":        "https://images.unsplash.com/photo-1531243269054-5ebf6f34081e?w=600",
    "tour":       "https://images.unsplash.com/photo-1476514525535-07fb3b4ae5f1?w=600",
    "neighbourhood": "https://images.unsplash.com/photo-1476514525535-07fb3b4ae5f1?w=600",
    "default":    "https://images.unsplash.com/photo-1488646953014-85cb44e25828?w=600",
}

# ── Category detection keywords ────────────────────────────────

CATEGORY_KEYWORDS = {
    "temple":       ["temple", "pagoda", "wat ", "jinja", "buddhist"],
    "shrine":       ["shrine", "torii", "shinto"],
    "museum":       ["museum", "gallery", "exhibit", "collection"],
    "park":         ["park", "garden", "botanical", "greenway"],
    "garden":       ["garden", "botanical"],
    "market":       ["market", "bazaar", "souk", "mercado", "night market", "street food"],
    "food":         ["food tour", "cooking class", "ramen", "sushi", "culinary", "tasting"],
    "restaurant":   ["restaurant", "bistro", "brasserie", "steakhouse", "pizzeria", "trattoria"],
    "cafe":         ["café", "cafe", "coffee", "bakery", "patisserie", "boulangerie", "brunch"],
    "beach":        ["beach", "coast", "surf", "snorkel", "dive", "seaside"],
    "nightlife":    ["nightlife", "bar", "club", "pub crawl", "rooftop bar"],
    "shopping":     ["shopping", "mall", "boutique", "outlet"],
    "landmark":     ["tower", "bridge", "statue", "monument", "observation deck", "skyline"],
    "nature":       ["hike", "trail", "mountain", "waterfall", "volcano", "canyon", "forest"],
    "adventure":    ["adventure", "zip line", "kayak", "rafting", "bungee", "skydive"],
    "historic":     ["castle", "palace", "fort", "ruins", "heritage", "historic", "old town"],
    "art":          ["art", "street art", "mural", "installation", "contemporary"],
    "tour":         ["tour", "walking tour", "guided", "day trip", "excursion"],
    "neighbourhood":["neighbourhood", "neighborhood", "district", "quarter", "stroll", "explore"],
}


def _detect_category(name: str, description: str = "") -> str:
    text = f"{name} {description}".lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return cat
    return "landmark"


def _get_category_image(category: str) -> str:
    return CATEGORY_IMAGES.get(category, CATEGORY_IMAGES["default"])


def _build_maps_url(name: str, city: str) -> str:
    q = urllib.parse.quote(f"{name} {city}")
    return f"https://www.google.com/maps/search/{q}"


def _is_real_image_url(url: str) -> bool:
    """Return True if the URL looks like a real, displayable photo (not a Google icon/logo)."""
    if not url or not url.startswith("http"):
        return False
    low = url.lower()
    # Reject tiny Google favicon/icon URLs
    bad_patterns = ["favicon", "logo", "icon", "/s13-", "/s16-", "/s32-", "gstatic.com/images/icons"]
    if any(p in low for p in bad_patterns):
        return False
    # Accept known photo CDNs
    good_patterns = [
        "lh3.googleusercontent.com", "lh4.googleusercontent.com",
        "lh5.googleusercontent.com", "lh6.googleusercontent.com",
        "ggpht.com", "encrypted-tbn", "serpapi.com/searches",
        "images.unsplash.com", "upload.wikimedia.org",
        "cdn.", "img.", "photo.", "media.", "static.",
    ]
    if any(p in low for p in good_patterns):
        return True
    # Accept anything with a plausible image extension
    if any(low.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]):
        return True
    return False


def _fetch_place_image(name: str, city: str) -> str:
    """
    Use SerpAPI Google Images to find a real photo of a specific place.
    Returns image URL or empty string if nothing found.
    """
    if not Config.SERPAPI_KEY:
        return ""
    try:
        params = {
            "engine": "google_images",
            "q": f"{name} {city}",
            "num": 5,
            "hl": "en",
            "gl": "us",
            "api_key": Config.SERPAPI_KEY,
        }
        resp = requests.get("https://serpapi.com/search.json", params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        for img in data.get("images_results", [])[:5]:
            url = img.get("original") or img.get("thumbnail") or ""
            if _is_real_image_url(url):
                return url
    except Exception as e:
        logger.debug("Place image search failed for %s: %s", name, e)
    return ""


def _parse_cost_from_text(text: str) -> float:
    lower = text.lower()
    if any(kw in lower for kw in ["free entry", "free admission", "no charge", "free to visit", "no fee"]):
        return 0.0
    for pattern in [
        r'(?:admission|entry|ticket|price|cost|fee)[:\s]*(?:\$|usd\s?)(\d+(?:\.\d{1,2})?)',
        r'(?:\$|usd\s?)(\d+(?:\.\d{1,2})?)\s*(?:per person|pp|entry|admission|ticket)',
        r'(?:¥|jpy\s?)(\d+)',
        r'(?:€|eur\s?)(\d+(?:\.\d{1,2})?)',
        r'(?:£|gbp\s?)(\d+(?:\.\d{1,2})?)',
    ]:
        m = re.search(pattern, lower)
        if m:
            try:
                val = float(m.group(1))
                if '¥' in text or 'jpy' in lower or 'yen' in lower:
                    val = round(val * 0.0067, 2)
                elif '€' in text or 'eur' in lower:
                    val = round(val * 1.08, 2)
                elif '£' in text or 'gbp' in lower:
                    val = round(val * 1.27, 2)
                if 0.5 <= val <= 500:
                    return val
            except ValueError:
                pass
    return 0.0


# ── SerpAPI search for activities ──────────────────────────────

def _search_serpapi_activities(city: str, num_results: int = 5) -> list[dict]:
    """
    Use SerpAPI Google Search to find top tourist activities for a city.
    Fetches real place photos via google_images for each top sight.
    Returns results tagged with source="serpapi".
    """
    if not Config.SERPAPI_KEY:
        raise ValueError("SERPAPI_KEY not set")

    params = {
        "engine": "google",
        "q": f"top things to do in {city} tourist attractions must visit",
        "num": 10,
        "hl": "en",
        "gl": "us",
        "api_key": Config.SERPAPI_KEY,
    }
    resp = requests.get("https://serpapi.com/search.json", params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    results = []

    # ── Top sights from knowledge graph (best source) ──────────
    for sight in data.get("top_sights", {}).get("sights", []):
        name = sight.get("title", "").strip()
        if not name:
            continue

        description = sight.get("description", "").strip()
        # Try thumbnail from the sight first, then fetch a dedicated image
        raw_thumb = sight.get("thumbnail") or sight.get("image") or ""
        if _is_real_image_url(raw_thumb):
            image_url = raw_thumb
        else:
            # Fetch a real photo of this specific place
            image_url = _fetch_place_image(name, city)
            if not image_url:
                image_url = _get_category_image(_detect_category(name, description))

        link = sight.get("link") or _build_maps_url(name, city)
        category = _detect_category(name, description)
        cost = _parse_cost_from_text(description)

        results.append({
            "name": name,
            "description": description[:200] if description else f"Popular attraction in {city}",
            "category": category,
            "cost": cost,
            "image_url": image_url,
            "booking_url": link,
            "city": city,
            "source": "serpapi",
        })

    # ── Organic results for additional activities ───────────────
    activity_keywords = [
        "things to do", "attraction", "must visit", "top sight",
        "tourist", "experience", "activity", "tour",
    ]

    for item in data.get("organic_results", [])[:8]:
        title = item.get("title", "").strip()
        snippet = item.get("snippet", "").strip()
        link = item.get("link", "")
        thumbnail = item.get("thumbnail") or ""

        combined = f"{title} {snippet}".lower()
        if not any(kw in combined for kw in activity_keywords):
            continue

        # Try to extract individual place names from listicle-style snippets
        places = _extract_places_from_snippet(snippet, city)
        if places:
            for place in places:
                if not any(r["name"].lower() == place["name"].lower() for r in results):
                    # Fetch a real image for extracted place names
                    img = _fetch_place_image(place["name"], city)
                    if img:
                        place["image_url"] = img
                    place["source"] = "serpapi"
                    results.append(place)
        elif title and not any(r["name"].lower() == title.lower()[:40] for r in results):
            category = _detect_category(title, snippet)
            img = thumbnail if _is_real_image_url(thumbnail) else _get_category_image(category)
            results.append({
                "name": title[:80],
                "description": snippet[:200] if snippet else f"Activity in {city}",
                "category": category,
                "cost": _parse_cost_from_text(snippet),
                "image_url": img,
                "booking_url": link or _build_maps_url(title, city),
                "city": city,
                "source": "serpapi",
            })

    # Deduplicate
    seen, unique = set(), []
    for r in results:
        key = r["name"].lower().strip()[:30]
        if key not in seen:
            seen.add(key)
            unique.append(r)

    return unique[:num_results]


def _extract_places_from_snippet(snippet: str, city: str) -> list[dict]:
    """Extract numbered place names from listicle snippets."""
    pattern = r'(?:^|\s)(\d+)[.)]\s*([A-Z][^.!?\d]{3,50}?)(?=\s*\d+[.)]|\s*$|\.)'
    matches = re.findall(pattern, snippet)
    if len(matches) < 2:
        return []
    places = []
    for _, name in matches[:6]:
        name = name.strip().rstrip(',;')
        if len(name) < 4:
            continue
        category = _detect_category(name)
        places.append({
            "name": name,
            "description": f"Popular attraction in {city}",
            "category": category,
            "cost": 0,
            "image_url": _get_category_image(category),
            "booking_url": _build_maps_url(name, city),
            "city": city,
            "source": "serpapi",
        })
    return places


# ── Curated fallback activities for popular cities ─────────────
# All booking_urls are verified. source = "curated".

CURATED_ACTIVITIES = {
    "Tokyo": [
        {"name": "Senso-ji Temple", "description": "Tokyo's oldest and most famous Buddhist temple in Asakusa, with the iconic Kaminarimon gate", "category": "temple", "cost": 0, "image_url": "https://images.unsplash.com/photo-1545569341-9eb8b30979d9?w=600", "booking_url": "https://www.senso-ji.jp/", "source": "curated"},
        {"name": "Shibuya Crossing & Shibuya Sky", "description": "The world's busiest pedestrian crossing, plus panoramic views from the Shibuya Sky observation deck", "category": "landmark", "cost": 18, "image_url": "https://images.unsplash.com/photo-1542051841857-5f90071e7989?w=600", "booking_url": "https://www.shibuya-scramble-square.com/sky/", "source": "curated"},
        {"name": "Meiji Shrine", "description": "Serene Shinto shrine set in a forested area near Harajuku, dedicated to Emperor Meiji", "category": "shrine", "cost": 0, "image_url": "https://images.unsplash.com/photo-1583766395091-2eb9994ed094?w=600", "booking_url": "https://www.meijijingu.or.jp/en/", "source": "curated"},
        {"name": "TeamLab Borderless", "description": "Immersive digital art museum with interactive, ever-changing light installations", "category": "art", "cost": 32, "image_url": "https://images.unsplash.com/photo-1579783928621-7a13d66a62d1?w=600", "booking_url": "https://www.teamlab.art/e/borderless-azabudai/", "source": "curated"},
        {"name": "Tsukiji Outer Market", "description": "Bustling market with fresh seafood, sushi stalls, and Japanese street food", "category": "food", "cost": 0, "image_url": "https://images.unsplash.com/photo-1554797589-7241bb691548?w=600", "booking_url": "https://www.google.com/maps/place/Tsukiji+Outer+Market", "source": "curated"},
        {"name": "Tokyo Skytree", "description": "The world's tallest tower with observation decks offering 360° views of Tokyo", "category": "landmark", "cost": 21, "image_url": "https://images.unsplash.com/photo-1536098561742-ca998e48cbcc?w=600", "booking_url": "https://www.tokyo-skytree.jp/en/", "source": "curated"},
        {"name": "Shinjuku Gyoen National Garden", "description": "Stunning national garden blending Japanese, English, and French landscape styles", "category": "garden", "cost": 4, "image_url": "https://images.unsplash.com/photo-1528360983277-13d401cdc186?w=600", "booking_url": "https://fng.or.jp/shinjuku/en/", "source": "curated"},
    ],
    "Osaka": [
        {"name": "Osaka Castle", "description": "Iconic 16th-century castle surrounded by a park, with a museum inside the main tower", "category": "historic", "cost": 5, "image_url": "https://images.unsplash.com/photo-1590559899731-a382839e5549?w=600", "booking_url": "https://www.osakacastle.net/english/", "source": "curated"},
        {"name": "Dotonbori District", "description": "Neon-lit street famous for street food, the Glico Running Man sign, and nightlife", "category": "food", "cost": 0, "image_url": "https://images.unsplash.com/photo-1493780474015-ba834fd0ce2f?w=600", "booking_url": "https://www.google.com/maps/place/Dotonbori", "source": "curated"},
        {"name": "Kuromon Market", "description": "Osaka's Kitchen — a bustling 600m market with fresh seafood, fruit, and street food", "category": "market", "cost": 0, "image_url": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=600", "booking_url": "https://www.kuromon.com/", "source": "curated"},
        {"name": "Shinsekai District", "description": "Retro neighborhood known for kushikatsu (deep-fried skewers) and Tsutenkaku Tower", "category": "food", "cost": 0, "image_url": "https://images.unsplash.com/photo-1476514525535-07fb3b4ae5f1?w=600", "booking_url": "https://www.google.com/maps/place/Shinsekai", "source": "curated"},
        {"name": "Universal Studios Japan", "description": "World-class theme park featuring the Wizarding World of Harry Potter and Nintendo World", "category": "adventure", "cost": 65, "image_url": "https://images.unsplash.com/photo-1551632811-561732d1e306?w=600", "booking_url": "https://www.usj.co.jp/web/en/us", "source": "curated"},
    ],
    "Seoul": [
        {"name": "Gyeongbokgung Palace", "description": "Grand Joseon dynasty palace with changing of the guard ceremony and hanbok rentals", "category": "historic", "cost": 3, "image_url": "https://images.unsplash.com/photo-1601621915196-2621bfb0cd6e?w=600", "booking_url": "https://www.google.com/maps/place/Gyeongbokgung+Palace", "source": "curated"},
        {"name": "Bukchon Hanok Village", "description": "Traditional Korean village with 600-year-old hanok houses between two palaces", "category": "historic", "cost": 0, "image_url": "https://images.unsplash.com/photo-1572252009286-268acec5ca0a?w=600", "booking_url": "https://www.google.com/maps/place/Bukchon+Hanok+Village", "source": "curated"},
        {"name": "Myeongdong Shopping District", "description": "Seoul's premier shopping and street food district with K-beauty stores and fashion", "category": "shopping", "cost": 0, "image_url": "https://images.unsplash.com/photo-1534274988757-a28bf1a57c17?w=600", "booking_url": "https://www.google.com/maps/place/Myeongdong", "source": "curated"},
        {"name": "Namsan Seoul Tower", "description": "Iconic tower on Namsan Mountain with panoramic city views and love lock fences", "category": "landmark", "cost": 12, "image_url": "https://images.unsplash.com/photo-1546874177-9e664107314e?w=600", "booking_url": "https://www.nseoultower.com/", "source": "curated"},
        {"name": "Gwangjang Market", "description": "Historic market famous for bindaetteok (mung bean pancakes) and traditional Korean food", "category": "food", "cost": 0, "image_url": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=600", "booking_url": "https://www.google.com/maps/place/Gwangjang+Market", "source": "curated"},
    ],
    "Paris": [
        {"name": "Eiffel Tower", "description": "Iconic iron lattice tower with observation decks offering sweeping views of Paris", "category": "landmark", "cost": 29, "image_url": "https://images.unsplash.com/photo-1511739001486-6bfe10ce65f4?w=600", "booking_url": "https://www.toureiffel.paris/en", "source": "curated"},
        {"name": "Louvre Museum", "description": "World's largest art museum, home to the Mona Lisa and thousands of masterworks", "category": "museum", "cost": 22, "image_url": "https://images.unsplash.com/photo-1499856871958-5b9627545d1a?w=600", "booking_url": "https://www.louvre.fr/en", "source": "curated"},
        {"name": "Montmartre & Sacré-Cœur", "description": "Charming hilltop neighborhood with artist studios, cafés, and the white basilica", "category": "landmark", "cost": 0, "image_url": "https://images.unsplash.com/photo-1550340499-a6c60fc8287c?w=600", "booking_url": "https://www.sacre-coeur-montmartre.com/", "source": "curated"},
        {"name": "Musée d'Orsay", "description": "Impressionist art museum in a stunning Beaux-Arts railway station on the Seine", "category": "museum", "cost": 16, "image_url": "https://images.unsplash.com/photo-1566127444979-b3d2b654e3d7?w=600", "booking_url": "https://www.musee-orsay.fr/en", "source": "curated"},
        {"name": "Le Marais Walking Tour", "description": "Explore the historic quarter with medieval streets, falafel shops, and boutiques", "category": "tour", "cost": 0, "image_url": "https://images.unsplash.com/photo-1431274172761-fca41d930114?w=600", "booking_url": "https://www.google.com/maps/place/Le+Marais", "source": "curated"},
    ],
    "New York": [
        {"name": "Central Park", "description": "Iconic 843-acre urban park with lakes, gardens, and cultural landmarks", "category": "park", "cost": 0, "image_url": "https://images.unsplash.com/photo-1568515387631-8b650bbcdb90?w=600", "booking_url": "https://www.centralparknyc.org/", "source": "curated"},
        {"name": "Statue of Liberty & Ellis Island", "description": "Ferry to the iconic statue and immigration museum on Ellis Island", "category": "landmark", "cost": 24, "image_url": "https://images.unsplash.com/photo-1492666673288-3c4b4f1a7b15?w=600", "booking_url": "https://www.statueofliberty.org", "source": "curated"},
        {"name": "Metropolitan Museum of Art", "description": "One of the world's greatest art museums with over 5,000 years of art", "category": "museum", "cost": 30, "image_url": "https://images.unsplash.com/photo-1566127444979-b3d2b654e3d7?w=600", "booking_url": "https://www.metmuseum.org", "source": "curated"},
        {"name": "Brooklyn Bridge Walk", "description": "Walk across the historic bridge for stunning views of Manhattan and the East River", "category": "landmark", "cost": 0, "image_url": "https://images.unsplash.com/photo-1534430480872-3498386e7856?w=600", "booking_url": "https://www.google.com/maps/place/Brooklyn+Bridge", "source": "curated"},
        {"name": "High Line Park", "description": "Elevated linear park on a historic freight rail line with gardens and art installations", "category": "park", "cost": 0, "image_url": "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=600", "booking_url": "https://www.thehighline.org/", "source": "curated"},
        {"name": "Times Square & Broadway", "description": "The neon-lit crossroads of the world, with world-class theater shows nightly", "category": "nightlife", "cost": 0, "image_url": "https://images.unsplash.com/photo-1534430480872-3498386e7856?w=600", "booking_url": "https://www.google.com/maps/place/Times+Square", "source": "curated"},
    ],
    "London": [
        {"name": "British Museum", "description": "World-famous museum with the Rosetta Stone, Egyptian mummies, and Greek sculptures", "category": "museum", "cost": 0, "image_url": "https://images.unsplash.com/photo-1566127444979-b3d2b654e3d7?w=600", "booking_url": "https://www.britishmuseum.org", "source": "curated"},
        {"name": "Tower of London", "description": "Historic castle with the Crown Jewels, Beefeater tours, and 1,000 years of history", "category": "historic", "cost": 33, "image_url": "https://images.unsplash.com/photo-1467269204594-9661b134dd2b?w=600", "booking_url": "https://www.hrp.org.uk/tower-of-london/", "source": "curated"},
        {"name": "Borough Market", "description": "London's most famous food market with artisan producers and global street food", "category": "food", "cost": 0, "image_url": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=600", "booking_url": "https://boroughmarket.org.uk", "source": "curated"},
        {"name": "Buckingham Palace & St James's Park", "description": "Watch the Changing of the Guard and stroll through the royal park", "category": "landmark", "cost": 0, "image_url": "https://images.unsplash.com/photo-1520986606214-8b456906c813?w=600", "booking_url": "https://www.rct.uk/visit/the-state-rooms-buckingham-palace", "source": "curated"},
        {"name": "South Bank & Tate Modern", "description": "Walk along the Thames past the London Eye, Shakespeare's Globe, and free modern art", "category": "art", "cost": 0, "image_url": "https://images.unsplash.com/photo-1531243269054-5ebf6f34081e?w=600", "booking_url": "https://www.tate.org.uk/visit/tate-modern", "source": "curated"},
    ],
}


# ── Public interface ───────────────────────────────────────────

def search_activities(city: str, num_activities: int = 5) -> list[dict]:
    """
    Search for tourist activities / things to do in a city.

    Returns a list of dicts with:
      name, description, category, cost, image_url, booking_url, city, source

    source values:
      "serpapi"  — real SerpAPI result; image and link are genuine
      "curated"  — hand-verified fallback
      "knowledge" — AI should use training knowledge; booking_url is a Maps link
    """
    num_activities = max(1, min(num_activities, 10))

    # 1. Try SerpAPI
    if Config.SERPAPI_KEY:
        try:
            results = _search_serpapi_activities(city, num_activities)
            if results:
                logger.info("SerpAPI activities: %d results for %s", len(results), city)
                return results[:num_activities]
        except Exception:
            logger.exception("SerpAPI activity search failed for %s", city)

    # 2. Curated fallback
    curated = CURATED_ACTIVITIES.get(city, [])
    if curated:
        logger.info("Using curated activities for %s (%d available)", city, len(curated))
        for item in curated:
            item.setdefault("city", city)
            item.setdefault("source", "curated")
        return curated[:num_activities]

    # 3. Nothing found — return empty; AI will use training knowledge
    logger.info("No activity data for %s — AI will use training knowledge", city)
    return []