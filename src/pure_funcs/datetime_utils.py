"""
DateTime utilities for timestamp and date conversions.
"""
import datetime

from utils import date_to_ts


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
