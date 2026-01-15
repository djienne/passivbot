"""
DateTime utilities for timestamp and date conversions.
"""
import datetime
import dateutil.parser


def date_to_ts(date_str: str) -> float:
    """
    Convert a flexible date string to UTC timestamp in milliseconds.

    Args:
        date_str: Date string in various formats:
                 - "2020" -> "2020-01-01T00:00:00"
                 - "2024-04" -> "2024-04-01T00:00:00"
                 - "2022-04-23" -> "2022-04-23T00:00:00"
                 - "2021-11-13T03:23:12" (full ISO format)
                 - And other common variants

    Returns:
        UTC timestamp in milliseconds as float
    """
    date_str = date_str.strip()

    # Use dateutil.parser with default date of Jan 1, 2000 for missing components
    default_date = datetime.datetime(2000, 1, 1)

    try:
        dt = dateutil.parser.parse(date_str, default=default_date)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Unable to parse date string '{date_str}': {e}")

    # If the datetime is naive (no timezone info), treat it as UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)

    # Convert to UTC timestamp in milliseconds
    return dt.timestamp() * 1000


def ts_to_date(timestamp: float) -> str:
    """Convert timestamp to date string in ISO format."""
    if timestamp > 253402297199:
        return str(datetime.datetime.utcfromtimestamp(timestamp / 1000)).replace(" ", "T")
    return str(datetime.datetime.utcfromtimestamp(timestamp)).replace(" ", "T")


def get_day(date):
    """Extract day (YYYY-MM-DD) from date which can be str, datetime, or timestamp."""
    # date can be str datetime or float/int timestamp
    try:
        return ts_to_date(date_to_ts(date))[:10]
    except Exception:
        pass
    try:
        return ts_to_date(date)[:10]
    except Exception:
        pass
    raise Exception(f"failed to get day from {date}")


def get_utc_now_timestamp() -> int:
    """
    Creates a millisecond based timestamp of UTC now.
    :return: Millisecond based timestamp of UTC now.
    """
    return int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
