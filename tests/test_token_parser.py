import pytest

from core.token_parser import extract_token
from tests.fixtures.sample_urls import (
    URL_EMPTY,
    URL_GARBAGE,
    URL_NO_TOKEN,
    VALID_TOKEN,
    VALID_URL_FULL,
    VALID_URL_NO_DATA,
)


class TestExtractToken:
    def test_valid_url_with_data(self):
        token = extract_token(VALID_URL_FULL)
        assert token == VALID_TOKEN

    def test_valid_url_without_data(self):
        """Token at end of URL with no &data= following."""
        token = extract_token(VALID_URL_NO_DATA)
        assert token == VALID_TOKEN

    def test_url_without_token_param(self):
        with pytest.raises(ValueError, match="URL inválida"):
            extract_token(URL_NO_TOKEN)

    def test_empty_url(self):
        with pytest.raises(ValueError, match="URL inválida"):
            extract_token(URL_EMPTY)

    def test_garbage_url(self):
        with pytest.raises(ValueError, match="URL inválida"):
            extract_token(URL_GARBAGE)

    def test_whitespace_url(self):
        with pytest.raises(ValueError, match="URL inválida"):
            extract_token("   ")

    def test_url_with_leading_trailing_whitespace(self):
        url = f"  {VALID_URL_FULL}  "
        token = extract_token(url)
        assert token == VALID_TOKEN

    def test_token_empty_after_equals(self):
        url = (
            "https://realtime.webwork-tracker.com/api/monitoring/"
            "daily-activity/download-excel/xlsx?token=&data={}"
        )
        with pytest.raises(ValueError, match="URL inválida"):
            extract_token(url)
