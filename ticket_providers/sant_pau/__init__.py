"""
Sant Pau ticket provider package.

Re-exports the public surface so that existing code importing from
`ticket_providers.sant_pau` continues to work after the refactoring of the
single-file module into a package.
"""

from .constants import (
    SANT_PAU_ACTIVITY_GROUP,
    SANT_PAU_BASE_FORM_PARAMS,
    SANT_PAU_BASE_URL,
    SANT_PAU_BROWSER_HEADERS,
    SANT_PAU_FALLBACK_ACTIVITY_ID,
    SANT_PAU_FALLBACK_ACTIVITY_NAME,
    SANT_PAU_HORA_PARAM_ALL_SLOTS,
    SANT_PAU_INITIAL_PAGE_URL,
    SANT_PAU_LANGUAGE_CODE,
    SANT_PAU_LIMITED_THRESHOLD_PERCENT_OCCUPIED,
    SANT_PAU_MUSEUM_CODE,
    SANT_PAU_PROPERTY_CODE,
    SANT_PAU_PROVIDER_ID,
    SANT_PAU_REQUEST_TIMEOUT_SECONDS,
    SANT_PAU_VENUE_ID,
    SANT_PAU_VENUE_NAME,
)
from .helpers import (
    compute_availability_status,
    convert_four_digit_time_to_hh_mm,
    convert_hh_mm_time_to_four_digit,
    convert_iso_date_to_sant_pau_format,
    parse_activity_from_raw_dict,
    parse_availability_slot_from_session_dict,
    parse_calendar_day_from_raw_dict,
    parse_price_tier_from_raw_dict,
)
from .provider import SantPauProvider

__all__ = [
    # Provider class
    "SantPauProvider",
    # Constants
    "SANT_PAU_ACTIVITY_GROUP",
    "SANT_PAU_BASE_FORM_PARAMS",
    "SANT_PAU_BASE_URL",
    "SANT_PAU_BROWSER_HEADERS",
    "SANT_PAU_FALLBACK_ACTIVITY_ID",
    "SANT_PAU_FALLBACK_ACTIVITY_NAME",
    "SANT_PAU_HORA_PARAM_ALL_SLOTS",
    "SANT_PAU_INITIAL_PAGE_URL",
    "SANT_PAU_LANGUAGE_CODE",
    "SANT_PAU_LIMITED_THRESHOLD_PERCENT_OCCUPIED",
    "SANT_PAU_MUSEUM_CODE",
    "SANT_PAU_PROPERTY_CODE",
    "SANT_PAU_PROVIDER_ID",
    "SANT_PAU_REQUEST_TIMEOUT_SECONDS",
    "SANT_PAU_VENUE_ID",
    "SANT_PAU_VENUE_NAME",
    # Helpers
    "compute_availability_status",
    "convert_four_digit_time_to_hh_mm",
    "convert_hh_mm_time_to_four_digit",
    "convert_iso_date_to_sant_pau_format",
    "parse_activity_from_raw_dict",
    "parse_availability_slot_from_session_dict",
    "parse_calendar_day_from_raw_dict",
    "parse_price_tier_from_raw_dict",
]
