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


def validate_dates(start_str: str, end_str: str) -> tuple[date, list[date]]:
    """Parse, validate, and generate the date range.

    Returns:
        Tuple of (start_date, list_of_dates).

    Raises:
        ValueError: On any validation failure.
    """
    start = parse_date_br(start_str)
    end = parse_date_br(end_str)

    today = date.today()
    if start > today:
        raise ValueError("A data de início não pode ser futura.")
    if end > today:
        raise ValueError("A data de fim não pode ser futura.")

    return start, generate_date_range(start, end)
