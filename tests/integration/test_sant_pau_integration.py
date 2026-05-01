"""
Integration tests for the Sant Pau provider.

These tests call the REAL Sant Pau ticketing API over the network.
They are intentionally opt-in and must be enabled by setting the
environment variable:

    RUN_INTEGRATION_TESTS=1

Do NOT run these tests in CI unless you have confirmed that the Sant Pau
endpoint is accessible and the rate of calls is acceptable.

Design principles
-----------------
- Only read-only flows are tested (no purchasing).
- A conservative sleep is inserted between each real API call to avoid
  looking like a bot and to be a good citizen towards the endpoint.
- Assertions check structural validity only (types and non-empty data),
  NOT exact availability numbers — those change in real time.
- A single future date is queried; no looping over many dates.
- Timeouts are conservative (defined in the provider constants).

How to run
----------
    RUN_INTEGRATION_TESTS=1 pytest tests/integration/ -v
"""

import os
import time
from datetime import date, timedelta

import pytest

from ticket_providers import SantPauProvider
from ticket_providers.models import (
    Activity,
    AvailabilitySlot,
    CalendarDay,
    PriceTier,
    Venue,
)

# Skip the entire module if the environment variable is not set
pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") != "1",
    reason=(
        "Integration tests are opt-in. "
        "Set RUN_INTEGRATION_TESTS=1 to enable them."
    ),
)

# A date in the near future to query for availability.
# Using tomorrow + 7 days to avoid same-day edge cases.
INTEGRATION_TEST_TARGET_DATE = (date.today() + timedelta(days=7)).isoformat()

# Intentionally conservative sleep between real API calls (seconds).
# This reduces the chance of triggering Cloudflare rate limiting or
# appearing as a bot to the ticketing backend.
SLEEP_SECONDS_BETWEEN_API_CALLS = 2


@pytest.fixture(scope="module")
def initialised_sant_pau_provider():
    """Module-scoped fixture that creates and initialises one provider
    instance for all integration tests in this module."""
    provider = SantPauProvider()
    provider.init()
    # Brief pause after init() to avoid rapid-fire requests
    time.sleep(SLEEP_SECONDS_BETWEEN_API_CALLS)
    return provider


class TestSantPauIntegration:
    """Integration tests that exercise the full Sant Pau provider flow
    against the real ticketing endpoint."""

    def test_get_venues_returns_at_least_one_venue(
        self, initialised_sant_pau_provider: SantPauProvider
    ):
        venues = initialised_sant_pau_provider.get_venues()

        assert isinstance(venues, list)
        assert len(venues) >= 1

        for venue in venues:
            assert isinstance(venue, Venue)
            assert isinstance(venue.id, str) and venue.id
            assert isinstance(venue.name, str) and venue.name
            assert isinstance(venue.provider, str) and venue.provider

        time.sleep(SLEEP_SECONDS_BETWEEN_API_CALLS)

    def test_get_activities_returns_at_least_one_activity(
        self, initialised_sant_pau_provider: SantPauProvider
    ):
        activities = initialised_sant_pau_provider.get_activities("sant_pau")

        assert isinstance(activities, list)
        assert len(activities) >= 1

        for activity in activities:
            assert isinstance(activity, Activity)
            assert isinstance(activity.id, str) and activity.id
            assert isinstance(activity.name, str) and activity.name
            assert activity.venue_id == "sant_pau"

        time.sleep(SLEEP_SECONDS_BETWEEN_API_CALLS)

    def test_get_calendar_returns_calendar_days(
        self, initialised_sant_pau_provider: SantPauProvider
    ):
        from_date = INTEGRATION_TEST_TARGET_DATE
        to_date = (
            date.fromisoformat(INTEGRATION_TEST_TARGET_DATE) + timedelta(days=6)
        ).isoformat()

        calendar_days = initialised_sant_pau_provider.get_calendar(
            venue_id="sant_pau",
            from_date=from_date,
            to_date=to_date,
            activity_id="1",
        )

        assert isinstance(calendar_days, list)
        # The API returns at least some days for any week-long range
        # (though they may all be unavailable)
        for calendar_day in calendar_days:
            assert isinstance(calendar_day, CalendarDay)
            assert isinstance(calendar_day.date, str) and len(calendar_day.date) == 10
            assert isinstance(calendar_day.is_available, bool)
            assert isinstance(calendar_day.is_free_admission_day, bool)
            assert calendar_day.venue_id == "sant_pau"

        time.sleep(SLEEP_SECONDS_BETWEEN_API_CALLS)

    def test_get_availability_returns_list(
        self, initialised_sant_pau_provider: SantPauProvider
    ):
        """The list may be empty if the date has no sessions; the important
        thing is that the call succeeds and returns the correct types."""
        availability_slots = initialised_sant_pau_provider.get_availability(
            venue_id="sant_pau",
            day=INTEGRATION_TEST_TARGET_DATE,
            activity_id="1",
        )

        assert isinstance(availability_slots, list)

        for slot in availability_slots:
            assert isinstance(slot, AvailabilitySlot)
            assert isinstance(slot.start_time, str)
            assert ":" in slot.start_time  # must be HH:MM format
            assert slot.status in {
                "available",
                "limited",
                "sold_out",
                "closed",
                "unknown",
            }
            assert slot.venue_id == "sant_pau"
            assert slot.provider == "sant_pau"
            assert isinstance(slot.requested_seats, int)
            assert isinstance(slot.has_availability, bool)
            if slot.seats_available is not None:
                assert slot.seats_available >= 0
            if slot.percent_occupied is not None:
                assert 0.0 <= slot.percent_occupied <= 100.0

        time.sleep(SLEEP_SECONDS_BETWEEN_API_CALLS)

    def test_get_prices_returns_price_tiers(
        self, initialised_sant_pau_provider: SantPauProvider
    ):
        """Fetch pricing for the first available slot on the target date.

        If no slots are available on that date, the test is skipped rather
        than failed so it does not become a false negative.
        """
        availability_slots = initialised_sant_pau_provider.get_availability(
            venue_id="sant_pau",
            day=INTEGRATION_TEST_TARGET_DATE,
            activity_id="1",
        )
        time.sleep(SLEEP_SECONDS_BETWEEN_API_CALLS)

        available_slots = [
            slot for slot in availability_slots if slot.status != "sold_out"
        ]
        if not available_slots:
            pytest.skip(
                f"No non-sold-out slots found on {INTEGRATION_TEST_TARGET_DATE}; "
                "cannot test get_prices."
            )

        first_slot = available_slots[0]
        price_tiers = initialised_sant_pau_provider.get_prices(
            venue_id="sant_pau",
            day=INTEGRATION_TEST_TARGET_DATE,
            start_time=first_slot.start_time,
            activity_id="1",
        )

        assert isinstance(price_tiers, list)

        for tier in price_tiers:
            assert isinstance(tier, PriceTier)
            assert isinstance(tier.id, str) and tier.id
            assert isinstance(tier.name, str) and tier.name
            assert isinstance(tier.price_eur, str)
            assert isinstance(tier.original_price_eur, str)
            assert isinstance(tier.is_membership_card_required, bool)
            assert isinstance(tier.is_free_admission_day_only, bool)

        # No further sleep needed — this is the last test
