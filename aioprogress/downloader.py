import asyncio
import typing
from urllib.parse import urlparse
from re import search
from os.path import basename, dirname, join
import aiohttp
import aiofiles
import aiofiles.os
from dataclasses import dataclass, field
from enum import Enum
from .progress import Progress
from .fetch_info import URLInfoFetcher, FetchConfig, URLInfo

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
    """
    UNDEFINED = "undefined"
    PENDING = "pending"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"

@dataclass
class DownloadConfig:
    """
    Configuration class for download behavior and parameters.
    
    Attributes:
        chunk_size: Size of data chunks to read at once (bytes)
        timeout: HTTP client timeout configuration
        max_retries: Maximum number of retry attempts on failure
        retry_delay: Base delay between retries (exponential backoff)
        resume_downloads: Whether to resume partially downloaded files
        overwrite_existing: Whether to overwrite existing complete files
        validate_ssl: Whether to validate SSL certificates
        headers: Additional HTTP headers to send with requests
        allowed_extensions: Set of allowed file extensions (empty = allow all)
        validate_content_type: Whether to validate response content type
        expected_content_types: Set of expected content type prefixes
        progress_interval: Minimum time between progress updates (seconds)
        auto_create_dirs: Whether to automatically create output directories
        proxy_url: HTTP/HTTPS/SOCKS proxy URL (e.g., 'http://proxy.example.com:8080')
        proxy_auth: Proxy authentication (username, password) tuple
        proxy_headers: Additional headers to send to proxy
        trust_env: Whether to trust environment variables for proxy configuration
        
    Example:
        >>> config = DownloadConfig(
        ...     chunk_size=16384,
        ...     max_retries=5,
        ...     allowed_extensions={'mp4', 'mkv', 'avi'},
        ...     headers={'User-Agent': 'MyDownloader/1.0'},
        ...     proxy_url='http://proxy.example.com:8080',
        ...     proxy_auth=('username', 'password')
        ... )
    """
    chunk_size: int = 8192
    timeout: aiohttp.ClientTimeout = field(default_factory=lambda: aiohttp.ClientTimeout(total=300))
    max_retries: int = 3
    retry_delay: float = 1.0
    resume_downloads: bool = True
    overwrite_existing: bool = False
    validate_ssl: bool = True
    headers: dict = field(default_factory=dict)
    allowed_extensions: set = field(default_factory=set)
    validate_content_type: bool = False
    expected_content_types: set = field(default_factory=set)
    progress_interval: float = 1.0
    auto_create_dirs: bool = True
    proxy_url: typing.Optional[str] = None
    proxy_auth: typing.Optional[typing.Tuple[str, str]] = None
    proxy_headers: dict = field(default_factory=dict)
    trust_env: bool = True

class AsyncDownloader:
    """
    High-performance async file downloader with resume capability and proxy support.
    
    Supports downloading files from HTTP/HTTPS URLs with features like:
    - Resume interrupted downloads
    - Progress tracking with callbacks
    - Cancellation and pause/resume
    - File validation (extensions, content types) using URLInfo from fetch_info
    - Automatic retry with exponential backoff
    - SSL validation control
    - HTTP/HTTPS/SOCKS proxy support
    - Environment proxy configuration
    
    Args:
        url: URL to download from
        output_path: Local path to save file (file or directory)
        config: Download configuration options
        progress_callback: Function to call with progress updates
        
    Example:
        >>> # Basic usage
        >>> from aioprogress import ProgressData
        >>>
        >>> async def progress_cb(data: ProgressData):
        ...     print(f"{data.progress:.1f}% at {data.speed_human_readable}")
        >>> 
        >>> async with AsyncDownloader(
        ...     "https://example.com/video.mp4",
        ...     "./downloads/",
        ...     progress_callback=progress_cb
        ... ) as downloader:
        ...     file_path = await downloader.start()
        ...     print(f"Downloaded to: {file_path}")
        
        >>> # With HTTP proxy
        >>> config = DownloadConfig(
        ...     proxy_url='http://proxy.example.com:8080',
        ...     proxy_auth=('username', 'password'),
        ...     proxy_headers={'User-Agent': 'CustomAgent/1.0'}
        ... )
        >>> async with AsyncDownloader(url, path, config) as downloader:
        ...     await downloader.start()
        
        >>> # With SOCKS proxy (requires aiohttp-socks)
        >>> config = DownloadConfig(
        ...     proxy_url='socks5://127.0.0.1:1080',
        ...     proxy_auth=('user', 'pass')
        ... )
        >>> async with AsyncDownloader(url, path, config) as downloader:
        ...     await downloader.start()
    """

    def __init__(
        self,
        url: str,
        output_path: str,
        config: DownloadConfig = None,
        progress_callback: typing.Optional[callable] = None
    ):
        """
        Initialize the downloader.

        Args:
            url: URL to download from
            output_path: Where to save the file (file or directory path)
            config: Configuration options. Uses defaults if None
            progress_callback: Optional callback for progress updates
        """
        self.url = url
        self.output_path = output_path
        self.config = config or DownloadConfig()
        self.progress = Progress(progress_callback, self.config.progress_interval)
        self.state = DownloadState.PENDING
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self.session: aiohttp.ClientSession = None
        self.cancel_event = asyncio.Event()
        self.pause_event = asyncio.Event()
        self.current_task: asyncio.Task = None
        self.resume_position = 0
        self.url_info: URLInfo = None

    async def __aenter__(self):
        """Async context manager entry. Sets up HTTP session with proxy support."""
        connector_kwargs = {'ssl': self.config.validate_ssl}

        fetch_config = FetchConfig(
            timeout=self.config.timeout,
            headers=self.config.headers,
            validate_ssl=self.config.validate_ssl,
            proxy_url=self.config.proxy_url,
            proxy_auth=self.config.proxy_auth,
            trust_env=self.config.trust_env
        )
        self.fetcher = URLInfoFetcher(fetch_config)
        await self.fetcher.__aenter__()
        self.url_info = await self.fetcher.fetch_info(self.url)

        if self.config.proxy_url:
            connector = aiohttp.TCPConnector(**connector_kwargs)

            session_kwargs = {
                'connector': connector,
                'timeout': self.config.timeout,
                'headers': self.config.headers,
                'trust_env': self.config.trust_env
            }

            if self.config.proxy_url.startswith(('http://', 'https://')):
                session_kwargs['proxy'] = self.config.proxy_url

                if self.config.proxy_auth:
                    session_kwargs['proxy_auth'] = aiohttp.BasicAuth(
                        self.config.proxy_auth[0],
                        self.config.proxy_auth[1]
                    )

                if self.config.proxy_headers:
                    session_kwargs['proxy_headers'] = self.config.proxy_headers

            elif self.config.proxy_url.startswith('socks'):
                try:
                    import aiohttp_socks
                    from aiohttp_socks import ProxyType

                    proxy_type = ProxyType.SOCKS5 if 'socks5' in self.config.proxy_url else ProxyType.SOCKS4

                    proxy_parts = self.config.proxy_url.replace('socks4://', '').replace('socks5://', '').split(':')
                    proxy_host = proxy_parts[0]
                    proxy_port = int(proxy_parts[1]) if len(proxy_parts) > 1 else 1080

                    connector = aiohttp_socks.ProxyConnector(
                        proxy_type=proxy_type,
                        host=proxy_host,
                        port=proxy_port,
                        username=self.config.proxy_auth[0] if self.config.proxy_auth else None,
                        password=self.config.proxy_auth[1] if self.config.proxy_auth else None,
                        **connector_kwargs
                    )
                    session_kwargs['connector'] = connector

                except ImportError:
                    raise ImportError(
                        "aiohttp-socks is required for SOCKS proxy support. Install with: pip install aiohttp-socks")
            else:
                raise ValueError(f"Unsupported proxy protocol: {self.config.proxy_url}")
        else:
            connector = aiohttp.TCPConnector(**connector_kwargs)
            session_kwargs = {
                'connector': connector,
                'timeout': self.config.timeout,
                'headers': self.config.headers,
                'trust_env': self.config.trust_env
            }

        self.session = aiohttp.ClientSession(**session_kwargs)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit. Cleans up HTTP session."""
        if self.session:
            await self.session.close()
        if self.fetcher:
            await self.fetcher.__aexit__(exc_type, exc_val, exc_tb)

    def _get_filename_from_response(self, response: aiohttp.ClientResponse) -> str:
        """
        Extract filename from HTTP response headers or URL.

        Args:
            response: HTTP response object

        Returns:
            Filename string, defaulting to 'download' if none found
        """
        if disposition := response.headers.get("Content-Disposition"):
            if match := search(r"filename[*]?=(?:[\"']?)([^\"';]+)(?:[\"']?)", disposition):
                return match.group(1)

        path = urlparse(self.url).path
        filename = basename(path) if path else "download"
        return filename or "download"

    def _validate_file(self, url_info: URLInfo) -> tuple[bool, str]:
        """
        Validate file against configured restrictions using URLInfo metadata.

        Args:
            url_info: URLInfo object containing file metadata

        Returns:
            Tuple of (is_valid, error_message)
        """
        if self.config.allowed_extensions and url_info.extension:
            ext = url_info.extension.lower()
            if ext not in self.config.allowed_extensions:
                return False, f"Extension '{ext}' not allowed"

        if self.config.validate_content_type and self.config.expected_content_types and url_info.mime_type:
            if not any(ct in url_info.mime_type for ct in self.config.expected_content_types):
                return False, f"Content type '{url_info.mime_type}' not allowed"

        return True, ""

    async def _get_resume_position(self, filepath: str) -> int:
        """
        Get the byte position to resume download from, considering server support.

        Args:
            filepath: Path to the partially downloaded file
            
        Returns:
            Byte position to resume from (0 if starting fresh)
        """
        if not self.config.resume_downloads or not self.url_info.supports_resume:
            return 0
        try:
            if await aiofiles.os.path.exists(filepath):
                stat = await aiofiles.os.stat(filepath)
                return stat.st_size
            return 0
        except OSError:
            return 0

    async def _make_request(self, headers: dict = None) -> aiohttp.ClientResponse:
        """
        Make HTTP request with configured options.
        
        Args:
            headers: Additional headers to include
            
        Returns:
            HTTP response object
        """
        request_headers = {**self.config.headers, **(headers or {})}
        return await self.session.get(self.url, headers=request_headers)

    async def download(self) -> typing.Optional[str]:
        """
        Execute the download with retry logic.
        
        Returns:
            Path to downloaded file, or None if cancelled

        Raises:
            Various exceptions after max retries exceeded
        """
        if not self.session:
            raise RuntimeError("Use async context manager or call __aenter__ first")

        for attempt in range(self.config.max_retries + 1):
            try:
                self.state = DownloadState.DOWNLOADING
                return await self._download_file()
            except Exception as e:
                if attempt == self.config.max_retries:
                    self.state = DownloadState.FAILED
                    raise e
                await asyncio.sleep(self.config.retry_delay * (2 ** attempt))

    async def _download_file(self) -> typing.Optional[str]:
        """
        Core download implementation using URLInfo for metadata.

        Returns:
            Path to downloaded file, or None if cancelled

        Raises:
            aiohttp.ClientResponseError: For HTTP errors
            ValueError: For validation errors
            FileExistsError: When file exists and overwrite is disabled
        """
        filename = self.url_info.filename or self._get_filename_from_response(await self._make_request())

        valid, error_msg = self._validate_file(self.url_info)
        if not valid:
            raise ValueError(error_msg)

        is_dir = await aiofiles.os.path.isdir(self.output_path)
        if is_dir:
            self.output_path = join(self.output_path, filename)

        if self.config.auto_create_dirs:
            try:
                await aiofiles.os.makedirs(dirname(self.output_path), exist_ok=True)
            except OSError as e:
                raise OSError(f"Failed to create directory {dirname(self.output_path)}: {e}")

            if await aiofiles.os.path.exists(self.output_path) and not self.config.overwrite_existing and self.resume_position == 0:
                raise FileExistsError(f"File already exists: {self.output_path}")

        self.resume_position = await self._get_resume_position(self.output_path)
        headers = {"Range": f"bytes={self.resume_position}-"} if self.resume_position > 0 else {}

        async with await self._make_request(headers) as response:
            if response.status not in (200, 206):
                raise aiohttp.ClientResponseError(
                    request_info=response.request_info,
                    history=response.history,
                    status=response.status
                )

            self.total_bytes = self.url_info.size or 0
            if self.total_bytes == 0:
                content_length = response.headers.get("Content-Length")
                if content_length:
                    self.total_bytes = int(content_length)
                    if response.status == 206:
                        content_range = response.headers.get("Content-Range", "")
                        if "/" in content_range:
                            self.total_bytes = int(content_range.split("/")[-1])

            mode = "ab" if self.resume_position > 0 else "wb"
            self.downloaded_bytes = self.resume_position

            async with aiofiles.open(self.output_path, mode) as f:
                async for chunk in response.content.iter_chunked(self.config.chunk_size):
                    if self.cancel_event.is_set():
                        self.state = DownloadState.CANCELLED
                        return None

                    while self.pause_event.is_set():
                        await asyncio.sleep(0.1)

                    await f.write(chunk)
                    self.downloaded_bytes += len(chunk)
                    self.progress(self.downloaded_bytes, self.total_bytes)

            self.state = DownloadState.COMPLETED
            return self.output_path

    def cancel(self):
        """
        Cancel the download.
        
        Sets the cancel event and cancels the current task if running.
        The download will stop at the next chunk boundary.
        """
        self.cancel_event.set()
        if self.current_task and not self.current_task.done():
            self.current_task.cancel()

    def pause(self):
        """
        Pause the download.
        
        The download will pause at the next chunk boundary.
        Call resume() to continue.
        """
        self.pause_event.set()
        self.state = DownloadState.PAUSED

    def resume(self):
        """
        Resume a paused download.
        
        Clears the pause event and updates state to downloading.
        """
        self.pause_event.clear()
        self.state = DownloadState.DOWNLOADING

    async def start(self) -> typing.Optional[str]:
        """
        Start the download process.
        
        Creates and manages the download task with proper cancellation handling.
        
        Returns:
            Path to downloaded file, or None if cancelled
            
        Example:
            >>> async with AsyncDownloader(url, path) as downloader:
            ...     result = await downloader.start()
            ...     if result:
            ...         print(f"Downloaded: {result}")
            ...     else:
            ...         print("Download was cancelled")
        """
        self.current_task = asyncio.create_task(self.download())
        try:
            return await self.current_task
        except asyncio.CancelledError:
            self.state = DownloadState.CANCELLED
            return None

class DownloadManager:
    """
    Manages multiple concurrent downloads with centralized control.
    
    Provides batch operations, concurrency limiting, and state tracking
    for multiple downloads. Useful for download queues and bulk operations.
    
    Args:
        max_concurrent: Maximum number of simultaneous downloads
        
    Example:
        >>> manager = DownloadManager(max_concurrent=3)
        >>> 
        >>> # Add downloads
        >>> id1 = await manager.add_download("https://example.com/file1.zip", "./downloads/")
        >>> id2 = await manager.add_download("https://example.com/file2.zip", "./downloads/")
        >>> 
        >>> # Start all downloads
        >>> results = await manager.start_all()
        >>> 
        >>> # Control individual downloads
        >>> manager.pause_download(id1)
        >>> manager.resume_download(id1)
        >>> manager.cancel_download(id2)
    """

    def __init__(self, max_concurrent: int = 5):
        """
        Initialize the download manager.

        Args:
            max_concurrent: Maximum number of downloads to run simultaneously
        """
        self.max_concurrent = max_concurrent
        self.downloads: dict[str, AsyncDownloader] = {}
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def add_download(
        self,
        url: str,
        output_path: str,
        config: DownloadConfig = None,
        progress_callback: typing.Optional[callable] = None,
        download_id: str = None
    ) -> str:
        """
        Add a download to the manager.
        
        Args:
            url: URL to download from
            output_path: Local path to save file
            config: Download configuration options
            progress_callback: Function to call with progress updates
            download_id: Unique identifier for this download (auto-generated if None)
            
        Returns:
            Unique download ID for managing this download
            
        Example:
            >>> config = DownloadConfig(max_retries=5)
            >>> download_id = await manager.add_download(
            ...     "https://example.com/large_file.zip",
            ...     "./downloads/",
            ...     config=config,
            ...     download_id="my_download"
            ... )
        """
        download_id = download_id or f"download_{len(self.downloads)}"

        downloader = AsyncDownloader(url, output_path, config, progress_callback)
        self.downloads[download_id] = downloader

        return download_id

    async def start_download(self, download_id: str) -> typing.Optional[str]:
        """
        Start a specific download by ID.
        
        Args:
            download_id: ID of the download to start
            
        Returns:
            Path to downloaded file, or None if cancelled
            
        Raises:
            ValueError: If download ID is not found
        """
        if download_id not in self.downloads:
            raise ValueError(f"Download {download_id} not found")

        downloader = self.downloads[download_id]

        async with self.semaphore:
            async with downloader:
                return await downloader.start()

    async def start_all(self) -> dict[str, typing.Optional[str]]:
        """
        Start all queued downloads concurrently.
        
        Downloads are limited by the max_concurrent setting.
        Failed downloads will have their exception as the value.
        
        Returns:
            Dictionary mapping download IDs to results (file paths or exceptions)
            
        Example:
            >>> results = await manager.start_all()
            >>> for download_id, result in results.items():
            ...     if isinstance(result, Exception):
            ...         print(f"Download {download_id} failed: {result}")
            ...     elif result:
            ...         print(f"Download {download_id} completed: {result}")
            ...     else:
            ...         print(f"Download {download_id} was cancelled")
        """
        tasks = []
        for download_id in self.downloads:
            task = asyncio.create_task(self.start_download(download_id))
            tasks.append((download_id, task))

        results = {}
        for download_id, task in tasks:
            try:
                results[download_id] = await task
            except Exception as e:
                results[download_id] = e

        return results

    def cancel_download(self, download_id: str):
        """
        Cancel a specific download.
        
        Args:
            download_id: ID of the download to cancel
        """
        if download_id in self.downloads:
            self.downloads[download_id].cancel()

    def pause_download(self, download_id: str):
        """
        Pause a specific download.
        
        Args:
            download_id: ID of the download to pause
        """
        if download_id in self.downloads:
            self.downloads[download_id].pause()

    def resume_download(self, download_id: str):
        """
        Resume a paused download.
        
        Args:
            download_id: ID of the download to resume
        """
        if download_id in self.downloads:
            self.downloads[download_id].resume()

    def get_download_state(self, download_id: str) -> DownloadState:
        """
        Get the current state of a download.
        
        Args:
            download_id: ID of the download to check
            
        Returns:
            Current download state, or None if download not found
        """
        if download_id in self.downloads:
            return self.downloads[download_id].state
        return DownloadState.UNDEFINED

    def remove_download(self, download_id: str):
        """
        Remove a download from the manager.
        
        Cancels the download if it's running, then removes it from tracking.
        
        Args:
            download_id: ID of the download to remove
        """
        if download_id in self.downloads:
            self.downloads[download_id].cancel()
            del self.downloads[download_id]