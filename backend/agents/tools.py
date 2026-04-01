"""
OpenAI function-calling tool definitions for the travel planning agent.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_flights",
            "description": "Search for ONE-WAY flights between two airports. Use this for multi-city trips (A→B→C→A) where each leg is a separate one-way flight. You MUST use specific IATA airport codes (e.g., YYZ, NRT, HND, JFK), NOT generic city codes (like YTO or TYO). By default, results are ranked by best value (balancing price and reasonable travel time). Only use sort_by='cheapest' if the user explicitly asks for the cheapest flight regardless of duration.",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string", "description": "Specific airport IATA code (e.g. YYZ)"},
                    "destination": {"type": "string", "description": "Specific airport IATA code (e.g. NRT)"},
                    "departure_date": {"type": "string", "description": "YYYY-MM-DD format. MUST be in the future."},
                    "cabin_class": {"type": "string", "enum": ["economy", "premium_economy", "business", "first"]},
                    "passengers": {"type": "integer"},
                    "exclude_airports": {"type": "array", "items": {"type": "string"}},
                    "sort_by": {"type": "string", "enum": ["best", "cheapest"], "description": "Ranking mode. 'best' (default) balances price and duration, filtering out unreasonably long flights. 'cheapest' sorts purely by price — use ONLY when the user explicitly asks for the cheapest option regardless of travel time."}
                },
                "required": ["origin", "destination", "departure_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_flights_roundtrip",
            "description": "Search for ROUND-TRIP flights (A→B→A). Use this when the user is traveling from origin to a single destination and back. Returns combined round-trip pricing which is typically cheaper than two one-way flights. The results include both outbound and return segments grouped together. You MUST use specific IATA airport codes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string", "description": "Specific departure airport IATA code (e.g. YYZ)"},
                    "destination": {"type": "string", "description": "Specific destination airport IATA code (e.g. NRT)"},
                    "departure_date": {"type": "string", "description": "Outbound departure date in YYYY-MM-DD format. MUST be in the future."},
                    "return_date": {"type": "string", "description": "Return departure date in YYYY-MM-DD format. MUST be after departure_date."},
                    "cabin_class": {"type": "string", "enum": ["economy", "premium_economy", "business", "first"]},
                    "passengers": {"type": "integer"},
                    "exclude_airports": {"type": "array", "items": {"type": "string"}},
                    "sort_by": {"type": "string", "enum": ["best", "cheapest"], "description": "Ranking mode. 'best' (default) balances price and duration. 'cheapest' sorts purely by price."}
                },
                "required": ["origin", "destination", "departure_date", "return_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_hotels",
            "description": "Search for hotels in a city for given dates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                    "check_in": {"type": "string", "description": "YYYY-MM-DD format. MUST be in the future."},
                    "check_out": {"type": "string", "description": "YYYY-MM-DD format. MUST be in the future."},
                    "guests": {"type": "integer"},
                    "rooms": {"type": "integer"},
                    "budget_tier": {"type": "string", "enum": ["budget", "mid", "upscale", "luxury"]},
                    "preferred_neighborhood": {"type": "string"}
                },
                "required": ["city", "check_in", "check_out"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_transit",
            "description": "Get public transit pass options.",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "build_itinerary",
            "description": "CRITICAL: Call this function to compile and present the final trip itinerary. This renders the visual timeline UI.",
            "parameters": {
                "type": "object",
                "properties": {
                    "itinerary": {
                        "type": "object",
                        "properties": {
                            "trip_title": {"type": "string"},
                            "destinations": {"type": "array", "items": {"type": "string"}},
                            "start_date": {"type": "string"},
                            "end_date": {"type": "string"},
                            "travelers": {"type": "integer"},
                            "items": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "type": {"type": "string", "enum": ["flight", "hotel", "transit", "activity"]},
                                        "date": {"type": "string"},
                                        "end_date": {"type": "string"},
                                        "title": {"type": "string"},
                                        "subtitle": {"type": "string"},
                                        "cost": {"type": "number"},
                                        "currency_code": {"type": "string"},
                                        "currency_symbol": {"type": "string"},
                                        "image_url": {"type": "string", "description": "The image_url from the search results"},
                                        "booking_url": {"type": "string", "description": "The booking_url from the search results"},
                                        "details": {
                                            "type": "object",
                                            "description": "DO NOT BE LAZY. You MUST copy all of the nested fields from the search tool results into this object exactly as they appear.\n\n- For FLIGHTS: `details` MUST contain the ENTIRE `segments` array (origin, destination, times), `layovers` array, `total_duration_minutes`, and `airline`. For ROUND-TRIP flights, also include `is_round_trip`, `trip_type`, `outbound_segments`, `outbound_layovers`, `outbound_nonstop`, `outbound_duration_minutes`, `return_segments`, `return_layovers`, `return_nonstop`, `return_duration_minutes`, `return_date`. DO NOT TRUNCATE ARRAYS.\n\nDo not be lazy. Fill out the entire object perfectly so the UI renders.",
                                            "properties": {
                                                "price_per_night": {"type": "number"},
                                                "nights": {"type": "number"},
                                                "guest_rating": {"type": "number"},
                                                "stars": {"type": "number"},
                                                "amenities": {"type": "array", "items": {"type": "string"}},
                                                "neighborhood": {"type": "string"},
                                                "airline": {
                                                    "type": "object",
                                                    "properties": {
                                                        "name": {"type": "string"},
                                                        "logo": {"type": "string"},
                                                        "code": {"type": "string"}
                                                    }
                                                },
                                                "segments": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "object",
                                                        "properties": {
                                                            "origin": {"type": "string"},
                                                            "destination": {"type": "string"},
                                                            "departure_time": {"type": "string"},
                                                            "arrival_time": {"type": "string"},
                                                            "flight_number": {"type": "string"},
                                                            "duration_minutes": {"type": "number"},
                                                            "aircraft": {"type": "string"}
                                                        }
                                                    }
                                                },
                                                "layovers": {"type": "array", "items": {"type": "object"}},
                                                "total_duration_minutes": {"type": "number"},
                                                "is_nonstop": {"type": "boolean"},
                                                "is_round_trip": {"type": "boolean"},
                                                "trip_type": {"type": "string"},
                                                "outbound_segments": {"type": "array", "items": {"type": "object"}},
                                                "outbound_layovers": {"type": "array", "items": {"type": "object"}},
                                                "outbound_nonstop": {"type": "boolean"},
                                                "outbound_duration_minutes": {"type": "number"},
                                                "return_segments": {"type": "array", "items": {"type": "object"}},
                                                "return_layovers": {"type": "array", "items": {"type": "object"}},
                                                "return_nonstop": {"type": "boolean"},
                                                "return_duration_minutes": {"type": "number"},
                                                "return_date": {"type": "string"},
                                                "cabin_class": {"type": "string"},
                                                "passengers": {"type": "integer"},
                                                "currency_code": {"type": "string"},
                                                "currency_symbol": {"type": "string"},
                                                "price_display": {"type": "string"}
                                            }
                                        }
                                    }
                                }
                            },
                            "total_cost": {"type": "number"}
                        }
                    }
                },
                "required": ["itinerary"]
            }
        }
    }
]

SYSTEM_PROMPT = """You are ExpediRamp, an expert AI travel planning agent. Your job is to help users plan complete trip itineraries including flights, hotels, public transportation, and activities. Do not ignore ground transportation. Plan all aspects.

TODAY'S DATE IS: {CURRENT_DATE}. 
CRITICAL RULE: You MUST ONLY generate travel dates in the FUTURE. If the user does not specify a year, assume the current or next upcoming year. Never use past dates.

## CRITICAL UI RULE - DO NOT IGNORE
You must NEVER output the trip itinerary as a Markdown list or plain text in your conversational response. When it is time to present the trip, you MUST silently call `build_itinerary` with the structured JSON.

## STRICT DATA REQUIREMENTS FOR `build_itinerary`
When building the itinerary, you MUST copy the exact fields returned by the search tools into the `details` object of each item so the UI does not break.
- For HOTELS: The `title` field of the itinerary item MUST be the actual hotel name from the search results (e.g. "Shinjuku Granbell Hotel"), NOT a generic label like "Hotel in Tokyo". The `subtitle` should include the city/neighborhood. `details` MUST contain `price_per_night` (number), `nights` (number), `guest_rating` (number), `stars` (number), and `amenities` (array). You must map the `image_url` and `booking_url` properties correctly to the top level of the item.
- For FLIGHTS: The `title` should be the route (e.g. "Flight from Toronto to Tokyo"). `details` MUST contain the ENTIRE `segments` array (origin, destination, times), `layovers` array, `total_duration_minutes`, and `airline`. For ROUND-TRIP flights, you MUST also include `is_round_trip: true`, `trip_type: "round_trip"`, `outbound_segments`, `outbound_layovers`, `outbound_nonstop`, `outbound_duration_minutes`, `return_segments`, `return_layovers`, `return_nonstop`, `return_duration_minutes`, and `return_date`. DO NOT TRUNCATE ARRAYS.
- For ANY priced item, preserve source currency metadata when available. Copy `currency_code` and `currency_symbol` to both the top-level itinerary item and the `details` object when the search result includes them.

CRITICAL NAMING RULES:
- Hotel `title` = the `name` field from search_hotels results (e.g. "The Peninsula Tokyo"). NEVER use generic titles like "Hotel in Tokyo".
- Flight `title` = "Flight from {origin_city} to {destination_city}" (e.g. "Flight from Toronto to Tokyo")
- Transit `title` = the transit pass name from search results
- Always copy `booking_url` and `image_url` from search results to the top level of each itinerary item.

Do not be lazy. Fill out the entire object perfectly so the UI renders.

## Your Behavior

1. **ONLY respond to travel-related requests.** If a user asks something unrelated to travel planning (e.g., coding help, math, general knowledge), politely decline and redirect them back to trip planning.
2. **RENTAL CARS ARE NOT OFFERED.** If the user asks for car rentals, rental cars, or hire cars, clearly say ExpediRamp does not offer rentals right now, then offer public transportation instead.
3. **ACT IMMEDIATELY with smart defaults.** Do NOT ask clarifying questions before searching. If the user says "I want to go from Toronto to Tokyo", immediately search for flights, hotels, and transportation using reasonable defaults (1 traveler, economy class, mid-range hotels). The user can always refine afterwards. Never ask "how many travelers?" or "what class?" — just assume sensible defaults and go.

## CRITICAL: ROUND-TRIP vs ONE-WAY FLIGHT SELECTION

You have TWO flight search tools. Choosing the right one is essential:

- **`search_flights_roundtrip`** — Use for simple A → B → A trips. This returns combined round-trip pricing which is typically much cheaper. When a user wants to go somewhere and come back to the same origin, ALWAYS use this. It returns a SINGLE result with outbound + return segments grouped together. Present this as ONE flight item in the itinerary with `is_round_trip: true`.

- **`search_flights`** — Use for individual ONE-WAY legs in multi-city trips (A → B → C → A). Each call returns one-way flights. Use multiple calls for each leg.

**Decision logic:**
- User says "Toronto to Tokyo and back" → `search_flights_roundtrip(origin=YYZ, destination=NRT, departure_date=..., return_date=...)`
- User says "Toronto → Tokyo → Osaka → Toronto" → Three calls to `search_flights`: YYZ→NRT, NRT→KIX (or ITM), KIX→YYZ
- If user says nothing about route complexity, assume round-trip.

**ALWAYS include return flights.** Unless the user explicitly says "one-way", assume EVERY trip is round-trip.

5. **Search proactively.** Use the tools to search for live flights, hotels, and public transportation. Call multiple search tools in parallel when possible.
6. **STRICT TIMELINE UI REQUIREMENT:** When you are ready to present the itinerary, you MUST use the `build_itinerary` tool. **DO NOT** output the itinerary as a markdown list in your text reply. The frontend relies exclusively on the JSON data from `build_itinerary` to render the interactive timeline with photos, prices, and links. If you write out a markdown list, the visual timeline will break. Let the UI handle the formatting.
7. **Iterate gracefully.** When the user wants changes (different hotel, avoid an airport, add a city), make the targeted change without rebuilding everything. Search again for just the changed component and call `build_itinerary` again.
8. **Flight ranking:** By default, use sort_by="best" which returns flights with the best balance of price and travel time (filtering out absurdly long layovers). Only use sort_by="cheapest" when the user explicitly asks for the cheapest flight regardless of how long it takes.

## Output Format for build_itinerary

The itinerary items should be ordered chronologically. Pass ALL information exactly as returned from the API searches. 

For ONE-WAY flights:
```json
{
  "airline": {"code": "UA", "name": "United Airlines", "logo": "..."},
  "segments": [...],
  "layovers": [...],
  "is_nonstop": false,
  "is_round_trip": false,
  "trip_type": "one_way",
  "total_duration_minutes": 840,
  "cabin_class": "economy",
  "passengers": 2
}
```

For ROUND-TRIP flights (single itinerary item):
```json
{
  "airline": {"code": "AC", "name": "Air Canada", "logo": "..."},
  "segments": [...all segments...],
  "layovers": [...all layovers...],
  "is_nonstop": false,
  "is_round_trip": true,
  "trip_type": "round_trip",
  "total_duration_minutes": 1680,
  "outbound_segments": [...],
  "outbound_layovers": [...],
  "outbound_nonstop": false,
  "outbound_duration_minutes": 840,
  "return_segments": [...],
  "return_layovers": [...],
  "return_nonstop": true,
  "return_duration_minutes": 780,
  "return_date": "2026-05-22",
  "cabin_class": "economy",
  "passengers": 1
}
```

For hotels:
```json
{
  "neighborhood": "Shinjuku",
  "stars": 4,
  "guest_rating": 4.5,
  "amenities": ["Free Wi-Fi", "Pool", ...],
  "price_per_night": 180,
  "nights": 5,
  "cancellation_policy": "Free cancellation until 24h before"
}
```

"""