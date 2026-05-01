"""
Abstract base class for all ticket providers.

A ticket provider wraps a venue's booking/availability API and exposes a
normalised interface so that multiple providers can be used interchangeably.

All date parameters follow ISO 8601 (YYYY-MM-DD). Internal date-format
conversions are the responsibility of each concrete provider implementation.
"""

from abc import ABC, abstractmethod

from .models import Activity, AvailabilitySlot, CalendarDay, PriceTier, Venue


class TicketProvider(ABC):
    """Abstract base for a read-only ticket availability provider.

    Concrete subclasses must implement every abstract method.  The caller
    is expected to invoke `init()` once before calling any other method so
    that the provider can establish HTTP sessions, load configuration, or
    perform any other one-time setup.

    All methods are synchronous and use a shared HTTP client internally.
    """

    @abstractmethod
    def init(self) -> None:
        """Initialize the provider.

        Must be called before any other method.  Implementations should
        create the HTTP client, establish session cookies, and perform any
        required warm-up requests here.

        Returns:
            None

        Raises:
            RuntimeError: If initialisation fails (e.g. network error
                during the warm-up request).
        """

    @abstractmethod
    def get_venues(self) -> list[Venue]:
        """Return the list of venues supported by this provider.

        Returns:
            A list of Venue objects.  The list may be empty if no venues
            are available.
        """

    @abstractmethod
    def get_activities(self, venue_id: str) -> list[Activity]:
        """Return the list of activities available at the given venue.

        Args:
            venue_id: The identifier of the venue as returned by
                `get_venues()`.

        Returns:
            A list of Activity objects.  The list may be empty.

        Raises:
            ValueError: If venue_id is not recognised by this provider.
        """

    @abstractmethod
    def get_calendar(
        self,
        venue_id: str,
        from_date: str,
        to_date: str,
        activity_id: str | None = None,
    ) -> list[CalendarDay]:
        """Return per-day availability summary for a date range.

        Useful for rendering a calendar view before fetching per-slot
        availability with `get_availability`.

        Args:
            venue_id: The identifier of the venue.
            from_date: Start of the date range in YYYY-MM-DD format
                (inclusive).
            to_date: End of the date range in YYYY-MM-DD format
                (inclusive).
            activity_id: Restrict the calendar to a specific activity.
                If None the provider may use a default activity or return
                aggregated data across all activities.

        Returns:
            A list of CalendarDay objects, one per date in the range for
            which the provider returned data.
        """

    @abstractmethod
    def get_availability(
        self,
        venue_id: str,
        day: str,
        activity_id: str | None = None,
        num_people: int = 1,
    ) -> list[AvailabilitySlot]:
        """Return time-slot availability for a specific day.

        Args:
            venue_id: The identifier of the venue.
            day: The date to query in YYYY-MM-DD format.
            activity_id: The identifier of the activity to query.  If None,
                the provider should use a sensible default (e.g. the
                general-admission activity).
            num_people: The number of people in the group.  This value is
                used to set `AvailabilitySlot.has_availability` (True when
                `seats_available >= num_people`) and is stored in
                `AvailabilitySlot.requested_seats` for reference.
                Defaults to 1.

        Returns:
            A list of AvailabilitySlot objects, one per time slot returned
            by the provider.  The list may be empty if no sessions exist
            for the requested date.
        """

    @abstractmethod
    def get_prices(
        self,
        venue_id: str,
        day: str,
        start_time: str,
        activity_id: str | None = None,
    ) -> list[PriceTier]:
        """Return the pricing tiers available for a specific time slot.

        Args:
            venue_id: The identifier of the venue.
            day: The date of the session in YYYY-MM-DD format.
            start_time: The start time of the session in HH:MM format
                (e.g. "09:30").  Must match a slot returned by
                `get_availability` for the same day.
            activity_id: The identifier of the activity.  If None, the
                provider should use a sensible default.

        Returns:
            A list of PriceTier objects, one per ticket type available for
            the requested slot.  The list may be empty if the provider does
            not support pricing or no tiers are configured for this slot.
        """
