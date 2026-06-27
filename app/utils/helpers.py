from datetime import datetime

def format_datetime(dt: datetime) -> str:
    """
    Formats a datetime object into a standard string representation.
    """
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def truncate_string(s: str, max_length: int = 100) -> str:
    """
    Truncates a string to a specified length and appends ellipsis if needed.
    """
    if len(s) > max_length:
        return s[:max_length - 3] + "..."
    return s
