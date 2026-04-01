"""
Currency conversion: detected local currency → USD.

The fli package returns prices in whatever currency Google Flights
assigns based on the server's IP geolocation. This module:
  1. Detects the source currency (IP geolocation → locale → env var → default)
  2. Fetches live exchange rates from free APIs (cached 6 hours)
  3. Falls back to hardcoded approximate rates if APIs are unreachable
  4. Converts all flight prices to USD before returning results
"""

import logging
import os
import locale
import time
import requests

logger = logging.getLogger(__name__)

# ── Fallback exchange rates (to USD) ───────────────────────────
# Approximate rates — only used if live API is unreachable.
_FALLBACK_RATES_TO_USD = {
    "USD": 1.0,
    "CAD": 0.73,    # 1 CAD ≈ 0.73 USD
    "EUR": 1.08,    # 1 EUR ≈ 1.08 USD
    "GBP": 1.27,    # 1 GBP ≈ 1.27 USD
    "AUD": 0.65,    # 1 AUD ≈ 0.65 USD
    "JPY": 0.0067,  # 1 JPY ≈ 0.0067 USD
    "INR": 0.012,   # 1 INR ≈ 0.012 USD
    "CNY": 0.14,    # 1 CNY ≈ 0.14 USD
    "KRW": 0.00074, # 1 KRW ≈ 0.00074 USD
    "MXN": 0.058,   # 1 MXN ≈ 0.058 USD
    "BRL": 0.20,    # 1 BRL ≈ 0.20 USD
    "CHF": 1.13,    # 1 CHF ≈ 1.13 USD
}

# Country code → currency mapping (used by both locale and IP detection)
_COUNTRY_TO_CURRENCY = {
    "CA": ("CAD", "CA$"),
    "US": ("USD", "$"),
    "GB": ("GBP", "£"),
    "UK": ("GBP", "£"),
    "AU": ("AUD", "A$"),
    "JP": ("JPY", "¥"),
    "IN": ("INR", "₹"),
    "CN": ("CNY", "¥"),
    "KR": ("KRW", "₩"),
    "MX": ("MXN", "MX$"),
    "BR": ("BRL", "R$"),
    "CH": ("CHF", "CHF"),
    "DE": ("EUR", "€"),
    "FR": ("EUR", "€"),
    "IT": ("EUR", "€"),
    "ES": ("EUR", "€"),
    "NL": ("EUR", "€"),
    "BE": ("EUR", "€"),
    "AT": ("EUR", "€"),
    "IE": ("EUR", "€"),
    "PT": ("EUR", "€"),
    "FI": ("EUR", "€"),
}


def _currency_symbol(code: str) -> str:
    symbols = {
        "USD": "$", "CAD": "CA$", "EUR": "€", "GBP": "£",
        "AUD": "A$", "JPY": "¥", "INR": "₹", "CNY": "¥",
        "KRW": "₩", "MXN": "MX$", "BRL": "R$", "CHF": "CHF",
    }
    return symbols.get(code, code)


# ── Currency detection ─────────────────────────────────────────

def _detect_country_from_ip() -> str | None:
    """
    Detect the server's country via free IP geolocation APIs.
    Returns a 2-letter country code (e.g. "CA", "US") or None.
    This matches what Google Flights uses to determine currency.
    """
    apis = [
        ("https://ipapi.co/country_code/", "text"),
        ("https://ifconfig.co/country-iso", "text"),
        ("http://ip-api.com/json/?fields=countryCode", "json"),
    ]
    for url, resp_type in apis:
        try:
            resp = requests.get(url, timeout=3)
            if resp.status_code == 200:
                if resp_type == "json":
                    country = resp.json().get("countryCode", "").strip().upper()
                else:
                    country = resp.text.strip().upper()
                if len(country) == 2 and country.isalpha():
                    logger.info("IP geolocation detected country: %s (from %s)",
                               country, url.split("/")[2])
                    return country
        except Exception:
            continue
    return None


def _detect_country_from_locale() -> str | None:
    """
    Try to extract a country code from system locale.
    Works on Linux (en_CA.UTF-8) and Windows (English_Canada).
    """
    try:
        loc = locale.getlocale()[0] or ""
        if not loc or loc == "C":
            try:
                loc = locale.getdefaultlocale()[0] or ""
            except Exception:
                loc = ""

        if not loc or loc == "C":
            return None

        # Linux-style: en_CA.UTF-8 or en_CA → split on _
        if "_" in loc:
            country = loc.split("_")[-1].split(".")[0].upper()
            if len(country) == 2 and country.isalpha():
                return country

        # Windows-style: "English_Canada" or "English_United States"
        windows_locale_map = {
            "canada": "CA",
            "united states": "US",
            "united kingdom": "GB",
            "australia": "AU",
            "japan": "JP",
            "india": "IN",
            "china": "CN",
            "korea": "KR",
            "mexico": "MX",
            "brazil": "BR",
            "france": "FR",
            "germany": "DE",
            "italy": "IT",
            "spain": "ES",
            "switzerland": "CH",
        }
        loc_lower = loc.lower()
        for name, code in windows_locale_map.items():
            if name in loc_lower:
                return code
    except Exception:
        pass
    return None


def detect_source_currency() -> tuple[str, str]:
    """
    Detect the currency that Google Flights is likely returning
    based on the server's location.

    Priority:
    1. FLIGHT_CURRENCY env var (explicit override)
    2. IP geolocation (most accurate — matches what Google sees)
    3. System locale
    4. Default: USD

    Returns (currency_code, currency_symbol)
    """
    # 1. Explicit env var
    env_currency = os.environ.get("FLIGHT_CURRENCY", "").upper().strip()
    if env_currency:
        logger.info("Source currency from FLIGHT_CURRENCY env var: %s", env_currency)
        return env_currency, _currency_symbol(env_currency)

    # 2. IP geolocation (this is what Google Flights actually uses)
    country = _detect_country_from_ip()
    if country and country in _COUNTRY_TO_CURRENCY:
        code, symbol = _COUNTRY_TO_CURRENCY[country]
        logger.info("Source currency from IP geolocation (%s): %s", country, code)
        return code, symbol

    # 3. System locale
    country = _detect_country_from_locale()
    if country and country in _COUNTRY_TO_CURRENCY:
        code, symbol = _COUNTRY_TO_CURRENCY[country]
        logger.info("Source currency from system locale (%s): %s", country, code)
        return code, symbol

    # 4. Default
    logger.warning("Could not detect source currency — defaulting to USD. "
                    "Set FLIGHT_CURRENCY in .env if prices look wrong.")
    return "USD", "$"


# ── Rate cache ─────────────────────────────────────────────────
_cached_rate: float | None = None
_cached_from: str | None = None
_cached_at: float = 0
_CACHE_TTL = 6 * 3600  # 6 hours


def _fetch_live_rate(from_currency: str) -> float | None:
    """
    Fetch the live exchange rate from a free API.
    Returns the rate to convert 1 unit of from_currency to USD,
    or None if the request fails.
    """
    from_currency = from_currency.upper()
    if from_currency == "USD":
        return 1.0

    apis = [
        f"https://open.er-api.com/v6/latest/{from_currency}",
        f"https://api.exchangerate-api.com/v4/latest/{from_currency}",
    ]

    for url in apis:
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                rates = data.get("rates", {})
                usd_rate = rates.get("USD")
                if usd_rate and usd_rate > 0:
                    logger.info(
                        "Fetched live exchange rate: 1 %s = %.6f USD (from %s)",
                        from_currency, usd_rate, url.split("/")[2],
                    )
                    return float(usd_rate)
        except Exception as exc:
            logger.debug("Exchange rate API failed (%s): %s", url, exc)
            continue

    return None


def get_usd_rate(from_currency: str) -> float:
    """
    Get the exchange rate to convert from_currency → USD.
    Uses cached live rate if fresh, otherwise fetches a new one.
    Falls back to hardcoded rates if all APIs fail.

    Returns a multiplier: price_in_local * rate = price_in_usd
    """
    global _cached_rate, _cached_from, _cached_at

    from_currency = from_currency.upper()
    if from_currency == "USD":
        return 1.0

    # Check cache
    now = time.time()
    if (
        _cached_rate is not None
        and _cached_from == from_currency
        and (now - _cached_at) < _CACHE_TTL
    ):
        return _cached_rate

    # Try live rate
    live_rate = _fetch_live_rate(from_currency)
    if live_rate is not None:
        _cached_rate = live_rate
        _cached_from = from_currency
        _cached_at = now
        return live_rate

    # Fallback to hardcoded
    fallback = _FALLBACK_RATES_TO_USD.get(from_currency)
    if fallback:
        logger.warning(
            "Using fallback exchange rate for %s → USD: %.6f "
            "(live API unavailable). Prices may be approximate.",
            from_currency, fallback,
        )
        # Cache the fallback too so we don't spam warnings
        _cached_rate = fallback
        _cached_from = from_currency
        _cached_at = now
        return fallback

    # Unknown currency — return 1.0 and log a warning
    logger.error(
        "Unknown currency '%s' with no fallback rate. "
        "Prices will NOT be converted and may be incorrect.",
        from_currency,
    )
    return 1.0


def convert_flight_results_to_usd(
    results: list[dict],
    source_currency: str,
) -> list[dict]:
    """
    Convert all price fields in flight results from source_currency to USD.
    Mutates the dicts in-place and returns the same list.

    If source_currency is already USD, this is a no-op.
    """
    source_currency = source_currency.upper()
    if source_currency == "USD":
        return results

    rate = get_usd_rate(source_currency)

    logger.info(
        "Converting %d flight results from %s → USD (rate: 1 %s = %.6f USD)",
        len(results), source_currency, source_currency, rate,
    )

    for result in results:
        # Convert price fields
        if "price_per_person" in result:
            result["price_per_person"] = round(result["price_per_person"] * rate, 2)
        if "total_price" in result:
            result["total_price"] = round(result["total_price"] * rate, 2)

        # Update currency metadata to reflect USD
        result["currency_code"] = "USD"
        result["currency_symbol"] = "$"

    return results