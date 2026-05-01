"""
SantPauProvider — concrete TicketProvider implementation for
Recinte Modernista de Sant Pau (Barcelona).

This module contains only the provider class.  All constants live in
`constants.py` and all parsing/conversion helpers live in `helpers.py`.
"""

import logging
import time

import httpx

from ..base import TicketProvider
from ..models import Activity, AvailabilitySlot, CalendarDay, PriceTier, Venue
from .constants import (
    SANT_PAU_ACTIVITY_GROUP,
    SANT_PAU_BASE_FORM_PARAMS,
    SANT_PAU_BASE_URL,
    SANT_PAU_BROWSER_HEADERS,
    SANT_PAU_FALLBACK_ACTIVITY_ID,
    SANT_PAU_FALLBACK_ACTIVITY_NAME,
    SANT_PAU_HORA_PARAM_ALL_SLOTS,
    SANT_PAU_INITIAL_PAGE_URL,
    SANT_PAU_MUSEUM_CODE,
    SANT_PAU_PROPERTY_CODE,
    SANT_PAU_PROVIDER_ID,
    SANT_PAU_REQUEST_TIMEOUT_SECONDS,
    SANT_PAU_VENUE_ID,
    SANT_PAU_VENUE_NAME,
)
from .helpers import (
    convert_hh_mm_time_to_four_digit,
    convert_iso_date_to_sant_pau_format,
    parse_activity_from_raw_dict,
    parse_availability_slot_from_session_dict,
    parse_calendar_day_from_raw_dict,
    parse_price_tier_from_raw_dict,
)

logger = logging.getLogger(__name__)


class SantPauProvider(TicketProvider):
    """Ticket provider for Recinte Modernista de Sant Pau (Barcelona).

    This provider wraps the EUROMUS/CCALGIR booking API used by the Sant
    Pau ticketing website.  It is read-only: it queries availability and
    pricing but does not support purchasing or reservations.

    Usage::

        provider = SantPauProvider()
        provider.init()
        venues = provider.get_venues()
        slots = provider.get_availability("sant_pau", "2026-06-15", num_people=2)
        prices = provider.get_prices("sant_pau", "2026-06-15", "09:30")

    Args:
        between_requests_sleep_seconds: Optional delay (in seconds) inserted
            before every POST request to the Sant Pau API.  A small value
            (e.g. 1.0–2.0) makes automated clients less conspicuous to rate
            limiters and Cloudflare.  Defaults to 0.0 (no sleep).
    """

    def __init__(
        self,
        between_requests_sleep_seconds: float = 0.0,
    ) -> None:
        self._http_client: httpx.Client | None = None
        self._between_requests_sleep_seconds = between_requests_sleep_seconds

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def init(self) -> None:
        """Initialise the HTTP session by loading the Sant Pau index page.

        This call establishes the JSESSIONID cookie required for all
        subsequent API calls.  It must be called exactly once before any
        other method.

        Raises:
            RuntimeError: If the HTTP session cannot be established.
        """
        self._http_client = httpx.Client(
            headers=SANT_PAU_BROWSER_HEADERS,
            follow_redirects=True,
            timeout=SANT_PAU_REQUEST_TIMEOUT_SECONDS,
        )
        try:
            index_page_response = self._http_client.get(
                SANT_PAU_INITIAL_PAGE_URL
            )
            index_page_response.raise_for_status()
            logger.debug(
                "Sant Pau session initialised. "
                "Cookies: %s",
                dict(self._http_client.cookies),
            )
        except httpx.HTTPError as http_error:
            raise RuntimeError(
                f"Failed to initialise Sant Pau session: {http_error}"
            ) from http_error

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_initialised_client(self) -> httpx.Client:
        """Return the HTTP client, raising if init() has not been called.

        Returns:
            The initialised httpx.Client instance.

        Raises:
            RuntimeError: If init() has not been called yet.
        """
        if self._http_client is None:
            raise RuntimeError(
                "SantPauProvider.init() must be called before any other method."
            )
        return self._http_client

    def _sleep_between_requests(self) -> None:
        """Sleep for the configured inter-request delay.

        No-op when between_requests_sleep_seconds is zero (the default).
        """
        if self._between_requests_sleep_seconds > 0:
            time.sleep(self._between_requests_sleep_seconds)

    def _post_to_api(self, form_params: dict[str, str]) -> list | dict:
        """Perform a POST request to the Sant Pau API endpoint.

        Merges the common base params (codiMuseu, property, lang) with the
        action-specific params before sending.  Sleeps for the configured
        inter-request delay before the request.

        Args:
            form_params: Action-specific form fields.  The common params are
                merged in automatically.

        Returns:
            The parsed JSON response body (list or dict).

        Raises:
            httpx.HTTPStatusError: If the server returns a non-2xx status.
            httpx.HTTPError: On any network-level error.
            ValueError: If the response body is not valid JSON.
        """
        self._sleep_between_requests()
        http_client = self._require_initialised_client()
        merged_form_params = {**SANT_PAU_BASE_FORM_PARAMS, **form_params}
        api_response = http_client.post(
            SANT_PAU_BASE_URL,
            data=merged_form_params,
        )
        api_response.raise_for_status()
        return api_response.json()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_venues(self) -> list[Venue]:
        """Return the single Sant Pau venue.

        In v1 the list of venues is hardcoded because the Sant Pau API
        does not expose a venues endpoint; only one monument is managed
        through this booking system.

        Returns:
            A one-element list containing the Recinte Modernista de Sant
            Pau venue.
        """
        sant_pau_venue = Venue(
            id=SANT_PAU_VENUE_ID,
            name=SANT_PAU_VENUE_NAME,
            provider=SANT_PAU_PROVIDER_ID,
            metadata={
                "initial_page_url": SANT_PAU_INITIAL_PAGE_URL,
                "museum_code": SANT_PAU_MUSEUM_CODE,
                "property_code": SANT_PAU_PROPERTY_CODE,
            },
        )
        return [sant_pau_venue]

    def get_activities(self, venue_id: str) -> list[Activity]:
        """Query the Sant Pau API for available activities and return them
        as normalised Activity objects.

        Falls back to a single hardcoded default activity (Visita Lliure,
        id="1") if the API call fails for any reason, so that callers can
        always proceed to fetch availability.

        Args:
            venue_id: Must be "sant_pau".  Raises ValueError otherwise.

        Returns:
            A list of Activity objects.

        Raises:
            ValueError: If venue_id is not "sant_pau".
        """
        if venue_id != SANT_PAU_VENUE_ID:
            raise ValueError(
                f"SantPauProvider only supports venue_id={SANT_PAU_VENUE_ID!r}, "
                f"got {venue_id!r}."
            )

        activities_form_params: dict[str, str] = {
            "elem": "activitats",
            "codiActiv": "",
            "codiCombi": "",
            "codiCicle": "",
            "grupActiv": SANT_PAU_ACTIVITY_GROUP,
            "dataVisita": "",
            "besCodiActiv": "",
            "besCodiCombi": "",
        }

        try:
            raw_activities_list = self._post_to_api(activities_form_params)
            if not isinstance(raw_activities_list, list):
                raise ValueError(
                    f"Expected a JSON array from elem=activitats, "
                    f"got {type(raw_activities_list).__name__}."
                )
            parsed_activities = [
                parse_activity_from_raw_dict(
                    raw_activity_dict=raw_activity,
                    venue_id=venue_id,
                )
                for raw_activity in raw_activities_list
            ]
            logger.debug("Fetched %d activities from Sant Pau.", len(parsed_activities))
            return parsed_activities

        except Exception as fetch_error:
            logger.warning(
                "get_activities failed (%s); returning fallback activity.",
                fetch_error,
            )
            fallback_activity = Activity(
                id=SANT_PAU_FALLBACK_ACTIVITY_ID,
                venue_id=venue_id,
                name=SANT_PAU_FALLBACK_ACTIVITY_NAME,
                metadata={"fallback": True},
            )
            return [fallback_activity]

    def get_calendar(
        self,
        venue_id: str,
        from_date: str,
        to_date: str,
        activity_id: str | None = None,
    ) -> list[CalendarDay]:
        """Query the Sant Pau API for a per-day availability calendar.

        This is useful for quickly identifying which dates have open
        sessions before calling `get_availability` for a specific day.

        Args:
            venue_id: Must be "sant_pau".
            from_date: Start date in YYYY-MM-DD format (inclusive).
            to_date: End date in YYYY-MM-DD format (inclusive).
            activity_id: The activity to query.  Defaults to the fallback
                activity ("1" = Visita Lliure) if None.

        Returns:
            A list of CalendarDay objects, one per date returned by the API.

        Raises:
            ValueError: If venue_id is not "sant_pau" or date formats are
                invalid.
        """
        if venue_id != SANT_PAU_VENUE_ID:
            raise ValueError(
                f"SantPauProvider only supports venue_id={SANT_PAU_VENUE_ID!r}, "
                f"got {venue_id!r}."
            )

        effective_activity_id = activity_id or SANT_PAU_FALLBACK_ACTIVITY_ID

        from_date_sant_pau_format = convert_iso_date_to_sant_pau_format(from_date)
        to_date_sant_pau_format = convert_iso_date_to_sant_pau_format(to_date)

        calendar_form_params: dict[str, str] = {
            "elem": "getCalendari",
            "fI": from_date_sant_pau_format,
            "fF": to_date_sant_pau_format,
            "fFBes": "",
            "cActivitats": effective_activity_id,
            "cActivitatsN": "",
            "activSel": effective_activity_id,
        }

        raw_calendar_list = self._post_to_api(calendar_form_params)

        if not isinstance(raw_calendar_list, list):
            raise ValueError(
                f"Expected a JSON array from elem=getCalendari, "
                f"got {type(raw_calendar_list).__name__}."
            )

        parsed_calendar_days = [
            parse_calendar_day_from_raw_dict(
                raw_calendar_day_dict=raw_day,
                venue_id=venue_id,
                activity_id=effective_activity_id,
            )
            for raw_day in raw_calendar_list
        ]

        logger.debug(
            "Fetched calendar for %s → %s: %d days.",
            from_date,
            to_date,
            len(parsed_calendar_days),
        )
        return parsed_calendar_days

    def get_availability(
        self,
        venue_id: str,
        day: str,
        activity_id: str | None = None,
        num_people: int = 1,
    ) -> list[AvailabilitySlot]:
        """Query the Sant Pau API for time-slot availability on a given day.

        Args:
            venue_id: Must be "sant_pau".
            day: The date to query in YYYY-MM-DD format.
            activity_id: The activity to query.  If None, defaults to "1"
                (Visita Lliure — general admission).
            num_people: The size of the group.  Sets the
                `has_availability` flag on each returned slot.

        Returns:
            A list of AvailabilitySlot objects.  Returns an empty list if
            the API returns no sessions for the requested date/activity.

        Raises:
            ValueError: If venue_id is not "sant_pau" or the date format
                is invalid.
        """
        if venue_id != SANT_PAU_VENUE_ID:
            raise ValueError(
                f"SantPauProvider only supports venue_id={SANT_PAU_VENUE_ID!r}, "
                f"got {venue_id!r}."
            )

        effective_activity_id = activity_id or SANT_PAU_FALLBACK_ACTIVITY_ID
        date_in_sant_pau_format = convert_iso_date_to_sant_pau_format(day)

        horaris_form_params: dict[str, str] = {
            "elem": "horaris",
            "codiActiv": effective_activity_id,
            "hora": SANT_PAU_HORA_PARAM_ALL_SLOTS,
            "fecha": date_in_sant_pau_format,
        }

        raw_horaris_response = self._post_to_api(horaris_form_params)

        if not isinstance(raw_horaris_response, list):
            logger.warning(
                "Unexpected horaris response type %s for day %s.",
                type(raw_horaris_response).__name__,
                day,
            )
            return []

        parsed_availability_slots: list[AvailabilitySlot] = []

        for raw_activity_wrapper in raw_horaris_response:
            raw_activity_id = str(raw_activity_wrapper.get("codi", effective_activity_id))
            raw_activity_name = raw_activity_wrapper.get("desc", "").strip()
            raw_sessions_list = raw_activity_wrapper.get("sessions", [])

            for raw_session in raw_sessions_list:
                parsed_slot = parse_availability_slot_from_session_dict(
                    raw_session_dict=raw_session,
                    activity_id=raw_activity_id,
                    activity_name=raw_activity_name,
                    venue_id=venue_id,
                    date_string_iso=day,
                    requested_seats=num_people,
                )
                parsed_availability_slots.append(parsed_slot)

        logger.debug(
            "Fetched %d slots for activity=%s on %s.",
            len(parsed_availability_slots),
            effective_activity_id,
            day,
        )
        return parsed_availability_slots

    def get_prices(
        self,
        venue_id: str,
        day: str,
        start_time: str,
        activity_id: str | None = None,
    ) -> list[PriceTier]:
        """Query the Sant Pau API for pricing tiers available for a specific
        time slot.

        Sends an elem=getTarifes request for the given date and start time.
        The pricing response lists every ticket type (General, BCN Card,
        Menors 12 anys, etc.) with the current price and conditions.

        Args:
            venue_id: Must be "sant_pau".
            day: The date of the session in YYYY-MM-DD format.
            start_time: The start time of the session in HH:MM format
                (e.g. "09:30").  Must match the start_time of an
                AvailabilitySlot returned by get_availability for this day.
            activity_id: The activity to query.  Defaults to "1"
                (Visita Lliure) if None.

        Returns:
            A list of PriceTier objects.  Returns an empty list if the API
            returns no tiers for the requested slot.

        Raises:
            ValueError: If venue_id is not "sant_pau", the date format is
                invalid, or the start_time is not in HH:MM format.
        """
        if venue_id != SANT_PAU_VENUE_ID:
            raise ValueError(
                f"SantPauProvider only supports venue_id={SANT_PAU_VENUE_ID!r}, "
                f"got {venue_id!r}."
            )

        effective_activity_id = activity_id or SANT_PAU_FALLBACK_ACTIVITY_ID
        date_in_sant_pau_format = convert_iso_date_to_sant_pau_format(day)
        hora_four_digit = convert_hh_mm_time_to_four_digit(start_time)

        tarifes_form_params: dict[str, str] = {
            "elem": "getTarifes",
            "cActivitats": effective_activity_id,
            "temporada": "",
            "fecha": date_in_sant_pau_format,
            "hora": hora_four_digit,
            "portesO": "false",
            "numerada": "false",
            "grupTarifa": "",
        }

        raw_tarifes_response = self._post_to_api(tarifes_form_params)

        if not isinstance(raw_tarifes_response, list):
            logger.warning(
                "Unexpected getTarifes response type %s for %s %s.",
                type(raw_tarifes_response).__name__,
                day,
                start_time,
            )
            return []

        parsed_price_tiers = [
            parse_price_tier_from_raw_dict(raw_price_tier_dict=raw_tier)
            for raw_tier in raw_tarifes_response
        ]

        logger.debug(
            "Fetched %d price tiers for activity=%s on %s at %s.",
            len(parsed_price_tiers),
            effective_activity_id,
            day,
            start_time,
        )
        return parsed_price_tiers
