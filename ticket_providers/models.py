"""
Data models for the generic ticket availability wrapper.

These dataclasses represent the normalized output of all ticket providers.
Provider-specific raw fields are stored in the `metadata` dict so that
the same models can be used regardless of which backend is queried.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Venue:
    """A physical venue or monument that can be visited.

    Args:
        id: Provider-scoped unique identifier for the venue.
        name: Human-readable name of the venue.
        provider: Identifier of the provider that manages this venue.
        metadata: Provider-specific raw fields that do not map to a
            standard field.
    """

    id: str
    name: str
    provider: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Activity:
    """A visitable activity offered at a venue (e.g. guided tour, free visit).

    Args:
        id: Provider-scoped unique identifier for the activity.
        venue_id: Identifier of the venue this activity belongs to.
        name: Human-readable name of the activity.
        metadata: Provider-specific raw fields.
    """

    id: str
    venue_id: str
    name: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CalendarDay:
    """Availability summary for one specific date at a venue/activity.

    Args:
        date: ISO date string (YYYY-MM-DD).
        venue_id: Identifier of the venue.
        activity_id: Identifier of the activity.
        is_available: True when there are sessions open for booking on this
            date (i.e. the day is not fully sold out or closed).
        is_free_admission_day: True when the venue offers free entry on this
            date (e.g. a "portes obertes" / open-doors day). Free-entry days
            may still have limited capacity and require a reservation.
        day_type: Raw provider string describing the day category (e.g.
            "EST" for a standard day, "senseLloc" for no-availability day).
        metadata: Provider-specific raw fields.
    """

    date: str
    venue_id: str
    activity_id: str
    is_available: bool
    is_free_admission_day: bool
    day_type: str
    metadata: dict[str, Any] = field(default_factory=dict)


# Valid status values for AvailabilitySlot.status
SLOT_STATUS_AVAILABLE = "available"
SLOT_STATUS_LIMITED = "limited"
SLOT_STATUS_SOLD_OUT = "sold_out"
SLOT_STATUS_CLOSED = "closed"
SLOT_STATUS_UNKNOWN = "unknown"


@dataclass
class AvailabilitySlot:
    """A single bookable time slot for an activity on a specific date.

    Availability numbers are expressed both as absolute seat counts and as
    a percentage so that callers can display whichever format suits them.

    The `has_availability` flag reflects whether the slot can accommodate
    the number of people specified in the originating `get_availability`
    call (the `num_people` parameter).

    Args:
        provider: Identifier of the provider that returned this slot.
        venue_id: Identifier of the venue.
        activity_id: Identifier of the activity.
        activity_name: Human-readable name of the activity.
        date: ISO date string (YYYY-MM-DD).
        start_time: Slot start time in HH:MM format.
        end_time: Slot end time in HH:MM format, or None if unknown.
        seats_available: Number of seats that can still be booked, or None
            if the provider did not supply capacity data for this slot.
        seats_total: Maximum number of seats for this slot (capacity), or
            None if unknown.
        percent_occupied: Percentage of seats already taken (0.0–100.0),
            as reported by the provider. None if unknown.
        percent_available: Percentage of seats still free (0.0–100.0),
            calculated as 100.0 - percent_occupied. None if unknown.
        has_availability: True when seats_available is not None and
            seats_available >= requested_seats.
        requested_seats: The value of `num_people` that was passed to
            `get_availability` when this slot was retrieved.
        status: One of "available", "limited", "sold_out", "closed",
            "unknown".
        slot_id: Provider-scoped identifier for this specific session/slot,
            or None if the provider does not assign one.
        metadata: Provider-specific raw fields.
    """

    provider: str
    venue_id: str
    activity_id: str
    activity_name: str
    date: str
    start_time: str
    end_time: str | None
    seats_available: int | None
    seats_total: int | None
    percent_occupied: float | None
    percent_available: float | None
    has_availability: bool
    requested_seats: int
    status: str
    slot_id: str | None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PriceTier:
    """A single pricing tier available for a time slot.

    Represents one ticket type (e.g. "General", "BCN Card", "Menors 12 anys")
    that can be selected when booking a specific session.

    Args:
        id: Provider-scoped unique identifier for this price tier.
        name: Human-readable name of the tier (e.g. "General").
        description: Extended description / conditions text.
        price_eur: Ticket price as a decimal string (e.g. "18.00").
        original_price_eur: Pre-discount price as a decimal string; may
            equal price_eur when no discount applies.
        is_membership_card_required: True when this tier requires presenting
            a membership or discount card at the entrance.
        is_free_admission_day_only: True when this tier is only valid on
            free-admission (open-doors) days.
        min_persons: Minimum number of persons for this tier, or None.
        max_persons: Maximum number of persons for this tier, or None.
        metadata: Provider-specific raw fields.
    """

    id: str
    name: str
    description: str
    price_eur: str
    original_price_eur: str
    is_membership_card_required: bool
    is_free_admission_day_only: bool
    min_persons: int | None
    max_persons: int | None
    metadata: dict[str, Any] = field(default_factory=dict)
