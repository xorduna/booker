"""
Unit tests for date/time conversion helpers and availability status logic.

These tests cover:
- ISO date → DD/MM/YYYY conversion for the Sant Pau API
- 4-digit time string → HH:MM conversion
- compute_availability_status() for all status branches
"""

import pytest

from ticket_providers.sant_pau import (
    SANT_PAU_LIMITED_THRESHOLD_PERCENT_OCCUPIED,
    compute_availability_status,
    convert_four_digit_time_to_hh_mm,
    convert_iso_date_to_sant_pau_format,
)
from ticket_providers.models import (
    SLOT_STATUS_AVAILABLE,
    SLOT_STATUS_LIMITED,
    SLOT_STATUS_SOLD_OUT,
    SLOT_STATUS_UNKNOWN,
)


# ---------------------------------------------------------------------------
# Date conversion tests
# ---------------------------------------------------------------------------


class TestConvertIsoDateToSantPauFormat:
    """Tests for convert_iso_date_to_sant_pau_format()."""

    def test_converts_standard_date_correctly(self):
        result = convert_iso_date_to_sant_pau_format("2026-05-02")
        assert result == "02/05/2026"

    def test_converts_date_with_leading_zero_in_day(self):
        result = convert_iso_date_to_sant_pau_format("2026-05-09")
        assert result == "09/05/2026"

    def test_converts_december_date_correctly(self):
        result = convert_iso_date_to_sant_pau_format("2026-12-31")
        assert result == "31/12/2026"

    def test_converts_january_first(self):
        result = convert_iso_date_to_sant_pau_format("2027-01-01")
        assert result == "01/01/2027"

    def test_raises_value_error_for_invalid_date_string(self):
        with pytest.raises(ValueError):
            convert_iso_date_to_sant_pau_format("not-a-date")

    def test_raises_value_error_for_wrong_format(self):
        # DD/MM/YYYY input should fail since we expect YYYY-MM-DD
        with pytest.raises(ValueError):
            convert_iso_date_to_sant_pau_format("02/05/2026")

    def test_output_uses_forward_slashes_not_dashes(self):
        """The Sant Pau horaris endpoint requires '/' separators; dashes
        cause it to silently return an empty list."""
        result = convert_iso_date_to_sant_pau_format("2026-06-15")
        assert "/" in result
        assert "-" not in result


# ---------------------------------------------------------------------------
# Time conversion tests
# ---------------------------------------------------------------------------


class TestConvertFourDigitTimeToHhMm:
    """Tests for convert_four_digit_time_to_hh_mm()."""

    def test_converts_morning_time(self):
        result = convert_four_digit_time_to_hh_mm("0930")
        assert result == "09:30"

    def test_converts_afternoon_time(self):
        result = convert_four_digit_time_to_hh_mm("1130")
        assert result == "11:30"

    def test_converts_hour_on_the_hour(self):
        result = convert_four_digit_time_to_hh_mm("1000")
        assert result == "10:00"

    def test_converts_midnight(self):
        result = convert_four_digit_time_to_hh_mm("0000")
        assert result == "00:00"

    def test_converts_end_of_day(self):
        result = convert_four_digit_time_to_hh_mm("2359")
        assert result == "23:59"

    def test_converts_late_afternoon(self):
        result = convert_four_digit_time_to_hh_mm("1730")
        assert result == "17:30"

    def test_raises_value_error_for_string_shorter_than_four_chars(self):
        with pytest.raises(ValueError):
            convert_four_digit_time_to_hh_mm("930")

    def test_raises_value_error_for_string_longer_than_four_chars(self):
        with pytest.raises(ValueError):
            convert_four_digit_time_to_hh_mm("09300")

    def test_raises_value_error_for_empty_string(self):
        with pytest.raises(ValueError):
            convert_four_digit_time_to_hh_mm("")


# ---------------------------------------------------------------------------
# Availability status computation tests
# ---------------------------------------------------------------------------


class TestComputeAvailabilityStatus:
    """Tests for compute_availability_status()."""

    def test_returns_unknown_when_seats_available_is_none(self):
        result = compute_availability_status(
            seats_available=None,
            percent_occupied=None,
        )
        assert result == SLOT_STATUS_UNKNOWN

    def test_returns_unknown_when_seats_available_is_none_even_with_percent(self):
        result = compute_availability_status(
            seats_available=None,
            percent_occupied=50.0,
        )
        assert result == SLOT_STATUS_UNKNOWN

    def test_returns_sold_out_when_seats_available_is_zero(self):
        result = compute_availability_status(
            seats_available=0,
            percent_occupied=100.0,
        )
        assert result == SLOT_STATUS_SOLD_OUT

    def test_returns_sold_out_when_seats_available_is_negative(self):
        """Negative values should not occur but are treated as sold out."""
        result = compute_availability_status(
            seats_available=-1,
            percent_occupied=100.0,
        )
        assert result == SLOT_STATUS_SOLD_OUT

    def test_returns_limited_at_threshold_boundary(self):
        result = compute_availability_status(
            seats_available=5,
            percent_occupied=SANT_PAU_LIMITED_THRESHOLD_PERCENT_OCCUPIED,
        )
        assert result == SLOT_STATUS_LIMITED

    def test_returns_limited_above_threshold(self):
        result = compute_availability_status(
            seats_available=10,
            percent_occupied=95.0,
        )
        assert result == SLOT_STATUS_LIMITED

    def test_returns_limited_for_93_percent_occupied(self):
        """Real-world value observed in HAR: 93% occupied, 25 seats free."""
        result = compute_availability_status(
            seats_available=25,
            percent_occupied=93.0,
        )
        assert result == SLOT_STATUS_LIMITED

    def test_returns_available_below_threshold(self):
        result = compute_availability_status(
            seats_available=315,
            percent_occupied=10.0,
        )
        assert result == SLOT_STATUS_AVAILABLE

    def test_returns_available_when_percent_occupied_is_none_but_seats_exist(self):
        """If the provider omits percPers but totalPers/nPers are present,
        we fall back to available status when seats exist."""
        result = compute_availability_status(
            seats_available=50,
            percent_occupied=None,
        )
        assert result == SLOT_STATUS_AVAILABLE

    def test_custom_limited_threshold_is_respected(self):
        """The threshold can be customised; verify boundary conditions."""
        result_just_below = compute_availability_status(
            seats_available=100,
            percent_occupied=79.9,
            limited_threshold_percent_occupied=80.0,
        )
        result_at_threshold = compute_availability_status(
            seats_available=100,
            percent_occupied=80.0,
            limited_threshold_percent_occupied=80.0,
        )
        assert result_just_below == SLOT_STATUS_AVAILABLE
        assert result_at_threshold == SLOT_STATUS_LIMITED
