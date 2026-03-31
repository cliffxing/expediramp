"""
Amadeus API client — handles OAuth token lifecycle.

Docs: https://developers.amadeus.com/self-service
"""

import time
import logging
import requests
from config import Config

logger = logging.getLogger(__name__)

_token: str | None = None
_token_expires: float = 0

AMADEUS_HOSTS = {
    "test": "https://test.api.amadeus.com",
    "production": "https://api.amadeus.com",
}


def _base_url() -> str:
    return AMADEUS_HOSTS.get(Config.AMADEUS_ENV, AMADEUS_HOSTS["test"])


def _refresh_token() -> str:
    """Obtain or refresh an Amadeus OAuth2 access token."""
    global _token, _token_expires

    if _token and time.time() < _token_expires - 60:
        return _token

    url = f"{_base_url()}/v1/security/oauth2/token"
    resp = requests.post(
        url,
        data={
            "grant_type": "client_credentials",
            "client_id": Config.AMADEUS_CLIENT_ID,
            "client_secret": Config.AMADEUS_CLIENT_SECRET,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    resp.raise_for_status()
    body = resp.json()

    _token = body["access_token"]
    _token_expires = time.time() + body.get("expires_in", 1799)
    logger.info("Amadeus token refreshed, expires in %ss", body.get("expires_in"))
    return _token


def amadeus_get(path: str, params: dict | None = None) -> dict:
    """Authenticated GET to Amadeus API. Returns the JSON body."""
    token = _refresh_token()
    url = f"{_base_url()}{path}"
    resp = requests.get(
        url,
        params=params,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if resp.status_code == 401:
        # force re-auth and retry once
        global _token_expires
        _token_expires = 0
        token = _refresh_token()
        resp = requests.get(
            url,
            params=params,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
    resp.raise_for_status()
    return resp.json()
