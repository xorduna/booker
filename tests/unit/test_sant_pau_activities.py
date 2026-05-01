"""
Unit tests for Sant Pau activity parsing.

Covers:
- Correct mapping of raw API fields to Activity dataclass
- Whitespace stripping on activity names
- Handling of combo activities (non-numeric IDs like "0-8")
- Fallback behaviour when the API call fails
"""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from tests.fixtures import MOCK_ACTIVITIES_API_RESPONSE
from ticket_providers.sant_pau import (
    SANT_PAU_FALLBACK_ACTIVITY_ID,
    SANT_PAU_FALLBACK_ACTIVITY_NAME,
    SANT_PAU_VENUE_ID,
    SantPauProvider,
    parse_activity_from_raw_dict,
)
from ticket_providers.models import Activity


# ---------------------------------------------------------------------------
# parse_activity_from_raw_dict unit tests
# ---------------------------------------------------------------------------


class TestParseActivityFromRawDict:
    """Tests for the parse_activity_from_raw_dict helper."""

    def test_maps_codi_to_id(self):
        raw_activity_data = {"codi": "1", "desc": "Visita Lliure "}
        parsed_activity = parse_activity_from_raw_dict(
            raw_activity_dict=raw_activity_data,
            venue_id=SANT_PAU_VENUE_ID,
        )
        assert parsed_activity.id == "1"

    def test_strips_trailing_whitespace_from_description(self):
        raw_activity_data = {"codi": "1", "desc": "Visita Lliure "}
        parsed_activity = parse_activity_from_raw_dict(
            raw_activity_dict=raw_activity_data,
            venue_id=SANT_PAU_VENUE_ID,
        )
        assert parsed_activity.name == "Visita Lliure"

    def test_strips_leading_whitespace_from_description(self):
        raw_activity_data = {"codi": "112", "desc": " La Nit dels Museus 2026"}
        parsed_activity = parse_activity_from_raw_dict(
            raw_activity_dict=raw_activity_data,
            venue_id=SANT_PAU_VENUE_ID,
        )
        assert parsed_activity.name == "La Nit dels Museus 2026"

    def test_sets_correct_venue_id(self):
        raw_activity_data = {"codi": "2", "desc": "Visita Guiada"}
        parsed_activity = parse_activity_from_raw_dict(
            raw_activity_dict=raw_activity_data,
            venue_id=SANT_PAU_VENUE_ID,
        )
        assert parsed_activity.venue_id == SANT_PAU_VENUE_ID

    def test_preserves_raw_dict_in_metadata(self):
        raw_activity_data = {
            "codi": "42",
            "desc": "Pack Infantil ",
            "preu": "50.00",
        }
        parsed_activity = parse_activity_from_raw_dict(
            raw_activity_dict=raw_activity_data,
            venue_id=SANT_PAU_VENUE_ID,
        )
        assert parsed_activity.metadata["preu"] == "50.00"
        assert parsed_activity.metadata["codi"] == "42"

    def test_handles_combo_activity_with_hyphenated_id(self):
        """Activity ID "0-8" is a real value returned by the Sant Pau API for
        combo (COMBI) activities.  It must be preserved as a string."""
        raw_activity_data = {
            "codi": "0-8",
            "desc": "Visita Lliure  amb audioguia interactiva",
            "tipus": "COMBI",
        }
        parsed_activity = parse_activity_from_raw_dict(
            raw_activity_dict=raw_activity_data,
            venue_id=SANT_PAU_VENUE_ID,
        )
        assert parsed_activity.id == "0-8"

    def test_handles_missing_desc_field_gracefully(self):
        raw_activity_data = {"codi": "5"}
        parsed_activity = parse_activity_from_raw_dict(
            raw_activity_dict=raw_activity_data,
            venue_id=SANT_PAU_VENUE_ID,
        )
        assert parsed_activity.name == ""


# ---------------------------------------------------------------------------
# SantPauProvider.get_activities integration-style unit tests (mocked HTTP)
# ---------------------------------------------------------------------------


class TestSantPauProviderGetActivities:
    """Tests for SantPauProvider.get_activities() with mocked HTTP."""

    def _build_provider_with_mocked_client(
        self, mocked_http_client: MagicMock
    ) -> SantPauProvider:
        """Helper: create a SantPauProvider whose _http_client is replaced
        with the supplied mock so we never hit the real network."""
        provider = SantPauProvider()
        provider._http_client = mocked_http_client
        return provider

    def test_returns_correct_number_of_activities(self):
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_ACTIVITIES_API_RESPONSE
        mock_response.raise_for_status = MagicMock()

        mocked_http_client = MagicMock()
        mocked_http_client.post.return_value = mock_response

        provider = self._build_provider_with_mocked_client(mocked_http_client)
        activities = provider.get_activities(SANT_PAU_VENUE_ID)

        assert len(activities) == len(MOCK_ACTIVITIES_API_RESPONSE)

    def test_first_activity_has_correct_id_and_name(self):
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_ACTIVITIES_API_RESPONSE
        mock_response.raise_for_status = MagicMock()

        mocked_http_client = MagicMock()
        mocked_http_client.post.return_value = mock_response

        provider = self._build_provider_with_mocked_client(mocked_http_client)
        activities = provider.get_activities(SANT_PAU_VENUE_ID)

        first_activity = activities[0]
        assert first_activity.id == "1"
        assert first_activity.name == "Visita Lliure"

    def test_all_activities_have_correct_venue_id(self):
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_ACTIVITIES_API_RESPONSE
        mock_response.raise_for_status = MagicMock()

        mocked_http_client = MagicMock()
        mocked_http_client.post.return_value = mock_response

        provider = self._build_provider_with_mocked_client(mocked_http_client)
        activities = provider.get_activities(SANT_PAU_VENUE_ID)

        for activity in activities:
            assert activity.venue_id == SANT_PAU_VENUE_ID

    def test_falls_back_to_default_activity_when_http_error_occurs(self):
        mocked_http_client = MagicMock()
        mocked_http_client.post.side_effect = httpx.ConnectError("timeout")

        provider = self._build_provider_with_mocked_client(mocked_http_client)
        fallback_activities = provider.get_activities(SANT_PAU_VENUE_ID)

        assert len(fallback_activities) == 1
        assert fallback_activities[0].id == SANT_PAU_FALLBACK_ACTIVITY_ID
        assert fallback_activities[0].name == SANT_PAU_FALLBACK_ACTIVITY_NAME

    def test_falls_back_to_default_activity_when_api_returns_invalid_json(self):
        mock_response = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError("bad json", "", 0)
        mock_response.raise_for_status = MagicMock()

        mocked_http_client = MagicMock()
        mocked_http_client.post.return_value = mock_response

        provider = self._build_provider_with_mocked_client(mocked_http_client)
        fallback_activities = provider.get_activities(SANT_PAU_VENUE_ID)

        assert len(fallback_activities) == 1
        assert fallback_activities[0].metadata.get("fallback") is True

    def test_falls_back_to_default_activity_when_api_returns_non_list(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"error": "invalid"}
        mock_response.raise_for_status = MagicMock()

        mocked_http_client = MagicMock()
        mocked_http_client.post.return_value = mock_response

        provider = self._build_provider_with_mocked_client(mocked_http_client)
        fallback_activities = provider.get_activities(SANT_PAU_VENUE_ID)

        assert len(fallback_activities) == 1
        assert fallback_activities[0].id == SANT_PAU_FALLBACK_ACTIVITY_ID

    def test_raises_value_error_for_unknown_venue_id(self):
        provider = SantPauProvider()
        provider._http_client = MagicMock()

        with pytest.raises(ValueError, match="sant_pau"):
            provider.get_activities("unknown_venue")
