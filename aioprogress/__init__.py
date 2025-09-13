"""A high-performance, flexible async file downloader built with aiohttp.

Supports resume downloads, progress tracking, cancellation, proxy support,
and concurrent downloads.
"""

__version__ = "0.2.1"

from .downloader import DownloadState, DownloadConfig, AsyncDownloader, DownloadManager
from .progress import Progress, ProgressData
from .utils import format_bytes, format_time
from .fetch_info import get_url_info, get_multiple_url_info, URLInfoFetcher, URLInfo, FetchMethod, FetchConfig
