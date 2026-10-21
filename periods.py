"""Calendar ranges for live data; legacy window sizes for offline demo fixtures."""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

PERIODS = (10, 7, 3, 1)
MAX_PERIOD = max(PERIODS)


def calendar_range(start_date, end_date):
    """Inclusive Lithuanian dates, converted to a half-open timestamp interval."""
    try:
        first, last = date.fromisoformat(start_date), date.fromisoformat(end_date)
        if first.isoformat() != start_date or last.isoformat() != end_date:
            raise ValueError()
        if first > last:
            raise ValueError("Data „Nuo“ negali būti vėlesnė už datą „Iki“.")
        zone = ZoneInfo("Europe/Vilnius")
        return datetime.combine(first, time(), zone), datetime.combine(last + timedelta(days=1), time(), zone)
    except (TypeError, OverflowError):
        raise ValueError("Pasirinkite tinkamas datas „Nuo“ ir „Iki“ (YYYY-MM-DD).") from None
    except ValueError as error:
        if "Nuo" in str(error):
            raise
        raise ValueError("Pasirinkite tinkamas datas „Nuo“ ir „Iki“ (YYYY-MM-DD).") from None
