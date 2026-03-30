from datetime import date, timedelta


def parse_date_br(date_str: str) -> date:
    """Parse a date string in DD/MM/YYYY format.

    Raises:
        ValueError: If the format is invalid.
    """
    parts = date_str.strip().split("/")
    if len(parts) != 3:
        raise ValueError(f"Formato de data inválido: '{date_str}'. Use DD/MM/AAAA.")
    try:
        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
        return date(year, month, day)
    except (ValueError, OverflowError):
        raise ValueError(f"Data inválida: '{date_str}'.")


def generate_date_range(start: date, end: date) -> list[date]:
    """Generate a list of all dates from start to end (inclusive).

    Raises:
        ValueError: If start > end.
    """
    if start > end:
        raise ValueError("A data de início não pode ser posterior à data de fim.")
    dates = []
    current = start
    while current <= end:
        dates.append(current)
        current += timedelta(days=1)
    return dates


class DateValidationResult:
    """Result of date validation, including truncation info."""

    def __init__(self, dates: list[date], truncated: bool = False,
                 truncated_to: date | None = None):
        self.dates = dates
        self.truncated = truncated
        self.truncated_to = truncated_to


def validate_dates(start_str: str, end_str: str) -> tuple[date, DateValidationResult]:
    """Parse, validate, and generate the date range.

    If the end date is in the future, it is silently truncated to today.
    If both dates are in the future, raises ValueError.

    Returns:
        Tuple of (start_date, DateValidationResult).

    Raises:
        ValueError: If start > end, or both dates are future.
    """
    start = parse_date_br(start_str)
    end = parse_date_br(end_str)

    if start > end:
        raise ValueError("A data de início não pode ser posterior à data de fim.")

    today = date.today()

    # Both dates in the future
    if start > today and end > today:
        raise ValueError(
            "O intervalo selecionado contém apenas datas futuras. "
            "Selecione um período válido."
        )

    # Truncate end date to today if it's in the future
    truncated = False
    if end > today:
        end = today
        truncated = True

    dates = generate_date_range(start, end)
    return start, DateValidationResult(
        dates=dates,
        truncated=truncated,
        truncated_to=today if truncated else None,
    )
