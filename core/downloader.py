import json
import os
import time
from datetime import date
from pathlib import Path
from typing import Callable

import requests

DOWNLOAD_URL = (
    "https://realtime.webwork-tracker.com/api/monitoring/"
    "daily-activity/download-excel/xlsx"
)

XLSX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

REQUEST_DELAY = 1.5  # seconds between requests


def _build_data_param(user_id: str, dt: date) -> str:
    """Build the JSON `data` parameter for the API request."""
    payload = {
        "user_id": str(user_id),
        "date": dt.strftime("%Y-%m-%d"),
        "contract_id": "",
        "groupBy": "minute",
        "timeFormat": "colon",
        "defaultColumns": {
            "time": True,
            "mouse": True,
            "keyboard": True,
            "scroll": True,
            "activity_level": True,
            "project": True,
            "task_title": True,
            "description": True,
            "app": True,
            "active_window_title": False,
            "category": False,
            "url": True,
            "version": False,
            "ip": False,
            "public_ip": False,
            "trackType": False,
            "screenshot": True,
        },
        "clockFormat": "HH:mm",
    }
    return json.dumps(payload, separators=(",", ":"))


def make_filename(colab_name: str, dt: date) -> str:
    """Build the filename for a downloaded report.

    Pattern: ``<collaborator name>_<YYYY-MM-DD>.xlsx``
    """
    return f"{colab_name}_{dt.strftime('%Y-%m-%d')}.xlsx"


class DownloadResult:
    """Holds the results of a batch download run."""

    def __init__(self):
        self.success = 0
        self.skipped = 0
        self.errors: list[dict] = []  # {"colaborador", "data", "motivo"}
        self.cancelled = False
        self.auth_failed = False


class ColabDownloadResult:
    """Results for a single collaborator's download batch."""

    def __init__(self, colab_name: str):
        self.colab_name = colab_name
        self.success_dates: list[date] = []
        self.colab_folder: Path | None = None


def run_downloads(
    token: str,
    colaboradores: list[dict],
    dates: list[date],
    dest_folder: str,
    on_progress: Callable[[int, int, str], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
    on_colab_complete: Callable[[ColabDownloadResult], None] | None = None,
) -> DownloadResult:
    """Execute the batch download process.

    Args:
        token: JWT token extracted from the WebWork URL.
        colaboradores: List of dicts with 'id' and 'nome' keys.
        dates: List of dates to download.
        dest_folder: Root destination folder.
        on_progress: Callback(current, total, status_message).
        should_cancel: Callback that returns True if the user wants to cancel.
        on_colab_complete: Callback fired after all dates for one collaborator
            have been processed. Receives a ColabDownloadResult with the list
            of successfully downloaded dates and the collaborator folder path.

    Returns:
        DownloadResult with counts and error details.
    """
    result = DownloadResult()
    total = len(colaboradores) * len(dates)
    current = 0

    for colab in colaboradores:
        colab_folder = Path(dest_folder) / colab["nome"]
        colab_folder.mkdir(parents=True, exist_ok=True)

        colab_result = ColabDownloadResult(colab["nome"])
        colab_result.colab_folder = colab_folder

        for dt in dates:
            if should_cancel and should_cancel():
                result.cancelled = True
                # Still fire callback for partial results
                if on_colab_complete and colab_result.success_dates:
                    on_colab_complete(colab_result)
                return result

            current += 1
            filename = make_filename(colab["nome"], dt)
            filepath = colab_folder / filename

            # Skip existing files
            if filepath.exists() and filepath.stat().st_size > 0:
                result.skipped += 1
                colab_result.success_dates.append(dt)
                if on_progress:
                    on_progress(
                        current,
                        total,
                        f"Pulado (já existe): {colab['nome']} — "
                        f"{dt.strftime('%d/%m/%Y')}",
                    )
                continue

            if on_progress:
                on_progress(
                    current,
                    total,
                    f"Baixando: {colab['nome']} — {dt.strftime('%d/%m/%Y')}",
                )

            data_param = _build_data_param(colab["id"], dt)

            try:
                resp = requests.get(
                    DOWNLOAD_URL,
                    params={"token": token, "data": data_param},
                    timeout=60,
                )

                if resp.status_code in (401, 403):
                    result.auth_failed = True
                    result.errors.append(
                        {
                            "colaborador": colab["nome"],
                            "data": dt.strftime("%d/%m/%Y"),
                            "motivo": (
                                f"HTTP {resp.status_code} — Token inválido ou "
                                "expirado. Capture um novo token."
                            ),
                        }
                    )
                    if on_colab_complete and colab_result.success_dates:
                        on_colab_complete(colab_result)
                    return result

                if resp.status_code != 200:
                    result.errors.append(
                        {
                            "colaborador": colab["nome"],
                            "data": dt.strftime("%d/%m/%Y"),
                            "motivo": f"HTTP {resp.status_code}",
                        }
                    )
                    time.sleep(REQUEST_DELAY)
                    continue

                content_type = resp.headers.get("Content-Type", "")
                if (
                    XLSX_CONTENT_TYPE not in content_type
                    or len(resp.content) == 0
                ):
                    result.errors.append(
                        {
                            "colaborador": colab["nome"],
                            "data": dt.strftime("%d/%m/%Y"),
                            "motivo": (
                                "Resposta não é um XLSX válido "
                                f"(Content-Type: {content_type}, "
                                f"tamanho: {len(resp.content)} bytes)"
                            ),
                        }
                    )
                    time.sleep(REQUEST_DELAY)
                    continue

                filepath.write_bytes(resp.content)
                result.success += 1
                colab_result.success_dates.append(dt)

            except requests.exceptions.Timeout:
                result.errors.append(
                    {
                        "colaborador": colab["nome"],
                        "data": dt.strftime("%d/%m/%Y"),
                        "motivo": "Timeout na requisição",
                    }
                )
            except requests.exceptions.RequestException as e:
                result.errors.append(
                    {
                        "colaborador": colab["nome"],
                        "data": dt.strftime("%d/%m/%Y"),
                        "motivo": f"Erro de rede: {e}",
                    }
                )

            time.sleep(REQUEST_DELAY)

        # Notify caller that this collaborator is done
        if on_colab_complete:
            on_colab_complete(colab_result)

    return result


def save_error_log(dest_folder: str, errors: list[dict]) -> str:
    """Save error log to dest_folder/log_erros.txt. Returns the file path."""
    log_path = Path(dest_folder) / "log_erros.txt"
    lines = ["Log de Erros — WebWork Downloader\n"]
    lines.append("=" * 50 + "\n")
    for err in errors:
        lines.append(
            f"Colaborador: {err['colaborador']}\n"
            f"Data: {err['data']}\n"
            f"Motivo: {err['motivo']}\n"
            f"{'-' * 40}\n"
        )
    log_path.write_text("\n".join(lines), encoding="utf-8")
    return str(log_path)
