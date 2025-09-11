from dataclasses import dataclass
from .utils import format_bytes, format_time
from enum import Enum

class DownloadState(Enum):
    """
    Enumeration of possible download states.

    States:
        UNDEFINED: Download State is undefined
        PENDING: Download is queued but not started
        DOWNLOADING: Download is actively in progress
        PAUSED: Download is temporarily paused
        COMPLETED: Download finished successfully
        CANCELLED: Download was cancelled by user
        FAILED: Download failed due to error
        RETRYING: Download is being retried after failure
    """
    UNDEFINED = "undefined"
    PENDING = "pending"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class DownloadEvent:
    """
    Base class for download events containing common information.

    Attributes:
        url: The download URL
        output_path: The output file path
        timestamp: When the event occurred
        state: Current download state
    """
    url: str
    output_path: str
    timestamp: float
    state: DownloadState


@dataclass
class DownloadStartEvent(DownloadEvent):
    """Event fired when download starts."""
    total_bytes: int = 0

    @property
    def human_readable_total_bytes(self):
        return format_bytes(self.total_bytes)


@dataclass
class DownloadCompleteEvent(DownloadEvent):
    """Event fired when download completes successfully."""
    file_size: int = 0
    duration: float = 0.0

    @property
    def human_readable_file_size(self):
        return format_bytes(self.file_size)

    @property
    def human_readable_duration(self):
        return format_time(self.duration)


@dataclass
class DownloadFailureEvent(DownloadEvent):
    """Event fired when download fails."""
    error: Exception = None
    attempt: int = 0
    will_retry: bool = False


@dataclass
class DownloadTimeoutEvent(DownloadEvent):
    """Event fired when download times out."""
    timeout_type: str = "total"
    attempt: int = 0
    will_retry: bool = False


@dataclass
class DownloadRetryEvent(DownloadEvent):
    """Event fired when download is being retried."""
    attempt: int = 0
    max_attempts: int = 0
    delay: float = 0.0
    last_error: Exception = None


@dataclass
class DownloadCancelledEvent(DownloadEvent):
    """Event fired when download is cancelled."""
    reason: str = "user_cancelled"


@dataclass
class DownloadPausedEvent(DownloadEvent):
    """Event fired when download is paused."""
    downloaded_bytes: int = 0

    @property
    def human_readable_downloaded_bytes(self):
        return format_bytes(self.downloaded_bytes)


@dataclass
class DownloadResumedEvent(DownloadEvent):
    """Event fired when download is resumed."""
    resume_position: int = 0


@dataclass
class DownloadValidationEvent(DownloadEvent):
    """Event fired when file validation occurs."""
    validation_type: str = "extension"
    is_valid: bool = True
    message: str = ""
