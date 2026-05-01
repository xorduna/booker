"""
Constants for the Sant Pau ticket provider.

All SANT_PAU_* names that are used across multiple modules (helpers,
provider, tests) live here so that there is a single source of truth.
"""

# ---------------------------------------------------------------------------
# Provider / venue identifiers
# ---------------------------------------------------------------------------

SANT_PAU_PROVIDER_ID = "sant_pau"

SANT_PAU_VENUE_ID = "sant_pau"
SANT_PAU_VENUE_NAME = "Recinte Modernista de Sant Pau"

# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

SANT_PAU_BASE_URL = (
    "https://tickets.santpaubarcelona.org/stpmuslinkIV/wsmuslinkIV"
)
SANT_PAU_INITIAL_PAGE_URL = (
    "https://tickets.santpaubarcelona.org/stpmuslinkIV/index.jsp"
    "?lang=1&nom_cache=SANTPAU&property=SANTPAU&grupActiv=1"
)

# ---------------------------------------------------------------------------
# Common form parameter values
# ---------------------------------------------------------------------------

SANT_PAU_MUSEUM_CODE = "SANTPAU"
SANT_PAU_PROPERTY_CODE = "SANTPAU"
SANT_PAU_LANGUAGE_CODE = "1"
SANT_PAU_ACTIVITY_GROUP = "1"

# The `hora` param is sent as the current time in the browser.  Using "0000"
# ensures we always receive ALL time slots for the requested day, not just
# those still in the future relative to the current clock.
SANT_PAU_HORA_PARAM_ALL_SLOTS = "0000"

# ---------------------------------------------------------------------------
# Fallback / default values
# ---------------------------------------------------------------------------

# Fallback activity used when the API call to retrieve activities fails
SANT_PAU_FALLBACK_ACTIVITY_ID = "1"
SANT_PAU_FALLBACK_ACTIVITY_NAME = "Visita Lliure"

# ---------------------------------------------------------------------------
# Availability thresholds
# ---------------------------------------------------------------------------

# Slots with percent_occupied >= this value are mapped to "limited".
# With a typical capacity of 350, 90 % occupied means ~35 seats remaining.
SANT_PAU_LIMITED_THRESHOLD_PERCENT_OCCUPIED = 90.0

# ---------------------------------------------------------------------------
# HTTP client configuration
# ---------------------------------------------------------------------------

# Request timeout in seconds (conservative for a public tourist endpoint)
SANT_PAU_REQUEST_TIMEOUT_SECONDS = 20.0

# Browser-like headers observed in the HAR capture
SANT_PAU_BROWSER_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:149.0) "
        "Gecko/20100101 Firefox/149.0"
    ),
    "Accept": "*/*",
    "Accept-Language": "en,ca;q=0.9,en-US;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "https://tickets.santpaubarcelona.org",
    "Referer": SANT_PAU_INITIAL_PAGE_URL,
}

# Base form params included in every POST request
SANT_PAU_BASE_FORM_PARAMS: dict[str, str] = {
    "codiMuseu": SANT_PAU_MUSEUM_CODE,
    "property": SANT_PAU_PROPERTY_CODE,
    "lang": SANT_PAU_LANGUAGE_CODE,
}
