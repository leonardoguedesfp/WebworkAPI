import os
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from core.downloader import (
    XLSX_CONTENT_TYPE,
    DownloadResult,
    _build_data_param,
    run_downloads,
    save_error_log,
)


FAKE_TOKEN = "fake-jwt-token"
FAKE_XLSX = b"\x50\x4b\x03\x04" + b"\x00" * 100  # Fake XLSX bytes


def _make_colab(name="Test User", uid="123456"):
    return {"id": uid, "nome": name}


def _make_response(status=200, content=FAKE_XLSX, content_type=XLSX_CONTENT_TYPE):
    resp = MagicMock()
    resp.status_code = status
    resp.content = content
    resp.headers = {"Content-Type": content_type}
    return resp


class TestBuildDataParam:
    def test_user_id_is_string(self):
        param = _build_data_param("397598", date(2026, 3, 15))
        assert '"user_id":"397598"' in param

    def test_date_format(self):
        param = _build_data_param("123", date(2026, 1, 5))
        assert '"date":"2026-01-05"' in param

    def test_contains_required_columns(self):
        param = _build_data_param("1", date(2026, 1, 1))
        assert '"screenshot":true' in param
        assert '"active_window_title":false' in param


class TestRunDownloads:
    @patch("core.downloader.time.sleep")
    @patch("core.downloader.requests.get")
    def test_successful_download(self, mock_get, mock_sleep, tmp_path):
        mock_get.return_value = _make_response()
        colabs = [_make_colab()]
        dates = [date(2026, 3, 1)]

        result = run_downloads(FAKE_TOKEN, colabs, dates, str(tmp_path))

        assert result.success == 1
        assert result.skipped == 0
        assert len(result.errors) == 0
        expected_file = tmp_path / "Test User" / "2026-03-01.xlsx"
        assert expected_file.exists()
        assert expected_file.read_bytes() == FAKE_XLSX

    @patch("core.downloader.time.sleep")
    @patch("core.downloader.requests.get")
    def test_skip_existing_file(self, mock_get, mock_sleep, tmp_path):
        colab = _make_colab()
        colab_dir = tmp_path / colab["nome"]
        colab_dir.mkdir()
        (colab_dir / "2026-03-01.xlsx").write_bytes(b"existing data")

        result = run_downloads(FAKE_TOKEN, [colab], [date(2026, 3, 1)], str(tmp_path))

        assert result.success == 0
        assert result.skipped == 1
        mock_get.assert_not_called()

    @patch("core.downloader.time.sleep")
    @patch("core.downloader.requests.get")
    def test_auth_failure_stops_all(self, mock_get, mock_sleep, tmp_path):
        mock_get.return_value = _make_response(status=401)
        colabs = [_make_colab("A", "1"), _make_colab("B", "2")]
        dates = [date(2026, 3, 1), date(2026, 3, 2)]

        result = run_downloads(FAKE_TOKEN, colabs, dates, str(tmp_path))

        assert result.auth_failed is True
        assert len(result.errors) == 1
        # Should have only made 1 request before stopping
        assert mock_get.call_count == 1

    @patch("core.downloader.time.sleep")
    @patch("core.downloader.requests.get")
    def test_403_stops_all(self, mock_get, mock_sleep, tmp_path):
        mock_get.return_value = _make_response(status=403)

        result = run_downloads(
            FAKE_TOKEN, [_make_colab()], [date(2026, 3, 1)], str(tmp_path)
        )

        assert result.auth_failed is True

    @patch("core.downloader.time.sleep")
    @patch("core.downloader.requests.get")
    def test_server_error_continues(self, mock_get, mock_sleep, tmp_path):
        mock_get.side_effect = [
            _make_response(status=500),
            _make_response(status=200),
        ]
        dates = [date(2026, 3, 1), date(2026, 3, 2)]

        result = run_downloads(FAKE_TOKEN, [_make_colab()], dates, str(tmp_path))

        assert result.success == 1
        assert len(result.errors) == 1
        assert "500" in result.errors[0]["motivo"]

    @patch("core.downloader.time.sleep")
    @patch("core.downloader.requests.get")
    def test_timeout_continues(self, mock_get, mock_sleep, tmp_path):
        mock_get.side_effect = [
            requests.exceptions.Timeout("timed out"),
            _make_response(),
        ]
        dates = [date(2026, 3, 1), date(2026, 3, 2)]

        result = run_downloads(FAKE_TOKEN, [_make_colab()], dates, str(tmp_path))

        assert result.success == 1
        assert len(result.errors) == 1
        assert "Timeout" in result.errors[0]["motivo"]

    @patch("core.downloader.time.sleep")
    @patch("core.downloader.requests.get")
    def test_empty_body_is_error(self, mock_get, mock_sleep, tmp_path):
        mock_get.return_value = _make_response(content=b"")

        result = run_downloads(
            FAKE_TOKEN, [_make_colab()], [date(2026, 3, 1)], str(tmp_path)
        )

        assert result.success == 0
        assert len(result.errors) == 1
        assert "tamanho: 0" in result.errors[0]["motivo"]

    @patch("core.downloader.time.sleep")
    @patch("core.downloader.requests.get")
    def test_wrong_content_type_is_error(self, mock_get, mock_sleep, tmp_path):
        mock_get.return_value = _make_response(content_type="text/html")

        result = run_downloads(
            FAKE_TOKEN, [_make_colab()], [date(2026, 3, 1)], str(tmp_path)
        )

        assert result.success == 0
        assert len(result.errors) == 1

    @patch("core.downloader.time.sleep")
    @patch("core.downloader.requests.get")
    def test_cancel_stops_process(self, mock_get, mock_sleep, tmp_path):
        mock_get.return_value = _make_response()
        cancel_after = 1
        call_count = [0]

        def should_cancel():
            call_count[0] += 1
            return call_count[0] > cancel_after

        dates = [date(2026, 3, 1), date(2026, 3, 2), date(2026, 3, 3)]
        result = run_downloads(
            FAKE_TOKEN,
            [_make_colab()],
            dates,
            str(tmp_path),
            should_cancel=should_cancel,
        )

        assert result.cancelled is True
        assert result.success <= 1

    @patch("core.downloader.time.sleep")
    @patch("core.downloader.requests.get")
    def test_progress_callback_called(self, mock_get, mock_sleep, tmp_path):
        mock_get.return_value = _make_response()
        progress_calls = []

        def on_progress(current, total, msg):
            progress_calls.append((current, total, msg))

        run_downloads(
            FAKE_TOKEN,
            [_make_colab()],
            [date(2026, 3, 1)],
            str(tmp_path),
            on_progress=on_progress,
        )

        assert len(progress_calls) == 1
        assert progress_calls[0][0] == 1
        assert progress_calls[0][1] == 1

    @patch("core.downloader.time.sleep")
    @patch("core.downloader.requests.get")
    def test_network_error_continues(self, mock_get, mock_sleep, tmp_path):
        mock_get.side_effect = [
            requests.exceptions.ConnectionError("no network"),
            _make_response(),
        ]
        dates = [date(2026, 3, 1), date(2026, 3, 2)]

        result = run_downloads(FAKE_TOKEN, [_make_colab()], dates, str(tmp_path))

        assert result.success == 1
        assert len(result.errors) == 1
        assert "rede" in result.errors[0]["motivo"]

    @patch("core.downloader.time.sleep")
    @patch("core.downloader.requests.get")
    def test_folder_structure(self, mock_get, mock_sleep, tmp_path):
        mock_get.return_value = _make_response()
        colabs = [_make_colab("Maria Isabel", "1"), _make_colab("João Silva", "2")]
        dates = [date(2026, 3, 1)]

        run_downloads(FAKE_TOKEN, colabs, dates, str(tmp_path))

        assert (tmp_path / "Maria Isabel" / "2026-03-01.xlsx").exists()
        assert (tmp_path / "João Silva" / "2026-03-01.xlsx").exists()


class TestSaveErrorLog:
    def test_creates_log_file(self, tmp_path):
        errors = [
            {
                "colaborador": "Test",
                "data": "01/03/2026",
                "motivo": "HTTP 500",
            }
        ]
        path = save_error_log(str(tmp_path), errors)
        assert os.path.exists(path)
        content = Path(path).read_text(encoding="utf-8")
        assert "Test" in content
        assert "HTTP 500" in content
