from datetime import date
from unittest.mock import patch

import pytest

from core.date_utils import generate_date_range, parse_date_br, validate_dates


class TestParseDateBr:
    def test_valid_date(self):
        assert parse_date_br("15/03/2026") == date(2026, 3, 15)

    def test_single_digit_day_month(self):
        assert parse_date_br("1/1/2026") == date(2026, 1, 1)

    def test_invalid_format(self):
        with pytest.raises(ValueError):
            parse_date_br("2026-03-15")

    def test_invalid_day(self):
        with pytest.raises(ValueError):
            parse_date_br("32/01/2026")

    def test_empty_string(self):
        with pytest.raises(ValueError):
            parse_date_br("")


class TestGenerateDateRange:
    def test_same_day(self):
        d = date(2026, 3, 15)
        assert generate_date_range(d, d) == [d]

    def test_within_month(self):
        start = date(2026, 3, 1)
        end = date(2026, 3, 5)
        result = generate_date_range(start, end)
        assert len(result) == 5
        assert result[0] == start
        assert result[-1] == end

    def test_cross_month(self):
        start = date(2026, 2, 28)
        end = date(2026, 3, 3)
        result = generate_date_range(start, end)
        expected = [
            date(2026, 2, 28),
            date(2026, 3, 1),
            date(2026, 3, 2),
            date(2026, 3, 3),
        ]
        assert result == expected

    def test_cross_year(self):
        start = date(2025, 12, 30)
        end = date(2026, 1, 2)
        result = generate_date_range(start, end)
        assert len(result) == 4
        assert result[0] == date(2025, 12, 30)
        assert result[-1] == date(2026, 1, 2)

    def test_start_after_end(self):
        with pytest.raises(ValueError, match="posterior"):
            generate_date_range(date(2026, 3, 15), date(2026, 3, 1))


class TestValidateDates:
    @patch("core.date_utils.date")
    def test_valid_range(self, mock_date):
        mock_date.today.return_value = date(2026, 3, 30)
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)
        _, result = validate_dates("01/03/2026", "05/03/2026")
        assert len(result.dates) == 5
        assert result.truncated is False
        assert result.truncated_to is None

    @patch("core.date_utils.date")
    def test_both_dates_future_rejected(self, mock_date):
        mock_date.today.return_value = date(2026, 3, 15)
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)
        with pytest.raises(ValueError, match="apenas datas futuras"):
            validate_dates("01/05/2026", "31/05/2026")

    @patch("core.date_utils.date")
    def test_future_end_date_truncated(self, mock_date):
        mock_date.today.return_value = date(2026, 3, 30)
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)
        _, result = validate_dates("01/03/2026", "15/04/2026")
        assert result.truncated is True
        assert result.truncated_to == date(2026, 3, 30)
        assert result.dates[-1] == date(2026, 3, 30)
        assert len(result.dates) == 30  # March 1-30

    @patch("core.date_utils.date")
    def test_end_date_equals_today_not_truncated(self, mock_date):
        mock_date.today.return_value = date(2026, 3, 30)
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)
        _, result = validate_dates("01/03/2026", "30/03/2026")
        assert result.truncated is False

    @patch("core.date_utils.date")
    def test_start_after_end_rejected(self, mock_date):
        mock_date.today.return_value = date(2026, 3, 30)
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)
        with pytest.raises(ValueError, match="posterior"):
            validate_dates("15/03/2026", "01/03/2026")

    @patch("core.date_utils.date")
    def test_single_future_start_and_end(self, mock_date):
        """Both start and end in the future (same day)."""
        mock_date.today.return_value = date(2026, 3, 15)
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)
        with pytest.raises(ValueError, match="apenas datas futuras"):
            validate_dates("20/03/2026", "20/03/2026")
