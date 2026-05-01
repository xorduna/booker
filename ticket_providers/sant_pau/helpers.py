"""
Stateless helper functions for the Sant Pau ticket provider.

These functions handle:
- Date/time format conversion between ISO 8601 and the Sant Pau API format
- Availability status computation
- Parsing of raw API response dicts into normalised model objects

They are pure functions with no side-effects and no HTTP calls, which
makes them straightforward to unit-test in isolation.

NOTE — nPers / percPers field semantics
----------------------------------------
The Sant Pau API returns three capacity-related fields per session:

  totalPers  — total seat capacity (integer, may be null for special sessions)
  nPers      — number of seats STILL AVAILABLE for booking (integer)
  percPers   — percentage of seats that are STILL AVAILABLE (float, 0.0–100.0)

This is the OPPOSITE of what the field names might suggest.  Empirical
verification: on 16/05/2026 all sessions showed nPers≈342–350 / percPers≈97–100%
while the booking website rendered every slot with green (low-occupancy)
bar-chart icons.  The old "nPers = booked" interpretation produced ~98% occupied
which contradicted the green icons.

Derivations:
  seats_available  = nPers
  seats_total      = totalPers
  percent_available = percPers
  percent_occupied  = 100.0 - percPers
"""

from datetime import datetime

from ..models import (
    SLOT_STATUS_AVAILABLE,
    SLOT_STATUS_LIMITED,
    SLOT_STATUS_SOLD_OUT,
    SLOT_STATUS_UNKNOWN,
    Activity,
    AvailabilitySlot,
    CalendarDay,
    PriceTier,
)
from .constants import (
    SANT_PAU_LIMITED_THRESHOLD_PERCENT_OCCUPIED,
    SANT_PAU_PROVIDER_ID,
    SANT_PAU_VENUE_ID,
)


# ---------------------------------------------------------------------------
# Date and time conversion utilities
# ---------------------------------------------------------------------------


def convert_iso_date_to_sant_pau_format(iso_date_string: str) -> str:
    """Convert an ISO 8601 date string to the DD/MM/YYYY format expected by
    the Sant Pau API.

    The Sant Pau horaris and getCalendari endpoints require dates in
    DD/MM/YYYY format with forward slashes.  Using dashes (DD-MM-YYYY)
    causes the horaris endpoint to silently return an empty list.

    Args:
        iso_date_string: A date in YYYY-MM-DD format (e.g. "2026-05-02").

    Returns:
        The same date in DD/MM/YYYY format (e.g. "02/05/2026").

    Raises:
        ValueError: If the input string cannot be parsed as a valid date.
    """
    parsed_date = datetime.strptime(iso_date_string, "%Y-%m-%d")
    return parsed_date.strftime("%d/%m/%Y")


def convert_four_digit_time_to_hh_mm(four_digit_time_string: str) -> str:
    """Convert a zero-padded 4-digit time string to HH:MM format.

    The Sant Pau API returns session times as 4-digit strings without a
    separator, e.g. "0930" for 09:30 or "1730" for 17:30.

    Args:
        four_digit_time_string: A 4-character string representing a time,
            e.g. "0930".

    Returns:
        The same time in HH:MM format, e.g. "09:30".

    Raises:
        ValueError: If the input is not exactly 4 characters.
    """
    if len(four_digit_time_string) != 4:
        raise ValueError(
            f"Expected a 4-character time string, got "
            f"{repr(four_digit_time_string)!s} "
            f"(length {len(four_digit_time_string)})."
        )
    hours_part = four_digit_time_string[:2]
    minutes_part = four_digit_time_string[2:]
    return f"{hours_part}:{minutes_part}"


def convert_hh_mm_time_to_four_digit(hh_mm_time_string: str) -> str:
    """Convert a HH:MM time string to the zero-padded 4-digit format used
    by the Sant Pau API.

    Inverse of convert_four_digit_time_to_hh_mm.  Used when constructing
    getTarifes requests that require `hora` as a 4-digit string.

    Args:
        hh_mm_time_string: A time string in HH:MM format, e.g. "09:30".

    Returns:
        The same time as a 4-digit zero-padded string, e.g. "0930".

    Raises:
        ValueError: If the input is not in HH:MM format.
    """
    parts = hh_mm_time_string.split(":")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise ValueError(
            f"Expected a time in HH:MM format, got {repr(hh_mm_time_string)!s}."
        )
    return f"{parts[0].zfill(2)}{parts[1].zfill(2)}"


# ---------------------------------------------------------------------------
# Availability computation
# ---------------------------------------------------------------------------


def compute_availability_status(
    seats_available: int | None,
    percent_occupied: float | None,
    limited_threshold_percent_occupied: float = SANT_PAU_LIMITED_THRESHOLD_PERCENT_OCCUPIED,
) -> str:
    """Determine the normalized status string for an availability slot.

    Args:
        seats_available: Number of remaining seats, or None if unknown.
        percent_occupied: Percentage of seats already taken (0.0–100.0),
            or None if unknown.  Note: this is 100 - percPers from the API.
        limited_threshold_percent_occupied: Threshold at or above which the
            slot is considered "limited".  Defaults to 90.0.

    Returns:
        One of "available", "limited", "sold_out", or "unknown".
    """
    if seats_available is None:
        return SLOT_STATUS_UNKNOWN
    if seats_available <= 0:
        return SLOT_STATUS_SOLD_OUT
    if (
        percent_occupied is not None
        and percent_occupied >= limited_threshold_percent_occupied
    ):
        return SLOT_STATUS_LIMITED
    return SLOT_STATUS_AVAILABLE


# ---------------------------------------------------------------------------
# Response parsing helpers
# ---------------------------------------------------------------------------


def parse_activity_from_raw_dict(
    raw_activity_dict: dict,
    venue_id: str,
) -> Activity:
    """Parse a single activity object from the `activitats` API response.

    Args:
        raw_activity_dict: A single element from the JSON array returned by
            the elem=activitats call.
        venue_id: The venue this activity belongs to.

    Returns:
        A normalised Activity dataclass instance.
    """
    activity_id = str(raw_activity_dict["codi"])
    activity_name = raw_activity_dict.get("desc", "").strip()

    return Activity(
        id=activity_id,
        venue_id=venue_id,
        name=activity_name,
        metadata=raw_activity_dict,
    )


def parse_calendar_day_from_raw_dict(
    raw_calendar_day_dict: dict,
    venue_id: str,
    activity_id: str,
) -> CalendarDay:
    """Parse a single calendar day object from the `getCalendari` response.

    Args:
        raw_calendar_day_dict: A single element from the JSON array returned
            by the elem=getCalendari call.
        venue_id: The venue this calendar day belongs to.
        activity_id: The activity this calendar day was queried for.

    Returns:
        A normalised CalendarDay dataclass instance.
    """
    raw_date_string = raw_calendar_day_dict["fecha"]  # already YYYY-MM-DD
    raw_day_type = raw_calendar_day_dict.get("tipus", "")
    raw_portes_obertes = raw_calendar_day_dict.get("portesObertes", "N")

    is_day_available = raw_day_type != "senseLloc"
    is_free_admission_day = raw_portes_obertes == "S"

    return CalendarDay(
        date=raw_date_string,
        venue_id=venue_id,
        activity_id=activity_id,
        is_available=is_day_available,
        is_free_admission_day=is_free_admission_day,
        day_type=raw_day_type,
        metadata=raw_calendar_day_dict,
    )


def parse_availability_slot_from_session_dict(
    raw_session_dict: dict,
    activity_id: str,
    activity_name: str,
    venue_id: str,
    date_string_iso: str,
    requested_seats: int,
) -> AvailabilitySlot:
    """Parse a single session object into a normalised AvailabilitySlot.

    Field semantics (confirmed empirically from HAR + website comparison):
      totalPers  — total capacity (None for special sessions)
      nPers      — seats STILL AVAILABLE (not booked)
      percPers   — percentage of capacity that is STILL AVAILABLE

    Args:
        raw_session_dict: A single element from the "sessions" array inside
            an elem=horaris response object.
        activity_id: The activity identifier this session belongs to.
        activity_name: Human-readable activity name (stripped).
        venue_id: The venue identifier.
        date_string_iso: The queried date in YYYY-MM-DD format.
        requested_seats: The num_people value from the originating
            get_availability call; used to compute has_availability.

    Returns:
        A normalised AvailabilitySlot dataclass instance.
    """
    raw_slot_id = raw_session_dict.get("numSessio")
    raw_start_time = raw_session_dict.get("horaInici", "")
    raw_end_time = raw_session_dict.get("horaFi")
    raw_total_persons = raw_session_dict.get("totalPers")
    raw_num_persons_available = raw_session_dict.get("nPers", 0)
    raw_percent_available = raw_session_dict.get("percPers")

    # Convert 4-digit time strings to HH:MM
    formatted_start_time = (
        convert_four_digit_time_to_hh_mm(raw_start_time)
        if len(raw_start_time) == 4
        else raw_start_time
    )
    formatted_end_time = (
        convert_four_digit_time_to_hh_mm(raw_end_time)
        if raw_end_time and len(raw_end_time) == 4
        else raw_end_time
    )

    # nPers = available seats; totalPers may be None for special sessions
    if raw_total_persons is not None:
        seats_total = int(raw_total_persons)
        seats_available = int(raw_num_persons_available)
    else:
        seats_total = None
        seats_available = None

    # percPers = percent available; percent_occupied = 100 - percPers
    if raw_percent_available is not None:
        percent_available_value = float(raw_percent_available)
        percent_occupied_value = round(100.0 - percent_available_value, 2)
    else:
        percent_available_value = None
        percent_occupied_value = None

    availability_status = compute_availability_status(
        seats_available=seats_available,
        percent_occupied=percent_occupied_value,
    )

    has_availability_for_group = (
        seats_available is not None and seats_available >= requested_seats
    )

    return AvailabilitySlot(
        provider=SANT_PAU_PROVIDER_ID,
        venue_id=venue_id,
        activity_id=activity_id,
        activity_name=activity_name,
        date=date_string_iso,
        start_time=formatted_start_time,
        end_time=formatted_end_time,
        seats_available=seats_available,
        seats_total=seats_total,
        percent_occupied=percent_occupied_value,
        percent_available=percent_available_value,
        has_availability=has_availability_for_group,
        requested_seats=requested_seats,
        status=availability_status,
        slot_id=str(raw_slot_id) if raw_slot_id is not None else None,
        metadata=raw_session_dict,
    )


def parse_price_tier_from_raw_dict(raw_price_tier_dict: dict) -> PriceTier:
    """Parse a single price tier object from the `getTarifes` API response.

    Args:
        raw_price_tier_dict: A single element from the JSON array returned
            by the elem=getTarifes call.

    Returns:
        A normalised PriceTier dataclass instance.
    """
    tier_id = str(raw_price_tier_dict.get("codi", ""))
    tier_name = raw_price_tier_dict.get("desc", "").strip()
    tier_description = (raw_price_tier_dict.get("observ") or "").strip()
    price_eur = str(raw_price_tier_dict.get("preu", "0.00"))
    original_price_eur = str(raw_price_tier_dict.get("preuOriginal", price_eur))
    is_membership_card_required = raw_price_tier_dict.get("amic", "N") == "S"
    is_free_admission_day_only = (
        raw_price_tier_dict.get("portesObertes", "N") == "S"
    )
    raw_min_persons = raw_price_tier_dict.get("minPers")
    raw_max_persons = raw_price_tier_dict.get("maxPers")
    min_persons = int(raw_min_persons) if raw_min_persons is not None else None
    max_persons = int(raw_max_persons) if raw_max_persons is not None else None

    return PriceTier(
        id=tier_id,
        name=tier_name,
        description=tier_description,
        price_eur=price_eur,
        original_price_eur=original_price_eur,
        is_membership_card_required=is_membership_card_required,
        is_free_admission_day_only=is_free_admission_day_only,
        min_persons=min_persons,
        max_persons=max_persons,
        metadata=raw_price_tier_dict,
    )
