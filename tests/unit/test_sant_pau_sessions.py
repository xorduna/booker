"""
Unit tests for Sant Pau session/availability-slot parsing.

Covers:
- Correct mapping of raw session fields to AvailabilitySlot
- Seat availability calculation (nPers = available seats)
- Percentage calculations (percent_available = percPers, percent_occupied = 100 - percPers)
- Status mapping (sold_out, limited, available, unknown)
- has_availability flag with various num_people values
- Handling of null totalPers (unknown status)
- Time conversion from 4-digit strings to HH:MM
"""

from unittest.mock import MagicMock

import pytest

from tests.fixtures import MOCK_HORARIS_API_RESPONSE
from ticket_providers.sant_pau import (
    SANT_PAU_PROVIDER_ID,
    SANT_PAU_VENUE_ID,
    SantPauProvider,
    parse_availability_slot_from_session_dict,
)
from ticket_providers.models import (
    SLOT_STATUS_AVAILABLE,
    SLOT_STATUS_LIMITED,
    SLOT_STATUS_SOLD_OUT,
    SLOT_STATUS_UNKNOWN,
)

# ---------------------------------------------------------------------------
# Test constants
# ---------------------------------------------------------------------------

TEST_ACTIVITY_ID = "1"
TEST_ACTIVITY_NAME = "Visita Lliure"
TEST_DATE_ISO = "2026-05-02"


# ---------------------------------------------------------------------------
# Session fixture helpers
# ---------------------------------------------------------------------------

def _make_session_dict(
    *,
    num_sessio: str = "99",
    hora_inici: str = "1000",
    hora_fi: str = "1030",
    total_persons: int | None = 350,
    num_persons_available: int = 315,
    percent_available: float | None = 90.0,
) -> dict:
    """Build a minimal raw session dict for testing.

    Args:
        num_persons_available: seats still available (nPers field).
        percent_available: percent of seats still available (percPers field).
    """
    return {
        "numSessio": num_sessio,
        "idioma": "0",
        "horaInici": hora_inici,
        "horaFi": hora_fi,
        "nomesCombi": None,
        "portesObertes": "N",
        "temporada": "2025 ",
        "identInt": None,
        "totalPers": total_persons,
        "nPers": num_persons_available,
        "percPers": percent_available,
    }


def _parse_test_slot(
    raw_session_dict: dict,
    requested_seats: int = 1,
):
    """Helper: call parse_availability_slot_from_session_dict with standard args."""
    return parse_availability_slot_from_session_dict(
        raw_session_dict=raw_session_dict,
        activity_id=TEST_ACTIVITY_ID,
        activity_name=TEST_ACTIVITY_NAME,
        venue_id=SANT_PAU_VENUE_ID,
        date_string_iso=TEST_DATE_ISO,
        requested_seats=requested_seats,
    )


# ---------------------------------------------------------------------------
# parse_availability_slot_from_session_dict unit tests
# ---------------------------------------------------------------------------


class TestParseAvailabilitySlotFromSessionDict:
    """Tests for the parse_availability_slot_from_session_dict helper."""

    def test_maps_provider_id_correctly(self):
        slot = _parse_test_slot(_make_session_dict())
        assert slot.provider == SANT_PAU_PROVIDER_ID

    def test_maps_venue_id_correctly(self):
        slot = _parse_test_slot(_make_session_dict())
        assert slot.venue_id == SANT_PAU_VENUE_ID

    def test_maps_activity_id_correctly(self):
        slot = _parse_test_slot(_make_session_dict())
        assert slot.activity_id == TEST_ACTIVITY_ID

    def test_maps_date_correctly(self):
        slot = _parse_test_slot(_make_session_dict())
        assert slot.date == TEST_DATE_ISO

    def test_converts_start_time_from_four_digit_string(self):
        slot = _parse_test_slot(_make_session_dict(hora_inici="0930"))
        assert slot.start_time == "09:30"

    def test_converts_end_time_from_four_digit_string(self):
        slot = _parse_test_slot(_make_session_dict(hora_fi="1000"))
        assert slot.end_time == "10:00"

    def test_calculates_seats_available_correctly(self):
        # nPers = 25 means 25 seats are still available
        raw_session = _make_session_dict(total_persons=350, num_persons_available=25)
        slot = _parse_test_slot(raw_session)
        assert slot.seats_available == 25

    def test_sets_seats_total_correctly(self):
        raw_session = _make_session_dict(total_persons=350, num_persons_available=350)
        slot = _parse_test_slot(raw_session)
        assert slot.seats_total == 350

    def test_seats_available_is_zero_when_fully_booked(self):
        # nPers=0 → 0 seats available → sold out
        raw_session = _make_session_dict(
            total_persons=350, num_persons_available=0, percent_available=0.0
        )
        slot = _parse_test_slot(raw_session)
        assert slot.seats_available == 0

    def test_seats_available_is_none_when_total_persons_is_null(self):
        raw_session = _make_session_dict(total_persons=None, num_persons_available=0)
        slot = _parse_test_slot(raw_session)
        assert slot.seats_available is None

    def test_seats_total_is_none_when_total_persons_is_null(self):
        raw_session = _make_session_dict(total_persons=None, num_persons_available=0)
        slot = _parse_test_slot(raw_session)
        assert slot.seats_total is None

    def test_percent_available_matches_api_percpers_value(self):
        # percPers is percent AVAILABLE — should map directly to percent_available
        raw_session = _make_session_dict(percent_available=7.0)
        slot = _parse_test_slot(raw_session)
        assert slot.percent_available == pytest.approx(7.0, abs=0.01)

    def test_percent_occupied_is_complement_of_percent_available(self):
        # percent_occupied = 100 - percPers
        raw_session = _make_session_dict(percent_available=7.0)
        slot = _parse_test_slot(raw_session)
        assert slot.percent_occupied == pytest.approx(93.0, abs=0.01)

    def test_percent_available_is_none_when_percpers_is_none(self):
        raw_session = {
            "numSessio": "1",
            "horaInici": "1000",
            "horaFi": "1030",
            "totalPers": None,
            "nPers": 0,
            "percPers": None,
        }
        slot = _parse_test_slot(raw_session)
        assert slot.percent_available is None

    def test_slot_id_matches_num_sessio(self):
        raw_session = _make_session_dict(num_sessio="23")
        slot = _parse_test_slot(raw_session)
        assert slot.slot_id == "23"

    def test_raw_session_dict_is_preserved_in_metadata(self):
        raw_session = _make_session_dict(num_sessio="23")
        slot = _parse_test_slot(raw_session)
        assert slot.metadata["numSessio"] == "23"
        assert slot.metadata["totalPers"] == 350

    def test_requested_seats_is_stored_on_slot(self):
        slot = _parse_test_slot(
            _make_session_dict(total_persons=350, num_persons_available=315),
            requested_seats=4,
        )
        assert slot.requested_seats == 4


# ---------------------------------------------------------------------------
# Status mapping tests
# ---------------------------------------------------------------------------


class TestAvailabilitySlotStatusMapping:
    """Tests verifying the status field for different capacity situations."""

    def test_status_is_sold_out_when_zero_seats_available(self):
        # nPers=0, percPers=0.0 → sold out
        raw_session = _make_session_dict(
            total_persons=350, num_persons_available=0, percent_available=0.0
        )
        slot = _parse_test_slot(raw_session)
        assert slot.status == SLOT_STATUS_SOLD_OUT

    def test_status_is_limited_when_7_percent_available(self):
        """7% available = 93% occupied, above the 90% occupied threshold → limited."""
        raw_session = _make_session_dict(
            total_persons=350, num_persons_available=25, percent_available=7.0
        )
        slot = _parse_test_slot(raw_session)
        assert slot.status == SLOT_STATUS_LIMITED

    def test_status_is_limited_when_5_percent_available(self):
        raw_session = _make_session_dict(
            total_persons=350, num_persons_available=18, percent_available=5.0
        )
        slot = _parse_test_slot(raw_session)
        assert slot.status == SLOT_STATUS_LIMITED

    def test_status_is_available_when_90_percent_available(self):
        # 90% available = 10% occupied, below the 90% occupied threshold → available
        raw_session = _make_session_dict(
            total_persons=350, num_persons_available=315, percent_available=90.0
        )
        slot = _parse_test_slot(raw_session)
        assert slot.status == SLOT_STATUS_AVAILABLE

    def test_status_is_unknown_when_total_persons_is_null(self):
        raw_session = {
            "numSessio": "24",
            "horaInici": "1730",
            "horaFi": "1800",
            "totalPers": None,
            "nPers": 0,
            "percPers": 0,
        }
        slot = _parse_test_slot(raw_session)
        assert slot.status == SLOT_STATUS_UNKNOWN


# ---------------------------------------------------------------------------
# has_availability flag tests
# ---------------------------------------------------------------------------


class TestHasAvailabilityFlag:
    """Tests for the has_availability flag under different num_people values."""

    def test_has_availability_true_when_single_seat_requested_and_available(self):
        raw_session = _make_session_dict(
            total_persons=350, num_persons_available=315, percent_available=90.0
        )
        slot = _parse_test_slot(raw_session, requested_seats=1)
        assert slot.has_availability is True

    def test_has_availability_false_when_zero_seats_remain(self):
        raw_session = _make_session_dict(
            total_persons=350, num_persons_available=0, percent_available=0.0
        )
        slot = _parse_test_slot(raw_session, requested_seats=1)
        assert slot.has_availability is False

    def test_has_availability_true_when_group_fits_exactly(self):
        # 6 seats available, group of 6 → fits exactly
        raw_session = _make_session_dict(
            total_persons=350, num_persons_available=6, percent_available=2.0
        )
        slot = _parse_test_slot(raw_session, requested_seats=6)
        assert slot.has_availability is True

    def test_has_availability_false_when_group_exceeds_remaining_seats(self):
        # 3 seats available, group of 4 → does not fit
        raw_session = _make_session_dict(
            total_persons=350, num_persons_available=3, percent_available=1.0
        )
        slot = _parse_test_slot(raw_session, requested_seats=4)
        assert slot.has_availability is False

    def test_has_availability_false_when_total_persons_is_null(self):
        raw_session = {
            "numSessio": "24",
            "horaInici": "1730",
            "horaFi": "1800",
            "totalPers": None,
            "nPers": 0,
            "percPers": 0,
        }
        slot = _parse_test_slot(raw_session, requested_seats=1)
        assert slot.has_availability is False


# ---------------------------------------------------------------------------
# SantPauProvider.get_availability integration-style unit tests (mocked HTTP)
# ---------------------------------------------------------------------------


class TestSantPauProviderGetAvailability:
    """Tests for SantPauProvider.get_availability() with mocked HTTP."""

    def _build_provider_with_mocked_client(
        self, mocked_http_client: MagicMock
    ) -> SantPauProvider:
        provider = SantPauProvider()
        provider._http_client = mocked_http_client
        return provider

    def test_returns_correct_number_of_slots(self):
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_HORARIS_API_RESPONSE
        mock_response.raise_for_status = MagicMock()

        mocked_http_client = MagicMock()
        mocked_http_client.post.return_value = mock_response

        provider = self._build_provider_with_mocked_client(mocked_http_client)
        availability_slots = provider.get_availability(
            venue_id=SANT_PAU_VENUE_ID,
            day=TEST_DATE_ISO,
            activity_id=TEST_ACTIVITY_ID,
        )

        expected_session_count = len(MOCK_HORARIS_API_RESPONSE[0]["sessions"])
        assert len(availability_slots) == expected_session_count

    def test_uses_default_activity_id_when_none_given(self):
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()

        mocked_http_client = MagicMock()
        mocked_http_client.post.return_value = mock_response

        provider = self._build_provider_with_mocked_client(mocked_http_client)
        provider.get_availability(
            venue_id=SANT_PAU_VENUE_ID,
            day=TEST_DATE_ISO,
            activity_id=None,
        )

        call_kwargs = mocked_http_client.post.call_args
        posted_data = call_kwargs[1]["data"]
        assert posted_data["codiActiv"] == "1"

    def test_sends_date_in_dd_mm_yyyy_format(self):
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()

        mocked_http_client = MagicMock()
        mocked_http_client.post.return_value = mock_response

        provider = self._build_provider_with_mocked_client(mocked_http_client)
        provider.get_availability(
            venue_id=SANT_PAU_VENUE_ID,
            day="2026-05-02",
            activity_id=TEST_ACTIVITY_ID,
        )

        call_kwargs = mocked_http_client.post.call_args
        posted_data = call_kwargs[1]["data"]
        assert posted_data["fecha"] == "02/05/2026"

    def test_sends_hora_as_0000(self):
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()

        mocked_http_client = MagicMock()
        mocked_http_client.post.return_value = mock_response

        provider = self._build_provider_with_mocked_client(mocked_http_client)
        provider.get_availability(
            venue_id=SANT_PAU_VENUE_ID,
            day=TEST_DATE_ISO,
            activity_id=TEST_ACTIVITY_ID,
        )

        call_kwargs = mocked_http_client.post.call_args
        posted_data = call_kwargs[1]["data"]
        assert posted_data["hora"] == "0000"

    def test_returns_empty_list_when_api_returns_empty_array(self):
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()

        mocked_http_client = MagicMock()
        mocked_http_client.post.return_value = mock_response

        provider = self._build_provider_with_mocked_client(mocked_http_client)
        availability_slots = provider.get_availability(
            venue_id=SANT_PAU_VENUE_ID,
            day=TEST_DATE_ISO,
            activity_id=TEST_ACTIVITY_ID,
        )

        assert availability_slots == []

    def test_slots_have_has_availability_set_based_on_num_people(self):
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_HORARIS_API_RESPONSE
        mock_response.raise_for_status = MagicMock()

        mocked_http_client = MagicMock()
        mocked_http_client.post.return_value = mock_response

        provider = self._build_provider_with_mocked_client(mocked_http_client)
        # Request 30 people — only the session with 315 seats free should fit
        availability_slots = provider.get_availability(
            venue_id=SANT_PAU_VENUE_ID,
            day=TEST_DATE_ISO,
            activity_id=TEST_ACTIVITY_ID,
            num_people=30,
        )

        slots_with_availability = [
            slot for slot in availability_slots if slot.has_availability
        ]
        # Only the "10% occupied" session has 315 seats, which fits 30 people
        assert len(slots_with_availability) == 1
        assert slots_with_availability[0].seats_available == 315

    def test_raises_value_error_for_unknown_venue_id(self):
        provider = SantPauProvider()
        provider._http_client = MagicMock()

        with pytest.raises(ValueError, match="sant_pau"):
            provider.get_availability(
                venue_id="unknown_venue",
                day=TEST_DATE_ISO,
            )
