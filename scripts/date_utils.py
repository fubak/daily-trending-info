"""Shared date-formatting helpers used across renderers and generators."""

from datetime import datetime


def format_long_date(date_str: str) -> str:
    """Convert a YYYY-MM-DD date string to "Month D, YYYY".

    Raises ValueError if the input is not in the expected format.
    """
    return datetime.strptime(date_str, "%Y-%m-%d").strftime("%B %d, %Y")
