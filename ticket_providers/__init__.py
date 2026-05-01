"""
ticket_providers package.

Exports the public API surface: the abstract base class, all data models,
and concrete provider implementations.
"""

from .base import TicketProvider
from .models import (
    SLOT_STATUS_AVAILABLE,
    SLOT_STATUS_CLOSED,
    SLOT_STATUS_LIMITED,
    SLOT_STATUS_SOLD_OUT,
    SLOT_STATUS_UNKNOWN,
    Activity,
    AvailabilitySlot,
    CalendarDay,
    PriceTier,
    Venue,
)
from .sant_pau import SantPauProvider

__all__ = [
    "TicketProvider",
    "Venue",
    "Activity",
    "CalendarDay",
    "AvailabilitySlot",
    "PriceTier",
    "SLOT_STATUS_AVAILABLE",
    "SLOT_STATUS_LIMITED",
    "SLOT_STATUS_SOLD_OUT",
    "SLOT_STATUS_CLOSED",
    "SLOT_STATUS_UNKNOWN",
    "SantPauProvider",
]
