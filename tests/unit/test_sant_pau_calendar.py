"""
Unit tests for Sant Pau calendar parsing.

Covers:
- Correct mapping of raw calendar day fields to CalendarDay
- is_available flag (True for "EST", False for "senseLloc")
- is_free_admission_day flag (True when portesObertes == "S")
- day_type field preservation
- SantPauProvider.get_calendar() with mocked HTTP
"""

from unittest.mock import MagicMock

import pytest

from tests.fixtures import MOCK_CALENDAR_API_RESPONSE
from ticket_providers.sant_pau import (
    SANT_PAU_FALLBACK_ACTIVITY_ID,
    SANT_PAU_VENUE_ID,
    SantPauProvider,
    parse_calendar_day_from_raw_dict,
)


# ---------------------------------------------------------------------------
# parse_calendar_day_from_raw_dict unit tests
# ---------------------------------------------------------------------------


class TestParseCalendarDayFromRawDict:
    """Tests for the parse_calendar_day_from_raw_dict helper."""

    def test_maps_fecha_to_date(self):
        raw_day_data = {
            "fecha": "2026-05-02",
            "tipus": "EST",
            "portesObertes": "N",
            "comentariCal": [],
        }
        parsed_day = parse_calendar_day_from_raw_dict(
            raw_calendar_day_dict=raw_day_data,
            venue_id=SANT_PAU_VENUE_ID,
            activity_id="1",
        )
        assert parsed_day.date == "2026-05-02"

    def test_standard_day_has_is_available_true(self):
        raw_day_data = {
            "fecha": "2026-05-02",
            "tipus": "EST",
            "portesObertes": "N",
            "comentariCal": [],
        }
        parsed_day = parse_calendar_day_from_raw_dict(
            raw_calendar_day_dict=raw_day_data,
            venue_id=SANT_PAU_VENUE_ID,
            activity_id="1",
        )
        assert parsed_day.is_available is True

    def test_sense_lloc_day_has_is_available_false(self):
        """A 'senseLloc' day means no availability (sold out or closed)."""
        raw_day_data = {
            "fecha": "2026-05-27",
            "tipus": "senseLloc",
            "portesObertes": "N",
            "comentariCal": [],
        }
        parsed_day = parse_calendar_day_from_raw_dict(
            raw_calendar_day_dict=raw_day_data,
            venue_id=SANT_PAU_VENUE_ID,
            activity_id="1",
        )
        assert parsed_day.is_available is False

    def test_portes_obertes_s_sets_is_free_admission_day_true(self):
        """portesObertes='S' means a free-entry (open-doors) day."""
        raw_day_data = {
            "fecha": "2026-05-03",
            "tipus": "EST",
            "portesObertes": "S",
            "comentariCal": [],
        }
        parsed_day = parse_calendar_day_from_raw_dict(
            raw_calendar_day_dict=raw_day_data,
            venue_id=SANT_PAU_VENUE_ID,
            activity_id="1",
        )
        assert parsed_day.is_free_admission_day is True

    def test_portes_obertes_n_sets_is_free_admission_day_false(self):
        raw_day_data = {
            "fecha": "2026-05-02",
            "tipus": "EST",
            "portesObertes": "N",
            "comentariCal": [],
        }
        parsed_day = parse_calendar_day_from_raw_dict(
            raw_calendar_day_dict=raw_day_data,
            venue_id=SANT_PAU_VENUE_ID,
            activity_id="1",
        )
        assert parsed_day.is_free_admission_day is False

    def test_day_type_preserves_raw_tipus(self):
        raw_day_data = {
            "fecha": "2026-05-27",
            "tipus": "senseLloc",
            "portesObertes": "N",
            "comentariCal": [],
        }
        parsed_day = parse_calendar_day_from_raw_dict(
            raw_calendar_day_dict=raw_day_data,
            venue_id=SANT_PAU_VENUE_ID,
            activity_id="1",
        )
        assert parsed_day.day_type == "senseLloc"

    def test_raw_dict_is_preserved_in_metadata(self):
        raw_day_data = {
            "fecha": "2026-05-03",
            "tipus": "EST",
            "portesObertes": "S",
            "comentariCal": [],
        }
        parsed_day = parse_calendar_day_from_raw_dict(
            raw_calendar_day_dict=raw_day_data,
            venue_id=SANT_PAU_VENUE_ID,
            activity_id="1",
        )
        assert parsed_day.metadata["portesObertes"] == "S"
        assert parsed_day.metadata["tipus"] == "EST"

    def test_venue_id_is_set_correctly(self):
        raw_day_data = {
            "fecha": "2026-05-02",
            "tipus": "EST",
            "portesObertes": "N",
            "comentariCal": [],
        }
        parsed_day = parse_calendar_day_from_raw_dict(
            raw_calendar_day_dict=raw_day_data,
            venue_id=SANT_PAU_VENUE_ID,
            activity_id="1",
        )
        assert parsed_day.venue_id == SANT_PAU_VENUE_ID

    def test_activity_id_is_set_correctly(self):
        raw_day_data = {
            "fecha": "2026-05-02",
            "tipus": "EST",
            "portesObertes": "N",
            "comentariCal": [],
        }
        parsed_day = parse_calendar_day_from_raw_dict(
            raw_calendar_day_dict=raw_day_data,
            venue_id=SANT_PAU_VENUE_ID,
            activity_id="2",
        )
        assert parsed_day.activity_id == "2"


# ---------------------------------------------------------------------------
# SantPauProvider.get_calendar integration-style unit tests (mocked HTTP)
# ---------------------------------------------------------------------------


class TestSantPauProviderGetCalendar:
    """Tests for SantPauProvider.get_calendar() with mocked HTTP."""

    def _build_provider_with_mocked_client(
        self, mocked_http_client: MagicMock
    ) -> SantPauProvider:
        provider = SantPauProvider()
        provider._http_client = mocked_http_client
        return provider

    def test_returns_correct_number_of_calendar_days(self):
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_CALENDAR_API_RESPONSE
        mock_response.raise_for_status = MagicMock()

        mocked_http_client = MagicMock()
        mocked_http_client.post.return_value = mock_response

        provider = self._build_provider_with_mocked_client(mocked_http_client)
        calendar_days = provider.get_calendar(
            venue_id=SANT_PAU_VENUE_ID,
            from_date="2026-05-01",
            to_date="2026-05-29",
            activity_id="1",
        )

        assert len(calendar_days) == len(MOCK_CALENDAR_API_RESPONSE)

    def test_sense_lloc_days_have_is_available_false(self):
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_CALENDAR_API_RESPONSE
        mock_response.raise_for_status = MagicMock()

        mocked_http_client = MagicMock()
        mocked_http_client.post.return_value = mock_response

        provider = self._build_provider_with_mocked_client(mocked_http_client)
        calendar_days = provider.get_calendar(
            venue_id=SANT_PAU_VENUE_ID,
            from_date="2026-05-01",
            to_date="2026-05-29",
        )

        unavailable_days = [day for day in calendar_days if not day.is_available]
        # Fixture has 2 senseLloc days (May 27 and May 28)
        assert len(unavailable_days) == 2

    def test_free_admission_day_is_detected(self):
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_CALENDAR_API_RESPONSE
        mock_response.raise_for_status = MagicMock()

        mocked_http_client = MagicMock()
        mocked_http_client.post.return_value = mock_response

        provider = self._build_provider_with_mocked_client(mocked_http_client)
        calendar_days = provider.get_calendar(
            venue_id=SANT_PAU_VENUE_ID,
            from_date="2026-05-01",
            to_date="2026-05-29",
        )

        free_days = [day for day in calendar_days if day.is_free_admission_day]
        # Fixture has 1 portesObertes="S" day (May 3)
        assert len(free_days) == 1
        assert free_days[0].date == "2026-05-03"

    def test_sends_from_date_in_dd_mm_yyyy_format(self):
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()

        mocked_http_client = MagicMock()
        mocked_http_client.post.return_value = mock_response

        provider = self._build_provider_with_mocked_client(mocked_http_client)
        provider.get_calendar(
            venue_id=SANT_PAU_VENUE_ID,
            from_date="2026-05-01",
            to_date="2026-05-31",
            activity_id="1",
        )

        call_kwargs = mocked_http_client.post.call_args
        posted_data = call_kwargs[1]["data"]
        assert posted_data["fI"] == "01/05/2026"
        assert posted_data["fF"] == "31/05/2026"

    def test_uses_fallback_activity_id_when_none_given(self):
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()

        mocked_http_client = MagicMock()
        mocked_http_client.post.return_value = mock_response

        provider = self._build_provider_with_mocked_client(mocked_http_client)
        provider.get_calendar(
            venue_id=SANT_PAU_VENUE_ID,
            from_date="2026-05-01",
            to_date="2026-05-31",
            activity_id=None,
        )

        call_kwargs = mocked_http_client.post.call_args
        posted_data = call_kwargs[1]["data"]
        assert posted_data["cActivitats"] == SANT_PAU_FALLBACK_ACTIVITY_ID

    def test_raises_value_error_for_unknown_venue_id(self):
        provider = SantPauProvider()
        provider._http_client = MagicMock()

        with pytest.raises(ValueError, match="sant_pau"):
            provider.get_calendar(
                venue_id="other_venue",
                from_date="2026-05-01",
                to_date="2026-05-31",
            )
