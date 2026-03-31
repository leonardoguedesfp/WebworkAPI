"""Excel report consolidation logic.

Merges multiple single-day XLSX reports into one flat workbook with a single
``Dados`` sheet.  All days are stacked vertically with a ``Data`` column.
"""

import re
from datetime import date
from pathlib import Path

from openpyxl import load_workbook, Workbook


# Flexible regex: find YYYY-MM-DD anywhere in the filename
_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _extract_date_from_filename(filename: str) -> date | None:
    """Try to extract a date from a filename containing ``YYYY-MM-DD``."""
    m = _DATE_RE.search(filename)
    if m:
        try:
            parts = m.group(1).split("-")
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
        except (ValueError, IndexError):
            return None
    return None


def _read_rows(fp: Path) -> list[list]:
    """Read all rows from the active sheet of an XLSX file."""
    try:
        wb = load_workbook(fp, data_only=True)
        ws = wb.active
        rows = [list(row) for row in ws.iter_rows(values_only=True)]
        wb.close()
        return rows
    except Exception:
        return []


def extract_collaborator_from_filename(filename: str) -> str | None:
    """Extract the collaborator name from a filename.

    Expects pattern: ``<name>_<YYYY-MM-DD>...``
    Returns the name with underscores replaced by spaces, or ``None``.
    """
    stem = Path(filename).stem if "." in filename else filename
    m = re.match(r"^(.+?)_(\d{4}-\d{2}-\d{2})", stem)
    if m:
        return m.group(1).replace("_", " ")
    return None


def detect_collaborator(
    filenames: list[str],
    known_names: list[str],
) -> tuple[str | None, str | None]:
    """Detect collaborator from a list of filenames.

    Compares extracted names against *known_names* (case-insensitive,
    ignoring underscores vs spaces).

    Returns:
        (matched_name, warning) -- *matched_name* is the canonical name from
        *known_names* if all files match the same collaborator, else ``None``.
        *warning* is set when files belong to different collaborators.
    """
    if not filenames:
        return None, None

    lookup: dict[str, str] = {}
    for name in known_names:
        key = name.replace("_", " ").strip().lower()
        lookup[key] = name

    detected: set[str] = set()
    any_extracted = False

    for fn in filenames:
        extracted = extract_collaborator_from_filename(fn)
        if extracted is None:
            continue
        any_extracted = True
        key = extracted.strip().lower()
        canonical = lookup.get(key)
        if canonical:
            detected.add(canonical)

    if not any_extracted:
        return None, None

    if len(detected) == 1:
        return detected.pop(), None

    if len(detected) > 1:
        return None, (
            "Os arquivos selecionados são de colaboradores diferentes. "
            "Selecione arquivos de um único colaborador."
        )

    return None, None


def consolidate_files(
    files: list[Path],
    colab_name: str,
    output_dir: Path | None = None,
) -> Path | None:
    """Consolidate multiple XLSX files into a single flat workbook.

    Produces one ``Dados`` sheet with a ``Data`` column prepended.  The header
    row from the source files is written once; data rows from all days are
    stacked chronologically.

    Args:
        files: Paths to the ``.xlsx`` files to merge.
        colab_name: Collaborator name (used in the output filename).
        output_dir: Directory where the consolidated file is saved.
            Defaults to the parent directory of the first file.

    Returns:
        Path to the consolidated file, or ``None`` if *files* is empty.
    """
    if not files:
        return None

    if output_dir is None:
        output_dir = files[0].parent

    # Build (date_or_None, path) and sort chronologically
    items: list[tuple[date | None, Path]] = []
    for fp in files:
        dt = _extract_date_from_filename(fp.name)
        items.append((dt, fp))

    items.sort(key=lambda t: (t[0] is None, t[0] or date.min, t[1].name))

    extracted_dates = sorted(d for d, _ in items if d is not None)

    wb = Workbook()
    ws = wb.active
    ws.title = "Dados"

    header_written = False
    any_data = False

    for dt, fp in items:
        rows = _read_rows(fp)
        if not rows:
            continue

        # First row is the header
        header_row = rows[0]
        data_rows = rows[1:]

        # Skip files with only a header (no data)
        if not data_rows:
            continue

        if not header_written:
            ws.append(["Data"] + list(header_row))
            header_written = True

        date_str = dt.strftime("%Y-%m-%d") if dt else ""
        for row in data_rows:
            ws.append([date_str] + list(row))
            any_data = True

    if not any_data:
        wb.close()
        return None

    if extracted_dates:
        start_str = min(extracted_dates).strftime("%Y-%m-%d")
        end_str = max(extracted_dates).strftime("%Y-%m-%d")
    else:
        start_str = "sem-data"
        end_str = "sem-data"

    out_name = f"consolidado_{colab_name}_{start_str}_{end_str}.xlsx"
    out_path = output_dir / out_name

    wb.save(out_path)
    wb.close()

    return out_path


def consolidate_general(
    colab_results: list[tuple[str, Path]],
    output_dir: Path,
) -> Path | None:
    """Consolidate all collaborators into a single flat workbook.

    Args:
        colab_results: List of (colab_name, consolidated_individual_path) or
            more precisely (colab_name, colab_folder) pairs.  For each
            collaborator, all ``*.xlsx`` files (excluding existing consolidados)
            in the folder are included.
        output_dir: Root destination folder for the general consolidation.

    Returns:
        Path to the general consolidated file, or ``None`` if insufficient data.
    """
    if len(colab_results) < 2:
        return None

    wb = Workbook()
    ws = wb.active
    ws.title = "Dados"

    header_written = False
    any_data = False
    all_dates: list[date] = []

    # Sort collaborators alphabetically
    for colab_name, colab_folder in sorted(colab_results, key=lambda t: t[0]):
        # Collect individual day files (exclude consolidados)
        day_files: list[tuple[date | None, Path]] = []
        for fp in sorted(colab_folder.glob("*.xlsx")):
            if fp.name.startswith("consolidado_"):
                continue
            dt = _extract_date_from_filename(fp.name)
            day_files.append((dt, fp))

        day_files.sort(key=lambda t: (t[0] is None, t[0] or date.min, t[1].name))

        for dt, fp in day_files:
            rows = _read_rows(fp)
            if not rows:
                continue

            header_row = rows[0]
            data_rows = rows[1:]

            if not data_rows:
                continue

            if not header_written:
                ws.append(["Colaborador", "Data"] + list(header_row))
                header_written = True

            date_str = dt.strftime("%Y-%m-%d") if dt else ""
            if dt:
                all_dates.append(dt)

            for row in data_rows:
                ws.append([colab_name, date_str] + list(row))
                any_data = True

    if not any_data:
        wb.close()
        return None

    if all_dates:
        start_str = min(all_dates).strftime("%Y-%m-%d")
        end_str = max(all_dates).strftime("%Y-%m-%d")
    else:
        start_str = "sem-data"
        end_str = "sem-data"

    out_name = f"consolidado_geral_{start_str}_{end_str}.xlsx"
    out_path = output_dir / out_name

    wb.save(out_path)
    wb.close()

    return out_path


def consolidate_after_download(
    colab_name: str,
    colab_folder: Path,
    success_dates: list[date],
) -> Path | None:
    """Consolidate downloaded files for a collaborator after download.

    Returns:
        Path to the consolidated file, or ``None`` if no files to consolidate.
    """
    if not success_dates:
        return None

    from core.downloader import make_filename

    sorted_dates = sorted(success_dates)
    files: list[Path] = []
    for dt in sorted_dates:
        fp = colab_folder / make_filename(colab_name, dt)
        if fp.exists():
            files.append(fp)

    if not files:
        return None

    return consolidate_files(files, colab_name, output_dir=colab_folder)
