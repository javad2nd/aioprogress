def format_bytes(byte: float, decimals: int = 2) -> str:
    """
    Convert bytes to human-readable format.

    Args:
        byte: Number of bytes to format
        decimals: Number of decimal places to show

    Returns:
        Human-readable string with appropriate unit (B, KB, MB, etc.)

    Example:
        >>> format_bytes(1024)
        '1.00 KB'
        >>> format_bytes(1536, 1)
        '1.5 KB'
    """
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']
    for unit in units:
        if byte < 1024:
            return f"{byte:.{decimals}f} {unit}"
        byte /= 1024
    return f"{byte:.{decimals}f} {units[-1]}"


def format_time(seconds: float) -> str:
    """
    Format seconds into a human-readable time string.

    Args:
        seconds: Time duration in seconds

    Returns:
        Formatted time string in format "Xh Ym Zs"

    Example:
        >>> format_time(3661)
        '1h 1m 1s'
        >>> format_time(125)
        '2m 5s'
    """
    if seconds < 0:
        return "0s"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes or hours:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)
