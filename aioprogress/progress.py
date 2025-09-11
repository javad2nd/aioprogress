from time import time
from inspect import iscoroutinefunction
from typing import Optional
import asyncio
from dataclasses import dataclass

from aioprogress.utils import format_time, format_bytes


@dataclass
class ProgressData:
    """
    Data class to store all progress-related variables and calculations.

    Attributes:
        current: Bytes downloaded so far
        total: Total bytes to download
        speed: Current download speed in bytes/second
        elapsed: Time elapsed since download started
        eta: Estimated time remaining
        progress: Progress percentage (0-100)
        current_human_readable: Human-readable current bytes (e.g., "1.2 MB")
        total_human_readable: Human-readable total bytes (e.g., "10.5 MB")
        speed_human_readable: Human-readable speed (e.g., "2.3 MB/s")
        elapsed_human_readable: Human-readable elapsed time (e.g., "1m 30s")
        eta_human_readable: Human-readable ETA (e.g., "5m 20s")
    """
    current: float
    total: float
    speed: float
    elapsed: float
    eta: float
    progress: float
    current_human_readable: str
    total_human_readable: str
    speed_human_readable: str
    elapsed_human_readable: str
    eta_human_readable: str

    def to_dict(self) -> dict:
        """Convert to dictionary for easy parameter passing."""
        return {
            'current': self.current,
            'total': self.total,
            'speed': self.speed,
            'elapsed': self.elapsed,
            'eta': self.eta,
            'progress': self.progress,
            'current_human_readable': self.current_human_readable,
            'total_human_readable': self.total_human_readable,
            'speed_human_readable': self.speed_human_readable,
            'elapsed_human_readable': self.elapsed_human_readable,
            'eta_human_readable': self.eta_human_readable,
        }

    def __int__(self):
        return int(self.progress)

    def __str__(self):
        return f"{self.progress:.2f}%"


class Progress:
    """
    Handles progress tracking and updates for file downloads.

    Provides speed calculation, ETA estimation, and formatted output
    for both human-readable and programmatic use.

    Args:
        callback: Function to call with progress updates
        interval: Minimum time between progress updates (seconds)
        loop: Event loop to use for async callbacks

    Example:
        >>> def my_callback(data: ProgressData):
        ...     print(f"{data.progress:.1f}% - {data.speed_human_readable} - ETA: {data.eta_human_readable}")
        >>> progress = Progress(my_callback, interval=2.0)
        >>> progress(1024, 10240)  # current bytes, total bytes
    """

    NONE = lambda x: None
    kwargs: dict = dict()

    def __init__(
            self,
            callback: Optional[callable] = None,
            interval: float = 1.0,
            loop: asyncio.AbstractEventLoop = None,
            **kwargs,
    ) -> None:
        """
        Initialize the progress tracker.

        Args:
            callback: Function to call with progress updates. If None, uses default printer
            interval: Minimum time between updates in seconds
            loop: Event loop for async callbacks. Uses current loop if None
        """
        self.callback = callback or self.default
        self.interval = interval
        self.start_time: float | None = None
        self.last_edit: float = 0
        self.last_bytes: float = 0
        self.loop = loop or asyncio.get_event_loop()
        self.kwargs = kwargs or dict()

    def __call__(self, current: float, total: float) -> None:
        """
        Update progress with current download status.

        Calculates speed, ETA, and percentage, then calls the callback
        with relevant parameters based on its signature.

        Args:
            current: Bytes downloaded so far
            total: Total bytes to download (0 if unknown)
        """
        now = time()
        self.start_time = self.start_time or now

        if now - self.last_edit < self.interval and current != total:
            return
        self.last_edit = now

        elapsed = now - self.start_time
        speed = (current - self.last_bytes) / max(now - self.last_edit, 1)
        progress = round(current / total * 100, 2) if total > 0 else 0
        eta = (total - current) / speed if speed > 0 else 0

        current_str = format_bytes(current)
        total_str = format_bytes(total)
        speed_str = format_bytes(speed) + "/s"
        elapsed_str = format_time(elapsed)
        eta_str = format_time(eta)

        datas = ProgressData(
            current=current,
            total=total,
            speed=speed,
            elapsed=elapsed,
            eta=eta,
            progress=progress,
            current_human_readable=current_str,
            total_human_readable=total_str,
            speed_human_readable=speed_str,
            elapsed_human_readable=elapsed_str,
            eta_human_readable=eta_str,
        )

        if iscoroutinefunction(self.callback):
            self.loop.create_task(self.callback(datas, **self.kwargs))
        else:
            self.callback(datas, **self.kwargs)

        self.last_bytes = current

    def default(self, progress: ProgressData):
        """Default progress callback that prints percentage."""
        print(progress)

    def update(self, **kwargs):
        self.kwargs.update(kwargs)

    def get(self, item, default=None):
        return self.kwargs.get(item, default)

    def set(self, key, value):
        self.kwargs.update({key: value})
