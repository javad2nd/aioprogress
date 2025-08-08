import time
import inspect
import typing
import asyncio
from aioprogress.utils import format_time, format_bytes


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
        >>> def my_callback(progress, speed_human_readable, eta_human_readable):
        ...     print(f"{progress:.1f}% - {speed_human_readable} - ETA: {eta_human_readable}")
        >>> progress = Progress(my_callback, interval=2.0)
        >>> progress(1024, 10240)  # current bytes, total bytes
    """
    
    def __init__(
        self,
        callback: typing.Optional[callable] = None,
        interval: float = 1.0,
        loop: asyncio.AbstractEventLoop = None
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
        self.callback_params = set(inspect.signature(self.callback).parameters.keys())
        self.loop = loop or asyncio.get_event_loop()

    def __call__(self, current: int, total: int) -> None:
        """
        Update progress with current download status.
        
        Calculates speed, ETA, and percentage, then calls the callback
        with relevant parameters based on its signature.

        Args:
            current: Bytes downloaded so far
            total: Total bytes to download (0 if unknown)
        """
        now = time.time()
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

        vars_dict = {
            "current": current,
            "total": total,
            "speed": speed,
            "elapsed": elapsed,
            "eta": eta,
            "progress": progress,
            "current_human_readable": current_str,
            "total_human_readable": total_str,
            "speed_human_readable": speed_str,
            "elapsed_human_readable": elapsed_str,
            "eta_human_readable": eta_str,
        }

        kwargs = {key: value for key, value in vars_dict.items() if key in self.callback_params}
        
        if inspect.iscoroutinefunction(self.callback):
            self.loop.create_task(self.callback(**kwargs))
        else:
            self.callback(**kwargs)

        self.last_bytes = current

    def default(self, progress):
        """Default progress callback that prints percentage."""
        print(f"{progress:.2f}%")
