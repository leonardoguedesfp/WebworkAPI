"""Excel report consolidation logic.

Merges multiple single-day XLSX reports into one workbook with one sheet per
day, ordered chronologically.
"""

import re
from datetime import date
from pathlib import Path

from openpyxl import load_workbook, Workbook


# Flexible regex: find YYYY-MM-DD anywhere in the filename (not just before .xlsx)
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


def _sheet_name_for_date(dt: date) -> str:
    """Return ``DD-MM`` sheet name for a given date."""
    return dt.strftime("%d-%m")


def _safe_sheet_name(name: str) -> str:
    """Truncate and sanitise a string for use as an Excel sheet name."""
    # Remove characters invalid in sheet names
    for ch in ("\\", "/", "*", "?", ":", "[", "]"):
        name = name.replace(ch, "_")
    return name[:31]


def consolidate_files(
    files: list[Path],
    colab_name: str,
    output_dir: Path | None = None,
) -> Path | None:
    """Consolidate multiple XLSX files into a single workbook.

    Each source file becomes one worksheet.  The sheet name is derived from
    the date encoded in the filename (``DD-MM``); if the filename does not
    match the expected pattern the original stem is used (truncated to 31
    chars).

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

    # Build list of (date_or_None, path) and sort chronologically
    items: list[tuple[date | None, Path]] = []
    for fp in files:
        dt = _extract_date_from_filename(fp.name)
        items.append((dt, fp))

    # Sort: dated files first (chronologically), then undated (by name)
    items.sort(key=lambda t: (t[0] is None, t[0] or date.min, t[1].name))

    # Determine date range from successfully extracted dates
    extracted_dates = sorted(d for d, _ in items if d is not None)

    wb = Workbook()
    # Remove the default sheet created by openpyxl
    wb.remove(wb.active)

    used_names: set[str] = set()

    for dt, fp in items:
        if dt is not None:
            sheet_name = _sheet_name_for_date(dt)
        else:
            sheet_name = _safe_sheet_name(fp.stem)

        # Ensure uniqueness
        base = sheet_name
        counter = 1
        while sheet_name in used_names:
            suffix = f"_{counter}"
            sheet_name = base[: 31 - len(suffix)] + suffix
            counter += 1
        used_names.add(sheet_name)

        ws = wb.create_sheet(title=sheet_name)

        try:
            src_wb = load_workbook(fp, data_only=True)
            src_ws = src_wb.active
            for row in src_ws.iter_rows(values_only=True):
                ws.append(list(row))
            src_wb.close()
        except Exception:
            # If we can't read the file, leave the sheet empty
            ws.append(["Erro ao ler o arquivo original"])

    if not wb.sheetnames:
        return None

    # Build output filename using real dates — never use placeholder strings
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


def consolidate_after_download(
    colab_name: str,
    colab_folder: Path,
    success_dates: list[date],
) -> Path | None:
    """Consolidate downloaded files for a collaborator after download.

    Uses the known list of successfully downloaded dates to locate files
    using the standard naming pattern.

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
