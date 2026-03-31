"""
OpenAI function-calling tool definitions for the travel planning agent.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_flights",
            "description": "Search for flights between two airports on a given date. Use IATA airport codes (e.g. JFK, LAX, LHR, NRT). Call this whenever the user wants to find or change flights.",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {
                        "type": "string",
                        "description": "IATA code of the departure airport, e.g. JFK"
                    },
                    "destination": {
                        "type": "string",
                        "description": "IATA code of the arrival airport, e.g. NRT"
                    },
                    "departure_date": {
                        "type": "string",
                        "description": "Departure date in YYYY-MM-DD format"
                    },
                    "cabin_class": {
                        "type": "string",
                        "enum": ["economy", "premium_economy", "business", "first"],
                        "description": "Cabin class preference"
                    },
                    "passengers": {
                        "type": "integer",
                        "description": "Number of passengers"
                    },
                    "exclude_airports": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of IATA codes to exclude from layovers"
                    }
                },
                "required": ["origin", "destination", "departure_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_hotels",
            "description": "Search for hotels in a city for given dates. Call this whenever the user wants to find or change hotel accommodations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name, e.g. Tokyo, Paris, New York"
                    },
                    "check_in": {
                        "type": "string",
                        "description": "Check-in date in YYYY-MM-DD format"
                    },
                    "check_out": {
                        "type": "string",
                        "description": "Check-out date in YYYY-MM-DD format"
                    },
                    "guests": {
                        "type": "integer",
                        "description": "Number of guests"
                    },
                    "rooms": {
                        "type": "integer",
                        "description": "Number of rooms needed"
                    },
                    "budget_tier": {
                        "type": "string",
                        "enum": ["budget", "mid", "upscale", "luxury"],
                        "description": "Hotel budget tier"
                    },
                    "preferred_neighborhood": {
                        "type": "string",
                        "description": "Preferred neighborhood or area within the city"
                    }
                },
                "required": ["city", "check_in", "check_out"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_car_rentals",
            "description": "Search for car rental options in a city. Call this when the user wants a rental car.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name for pickup"
                    },
                    "pickup_date": {
                        "type": "string",
                        "description": "Pickup date in YYYY-MM-DD format"
                    },
                    "dropoff_date": {
                        "type": "string",
                        "description": "Drop-off date in YYYY-MM-DD format"
                    },
                    "car_class": {
                        "type": "string",
                        "enum": ["compact", "midsize", "full_size", "suv", "luxury", "minivan", "convertible"],
                        "description": "Preferred car class"
                    }
                },
                "required": ["city", "pickup_date", "dropoff_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_transit",
            "description": "Get public transit pass options for a city. Call this when the user prefers public transit over car rental.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name"
                    }
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "build_itinerary",
            "description": "Compile a complete trip itinerary with selected flights, hotels, transportation, and day-by-day activities. Call this once you have gathered enough search results and user preferences to assemble the final plan. The itinerary_data should be a well-structured JSON object.",
            "parameters": {
                "type": "object",
                "properties": {
                    "itinerary": {
                        "type": "object",
                        "description": "The complete trip itinerary object",
                        "properties": {
                            "trip_title": {"type": "string"},
                            "destinations": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "start_date": {"type": "string"},
                            "end_date": {"type": "string"},
                            "travelers": {"type": "integer"},
                            "items": {
                                "type": "array",
                                "description": "Ordered list of itinerary items (flights, hotels, transport, activities)",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "type": {
                                            "type": "string",
                                            "enum": ["flight", "hotel", "car_rental", "transit", "activity"]
                                        },
                                        "date": {"type": "string"},
                                        "end_date": {"type": "string"},
                                        "title": {"type": "string"},
                                        "subtitle": {"type": "string"},
                                        "details": {"type": "object"},
                                        "cost": {"type": "number"},
                                        "image_url": {"type": "string"},
                                        "booking_url": {"type": "string"}
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

SYSTEM_PROMPT = """You are ExpediRamp, an expert AI travel planning agent. Your job is to help users plan complete trip itineraries including flights, hotels, ground transportation, and activities.

## Your Behavior

1. **ONLY respond to travel-related requests.** If a user asks something unrelated to travel planning (e.g., coding help, math, general knowledge), politely decline and redirect them back to trip planning. Say something like: "I'm ExpediRamp, your travel planning assistant! I can only help with trip planning. Tell me about a trip you'd like to take!"

2. **Gather essential information** before searching. You MUST know:
   - Departure city/airport
   - Destination city/cities
   - Travel dates (or approximate timeframe)
   - Number of travelers
   - Budget preference (budget, mid-range, upscale, luxury)
   
   Ask for missing info conversationally — don't dump a bulleted checklist. Ask the 2-3 most important missing items first.

3. **Search proactively.** Once you have enough info, immediately call the search tools. Don't ask for permission to search. Search for flights, hotels, and transportation in parallel when possible.

4. **Present options and recommend.** After searching, pick the best option for each category based on the user's stated preferences (price, comfort, convenience, etc.). Explain *why* you chose it.

5. **Build the itinerary** once you've selected options. Call `build_itinerary` with a complete, structured itinerary that includes:
   - All flights with full segment details, layover info, and prices
   - Hotel stays with photos, amenities, and nightly rates
   - Transportation (car rental or transit passes)
   - Suggested daily activities
   - Running cost for each item and total trip cost

6. **Iterate gracefully.** When the user wants changes (different hotel, avoid an airport, add a city), make the targeted change without rebuilding everything. Search again for just the changed component and rebuild the itinerary.

## Important Rules

- Always use real IATA airport codes when calling search_flights.
- For multi-city trips, search each flight leg separately.
- If the user mentions a city, infer the main airport(s) for that city.
- Convert vague dates ("next month", "early July") to specific dates. If unsure, ask.
- Always include a total cost breakdown.
- Be enthusiastic but professional. Channel the energy of a knowledgeable travel advisor.
- When presenting the itinerary via build_itinerary, include image_url for hotels and booking_url for all bookable items.
- For flights, always include full segment details including layover information in the details object.
- Car rental results provide price *estimates* with booking links to aggregators (Kayak, Google). Let the user know prices are estimates and they should click through to see exact rates.
- All flight data comes from the Duffel API (real airline inventory). Flight offers include a `duffel_offer_id` and an `expires_at` timestamp — mention to the user that prices are live but may expire.
- Hotel data comes from Duffel Stays (real availability). Present the results confidently — they reflect actual inventory.
- If a flight result includes an `expires_at` field, let the user know the offer is time-sensitive.

## Output Format for build_itinerary

The itinerary items should be ordered chronologically. Each item's `details` object should contain all relevant specifics:

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
