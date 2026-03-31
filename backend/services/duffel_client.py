"""
Duffel API client — handles authenticated requests to the Duffel Travel API.

Docs: https://duffel.com/docs/api
"""

import logging
import requests
from typing import Any

from config import Config

logger = logging.getLogger(__name__)

DUFFEL_BASE_URL = "https://api.duffel.com"
DUFFEL_API_VERSION = "v2"


def _headers() -> dict:
    """Return Duffel auth headers."""
    if not Config.DUFFEL_ACCESS_TOKEN:
        raise ValueError(
            "DUFFEL_ACCESS_TOKEN is not set. Get a token from https://app.duffel.com/."
        )
    return {
        "Authorization": f"Bearer {Config.DUFFEL_ACCESS_TOKEN}",
        "Duffel-Version": DUFFEL_API_VERSION,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
    }


def duffel_get(path: str, params: dict | None = None) -> dict:
    """Authenticated GET to Duffel API. Returns the JSON body."""
    url = f"{DUFFEL_BASE_URL}{path}"
    resp = requests.get(url, params=params, headers=_headers(), timeout=30)
    _raise_for_duffel_error(resp)
    return resp.json()


def duffel_post(path: str, body: dict) -> dict:
    """Authenticated POST to Duffel API. Returns the JSON body."""
    url = f"{DUFFEL_BASE_URL}{path}"
    resp = requests.post(url, json=body, headers=_headers(), timeout=30)
    _raise_for_duffel_error(resp)
    return resp.json()


def _raise_for_duffel_error(resp: requests.Response) -> None:
    """Raise a descriptive error for Duffel API failures."""
    if resp.ok:
        return
    try:
        err = resp.json()
        errors = err.get("errors", [])
        msg = "; ".join(
            f"{e.get('title', 'Error')}: {e.get('message', '')}" for e in errors
        ) or resp.text
    except Exception:
        msg = resp.text
    raise requests.HTTPError(
        f"Duffel API error {resp.status_code}: {msg}", response=resp
    )


def search_airports(query: str) -> list[dict]:
    """
    Search Duffel for airports matching a city name or IATA code.
    Returns a list of airport objects with id, iata_code, name, city_name.
    """
    data = duffel_get("/air/airports", {"name": query})
    return data.get("data", [])


def resolve_iata_to_duffel_id(iata_code: str) -> str:
    """
    Given an IATA code like 'JFK', return the Duffel airport ID (e.g. 'arp_jfk_us').
    Falls back to constructing the ID if not found.
    """
    try:
        results = search_airports(iata_code)
        for ap in results:
            if ap.get("iata_code", "").upper() == iata_code.upper():
                return ap["id"]
    except Exception as e:
        logger.warning("Airport lookup failed for %s: %s", iata_code, e)
    # Duffel IDs follow a predictable pattern — construct as fallback
    return f"arp_{iata_code.lower()}_us"
