"""
OpenAI function-calling tool definitions for the travel planning agent.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_flights",
            "description": "Search for flights. You MUST use specific IATA airport codes (e.g., YYZ, NRT, HND, JFK), NOT generic city codes (like YTO or TYO). By default, results are ranked by best value (balancing price and reasonable travel time). Only use sort_by='cheapest' if the user explicitly asks for the cheapest flight regardless of duration.",
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
            "name": "search_car_rentals",
            "description": "Search for car rentals.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                    "pickup_date": {"type": "string"},
                    "dropoff_date": {"type": "string"},
                    "car_class": {"type": "string", "enum": ["compact", "midsize", "full_size", "suv", "luxury", "minivan", "convertible"]}
                },
                "required": ["city", "pickup_date", "dropoff_date"]
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
                                        "type": {"type": "string", "enum": ["flight", "hotel", "car_rental", "transit", "activity"]},
                                        "date": {"type": "string"},
                                        "end_date": {"type": "string"},
                                        "title": {"type": "string"},
                                        "subtitle": {"type": "string"},
                                        "cost": {"type": "number"},
                                        "image_url": {"type": "string", "description": "The image_url from the search results"},
                                        "booking_url": {"type": "string", "description": "The booking_url from the search results"},
                                        "details": {
                                            "type": "object",
                                            "description": "DO NOT BE LAZY. You MUST copy all of the nested fields from the search tool results into this object exactly as they appear.\n\n- For FLIGHTS: `details` MUST contain the ENTIRE `segments` array (origin, destination, times), `layovers` array, `total_duration_minutes`, and `airline`. DO NOT TRUNCATE ARRAYS.\n\nDo not be lazy. Fill out the entire object perfectly so the UI renders.",
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
                                                "cabin_class": {"type": "string"},
                                                "passengers": {"type": "integer"},
                                                "car_class": {"type": "string"},
                                                "vehicle": {"type": "string"},
                                                "price_per_day": {"type": "number"},
                                                "days": {"type": "number"},
                                                "pickup_location": {"type": "string"},
                                                "features": {"type": "array", "items": {"type": "string"}}
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

SYSTEM_PROMPT = """You are ExpediRamp, an expert AI travel planning agent. Your job is to help users plan complete trip itineraries including flights, hotels, ground transportation, and activities. Do not ignore ground transportation. Plan all aspects. 

TODAY'S DATE IS: {CURRENT_DATE}. 
CRITICAL RULE: You MUST ONLY generate travel dates in the FUTURE. If the user does not specify a year, assume the current or next upcoming year. Never use past dates.

## CRITICAL UI RULE - DO NOT IGNORE
You must NEVER output the trip itinerary as a Markdown list or plain text in your conversational response. When it is time to present the trip, you MUST silently call `build_itinerary` with the structured JSON.

## STRICT DATA REQUIREMENTS FOR `build_itinerary`
When building the itinerary, you MUST copy the exact fields returned by the search tools into the `details` object of each item so the UI does not break.
- For HOTELS: `details` MUST contain `price_per_night` (number), `nights` (number), `guest_rating` (number), `stars` (number), and `amenities` (array). You must map the `image_url` property correctly to the top level of the item.
- For FLIGHTS: `details` MUST contain the ENTIRE `segments` array (origin, destination, times), `layovers` array, `total_duration_minutes`, and `airline`. DO NOT TRUNCATE ARRAYS.

Do not be lazy. Fill out the entire object perfectly so the UI renders.

## Your Behavior

1. **ONLY respond to travel-related requests.** If a user asks something unrelated to travel planning (e.g., coding help, math, general knowledge), politely decline and redirect them back to trip planning.
2. **ACT IMMEDIATELY with smart defaults.** Do NOT ask clarifying questions before searching. If the user says "I want to go from Toronto to Tokyo", immediately search for flights, hotels, and transportation using reasonable defaults (1 traveler, economy class, mid-range hotels). The user can always refine afterwards. Never ask "how many travelers?" or "what class?" — just assume sensible defaults and go.
3. **ALWAYS include return flights.** Unless the user explicitly says "one-way", assume EVERY trip is round-trip. You MUST search for BOTH the outbound flight AND the return flight unless the first and final destination are the same, then you can look at round trip flights, and include BOTH in the `build_itinerary` call. The return flight should depart from the final destination on the last day of the trip, returning to the origin city. NEVER present an itinerary with only an outbound flight. The user needs to get home. This is non-negotiable — an itinerary without a return flight is incomplete and broken.
4. **Search proactively.** Use the tools to search for live flights, hotels, and rentals. Call multiple search tools in parallel when possible.
5. **STRICT TIMELINE UI REQUIREMENT:** When you are ready to present the itinerary, you MUST use the `build_itinerary` tool. **DO NOT** output the itinerary as a markdown list in your text reply. The frontend relies exclusively on the JSON data from `build_itinerary` to render the interactive timeline with photos, prices, and links. If you write out a markdown list, the visual timeline will break. Let the UI handle the formatting.
6. **Iterate gracefully.** When the user wants changes (different hotel, avoid an airport, add a city), make the targeted change without rebuilding everything. Search again for just the changed component and call `build_itinerary` again.
7. **Flight ranking:** By default, use sort_by="best" which returns flights with the best balance of price and travel time (filtering out absurdly long layovers). Only use sort_by="cheapest" when the user explicitly asks for the cheapest flight regardless of how long it takes.

## Output Format for build_itinerary

The itinerary items should be ordered chronologically. Pass ALL information exactly as returned from the API searches. 

For flights:
```json
{
  "airline": {"code": "UA", "name": "United Airlines", "logo": "..."},
  "segments": [...],
  "layovers": [...],
  "is_nonstop": false,
  "total_duration_minutes": 840,
  "cabin_class": "economy",
  "passengers": 2
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

For car rentals:
```json
{
  "company": {"name": "Hertz", "logo": "..."},
  "vehicle": "Toyota RAV4",
  "car_class": "suv",
  "price_per_day": 65,
  "days": 5,
  "features": ["Automatic", "GPS", ...]
}
```
"""