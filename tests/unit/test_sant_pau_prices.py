"""
Unit tests for Sant Pau price tier parsing and get_prices provider method.

Covers:
- parse_price_tier_from_raw_dict: field mapping, boolean flags, min/max persons
- convert_hh_mm_time_to_four_digit: time format conversion
- SantPauProvider.get_prices: request params, response parsing, empty response
"""

from unittest.mock import MagicMock

import pytest

from tests.fixtures import MOCK_TARIFES_API_RESPONSE
from ticket_providers.sant_pau import (
    SANT_PAU_VENUE_ID,
    SantPauProvider,
    convert_hh_mm_time_to_four_digit,
    parse_price_tier_from_raw_dict,
)


# ---------------------------------------------------------------------------
# convert_hh_mm_time_to_four_digit tests
# ---------------------------------------------------------------------------


class TestConvertHhMmTimeToFourDigit:
    """Tests for the HH:MM → 4-digit conversion helper."""

    def test_converts_standard_morning_time(self):
        result = convert_hh_mm_time_to_four_digit("09:30")
        assert result == "0930"

    def test_converts_noon(self):
        result = convert_hh_mm_time_to_four_digit("12:00")
        assert result == "1200"

    def test_converts_late_afternoon(self):
        result = convert_hh_mm_time_to_four_digit("17:30")
        assert result == "1730"

    def test_raises_value_error_for_invalid_format(self):
        with pytest.raises(ValueError):
            convert_hh_mm_time_to_four_digit("930")

    def test_raises_value_error_for_missing_colon(self):
        with pytest.raises(ValueError):
            convert_hh_mm_time_to_four_digit("0930")

    def test_roundtrip_with_four_digit_to_hh_mm(self):
        from ticket_providers.sant_pau import convert_four_digit_time_to_hh_mm
        original = "14:00"
        assert convert_four_digit_time_to_hh_mm(
            convert_hh_mm_time_to_four_digit(original)
        ) == original


# ---------------------------------------------------------------------------
# parse_price_tier_from_raw_dict tests
# ---------------------------------------------------------------------------


class TestParsePriceTierFromRawDict:
    """Tests for the parse_price_tier_from_raw_dict helper."""

    def _general_tier(self):
        return MOCK_TARIFES_API_RESPONSE[0]  # General, 18.00€

    def _membership_tier(self):
        return MOCK_TARIFES_API_RESPONSE[1]  # Amics del Recinte (amic=S)

    def _with_persons_limits(self):
        return MOCK_TARIFES_API_RESPONSE[2]  # Menors 12 anys (minPers=1, maxPers=4)

    def _free_admission_day_only(self):
        return MOCK_TARIFES_API_RESPONSE[3]  # portesObertes=S

    def test_maps_id_as_string(self):
        tier = parse_price_tier_from_raw_dict(self._general_tier())
        assert tier.id == "1"

    def test_maps_name_stripped(self):
        tier = parse_price_tier_from_raw_dict(self._general_tier())
        assert tier.name == "General"

    def test_maps_description(self):
        tier = parse_price_tier_from_raw_dict(self._membership_tier())
        assert "Amic Veí" in tier.description

    def test_maps_price_eur(self):
        tier = parse_price_tier_from_raw_dict(self._general_tier())
        assert tier.price_eur == "18.00"

    def test_maps_original_price_eur(self):
        tier = parse_price_tier_from_raw_dict(self._general_tier())
        assert tier.original_price_eur == "17.00"

    def test_is_membership_card_required_false_for_general(self):
        tier = parse_price_tier_from_raw_dict(self._general_tier())
        assert tier.is_membership_card_required is False

    def test_is_membership_card_required_true_for_amic(self):
        tier = parse_price_tier_from_raw_dict(self._membership_tier())
        assert tier.is_membership_card_required is True

    def test_is_free_admission_day_only_false_for_general(self):
        tier = parse_price_tier_from_raw_dict(self._general_tier())
        assert tier.is_free_admission_day_only is False

    def test_is_free_admission_day_only_true_when_portes_obertes(self):
        tier = parse_price_tier_from_raw_dict(self._free_admission_day_only())
        assert tier.is_free_admission_day_only is True

    def test_min_persons_is_none_when_not_set(self):
        tier = parse_price_tier_from_raw_dict(self._general_tier())
        assert tier.min_persons is None

    def test_max_persons_is_none_when_not_set(self):
        tier = parse_price_tier_from_raw_dict(self._general_tier())
        assert tier.max_persons is None

    def test_min_persons_mapped_correctly(self):
        tier = parse_price_tier_from_raw_dict(self._with_persons_limits())
        assert tier.min_persons == 1

    def test_max_persons_mapped_correctly(self):
        tier = parse_price_tier_from_raw_dict(self._with_persons_limits())
        assert tier.max_persons == 4

    def test_raw_dict_stored_in_metadata(self):
        raw = self._general_tier()
        tier = parse_price_tier_from_raw_dict(raw)
        assert tier.metadata["codi"] == raw["codi"]
        assert tier.metadata["preu"] == raw["preu"]


# ---------------------------------------------------------------------------
# SantPauProvider.get_prices mocked HTTP tests
# ---------------------------------------------------------------------------


class TestSantPauProviderGetPrices:
    """Tests for SantPauProvider.get_prices() with mocked HTTP."""

    def _build_provider_with_mocked_client(
        self, mocked_http_client: MagicMock
    ) -> SantPauProvider:
        provider = SantPauProvider()
        provider._http_client = mocked_http_client
        return provider

    def _make_mock_response(self, json_data):
        mock_response = MagicMock()
        mock_response.json.return_value = json_data
        mock_response.raise_for_status = MagicMock()
        return mock_response

    def test_returns_correct_number_of_price_tiers(self):
        mocked_http_client = MagicMock()
        mocked_http_client.post.return_value = self._make_mock_response(
            MOCK_TARIFES_API_RESPONSE
        )
        provider = self._build_provider_with_mocked_client(mocked_http_client)
        price_tiers = provider.get_prices(
            venue_id=SANT_PAU_VENUE_ID,
            day="2026-05-16",
            start_time="11:00",
            activity_id="1",
        )
        assert len(price_tiers) == len(MOCK_TARIFES_API_RESPONSE)

    def test_sends_fecha_in_dd_mm_yyyy_format(self):
        mocked_http_client = MagicMock()
        mocked_http_client.post.return_value = self._make_mock_response([])
        provider = self._build_provider_with_mocked_client(mocked_http_client)
        provider.get_prices(
            venue_id=SANT_PAU_VENUE_ID,
            day="2026-05-16",
            start_time="11:00",
        )
        posted_data = mocked_http_client.post.call_args[1]["data"]
        assert posted_data["fecha"] == "16/05/2026"

    def test_sends_hora_as_four_digit_string(self):
        mocked_http_client = MagicMock()
        mocked_http_client.post.return_value = self._make_mock_response([])
        provider = self._build_provider_with_mocked_client(mocked_http_client)
        provider.get_prices(
            venue_id=SANT_PAU_VENUE_ID,
            day="2026-05-16",
            start_time="09:30",
        )
        posted_data = mocked_http_client.post.call_args[1]["data"]
        assert posted_data["hora"] == "0930"

    def test_sends_elem_as_get_tarifes(self):
        mocked_http_client = MagicMock()
        mocked_http_client.post.return_value = self._make_mock_response([])
        provider = self._build_provider_with_mocked_client(mocked_http_client)
        provider.get_prices(
            venue_id=SANT_PAU_VENUE_ID,
            day="2026-05-16",
            start_time="11:00",
        )
        posted_data = mocked_http_client.post.call_args[1]["data"]
        assert posted_data["elem"] == "getTarifes"

    def test_uses_default_activity_id_when_none_given(self):
        mocked_http_client = MagicMock()
        mocked_http_client.post.return_value = self._make_mock_response([])
        provider = self._build_provider_with_mocked_client(mocked_http_client)
        provider.get_prices(
            venue_id=SANT_PAU_VENUE_ID,
            day="2026-05-16",
            start_time="11:00",
            activity_id=None,
        )
        posted_data = mocked_http_client.post.call_args[1]["data"]
        assert posted_data["cActivitats"] == "1"

    def test_returns_empty_list_when_api_returns_empty_array(self):
        mocked_http_client = MagicMock()
        mocked_http_client.post.return_value = self._make_mock_response([])
        provider = self._build_provider_with_mocked_client(mocked_http_client)
        result = provider.get_prices(
            venue_id=SANT_PAU_VENUE_ID,
            day="2026-05-16",
            start_time="11:00",
        )
        assert result == []

    def test_raises_value_error_for_wrong_venue_id(self):
        provider = SantPauProvider()
        with pytest.raises(ValueError, match="sant_pau"):
            provider.get_prices(
                venue_id="wrong_venue",
                day="2026-05-16",
                start_time="11:00",
            )

    def test_first_price_tier_is_general(self):
        mocked_http_client = MagicMock()
        mocked_http_client.post.return_value = self._make_mock_response(
            MOCK_TARIFES_API_RESPONSE
        )
        provider = self._build_provider_with_mocked_client(mocked_http_client)
        price_tiers = provider.get_prices(
            venue_id=SANT_PAU_VENUE_ID,
            day="2026-05-16",
            start_time="11:00",
        )
        assert price_tiers[0].name == "General"
        assert price_tiers[0].price_eur == "18.00"
