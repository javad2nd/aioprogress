import asyncio
import typing
import mimetypes
from urllib.parse import urlparse, unquote
from re import search, IGNORECASE
from os.path import basename, splitext
from dataclasses import dataclass, field
from enum import Enum
import aiohttp


class FetchMethod(Enum):
    """
    Enumeration of different methods used to fetch URL information.

    Methods:
        HEAD_REQUEST: Using HTTP HEAD request (fastest, least data)
        PARTIAL_GET: Using HTTP GET with Range header (small download)
        CONTENT_DISPOSITION: From Content-Disposition header
        URL_PARSING: From URL path analysis
        CONTENT_SNIFFING: From actual content analysis
        MIME_DATABASE: From system MIME type database
    """
    HEAD_REQUEST = "head_request"
    PARTIAL_GET = "partial_get"
    CONTENT_DISPOSITION = "content_disposition"
    URL_PARSING = "url_parsing"
    CONTENT_SNIFFING = "content_sniffing"
    MIME_DATABASE = "mime_database"


@dataclass
class URLInfo:
    """
    Comprehensive information about a URL's target resource.

    Attributes:
        url: Original URL
        filename: Detected filename
        size: File size in bytes (None if unknown)
        extension: File extension without dot
        mime_type: MIME type (e.g., 'video/mp4')
        content_type: Full Content-Type header value
        supports_resume: Whether server supports partial content requests
        last_modified: Last-Modified header value
        etag: ETag header value
        server: Server header value
        content_encoding: Content-Encoding header value
        fetch_methods: Set of methods used to gather this information
        headers: All response headers received
        redirect_url: Final URL after redirects (if any)
        status_code: HTTP status code received
    """
    url: str
    filename: typing.Optional[str] = None
    size: typing.Optional[int] = None
    extension: typing.Optional[str] = None
    mime_type: typing.Optional[str] = None
    content_type: typing.Optional[str] = None
    supports_resume: bool = False
    last_modified: typing.Optional[str] = None
    etag: typing.Optional[str] = None
    server: typing.Optional[str] = None
    content_encoding: typing.Optional[str] = None
    fetch_methods: set = field(default_factory=set)
    headers: dict = field(default_factory=dict)
    redirect_url: typing.Optional[str] = None
    status_code: typing.Optional[int] = None


@dataclass
class FetchConfig:
    """
    Configuration for URL information fetching behavior.

    Attributes:
        timeout: HTTP request timeout
        max_redirects: Maximum number of redirects to follow
        user_agent: User-Agent header to send
        headers: Additional headers to send
        use_head_request: Whether to try HEAD request first
        use_partial_get: Whether to try partial GET request
        partial_size: Size of partial content to fetch for analysis (bytes)
        enable_content_sniffing: Whether to analyze actual content
        validate_ssl: Whether to validate SSL certificates
        proxy_url: HTTP/HTTPS/SOCKS proxy URL
        proxy_auth: Proxy authentication tuple
        trust_env: Whether to trust environment proxy settings
        libmagic_available: Whether python-magic is available for content sniffing

    Example:
        >>> config = FetchConfig(
        ...     timeout=aiohttp.ClientTimeout(total=30),
        ...     user_agent='URLInfoFetcher/1.0',
        ...     use_head_request=True,
        ...     enable_content_sniffing=True,
        ...     partial_size=8192
        ... )
    """
    timeout: aiohttp.ClientTimeout = field(default_factory=lambda: aiohttp.ClientTimeout(total=30))
    max_redirects: int = 10
    user_agent: str = "URLInfoFetcher/1.0"
    headers: dict = field(default_factory=dict)
    use_head_request: bool = True
    use_partial_get: bool = True
    partial_size: int = 8192
    enable_content_sniffing: bool = True
    validate_ssl: bool = True
    proxy_url: typing.Optional[str] = None
    proxy_auth: typing.Optional[typing.Tuple[str, str]] = None
    trust_env: bool = True
    libmagic_available: bool = field(init=False)

    def __post_init__(self):
        """Check if python-magic is available for content sniffing."""
        try:
            import magic
            self.libmagic_available = True
        except ImportError:
            self.libmagic_available = False


class URLInfoFetcher:
    """
    High-performance async URL information fetcher with multiple detection methods.

    Fetches comprehensive metadata about URLs including filename, size, MIME type,
    and more using various detection strategies for maximum accuracy and fallback support.

    Detection Methods:
    1. HTTP HEAD request - Fast, minimal data transfer
    2. Partial GET request - Small content sample for analysis
    3. Content-Disposition header parsing
    4. URL path analysis and parsing
    5. Content sniffing with libmagic (if available)
    6. System MIME type database lookup

    Args:
        config: Configuration options for fetching behavior

    Example:
        >>> # Basic usage
        >>> fetcher = URLInfoFetcher()
        >>> async with fetcher:
        ...     info = await fetcher.fetch_info("https://example.com/video.mp4")
        ...     print(f"File: {info.filename}")
        ...     print(f"Size: {info.size} bytes")
        ...     print(f"Type: {info.mime_type}")

        >>> # With custom configuration
        >>> config = FetchConfig(
        ...     use_head_request=True,
        ...     enable_content_sniffing=True,
        ...     proxy_url='http://proxy.example.com:8080'
        ... )
        >>> fetcher = URLInfoFetcher(config)
        >>> async with fetcher:
        ...     info = await fetcher.fetch_info(url)

        >>> # Batch processing
        >>> urls = ["https://example.com/file1.zip", "https://example.com/file2.pdf"]
        >>> async with fetcher:
        ...     results = await fetcher.fetch_multiple(urls)
        ...     for url, info in results.items():
        ...         print(f"{url}: {info.filename} ({info.size} bytes)")
    """

    def __init__(self, config: FetchConfig = None):
        """
        Initialize the URL info fetcher.

        Args:
            config: Configuration options. Uses defaults if None.
        """
        self.config = config or FetchConfig()
        self.session: aiohttp.ClientSession = None

    async def __aenter__(self):
        """Async context manager entry. Sets up HTTP session with proxy support."""
        connector_kwargs = {'ssl': self.config.validate_ssl}

        if self.config.proxy_url:
            connector = aiohttp.TCPConnector(**connector_kwargs)

            session_kwargs = {
                'connector': connector,
                'timeout': self.config.timeout,
                'headers': {**self.config.headers, 'User-Agent': self.config.user_agent},
                'trust_env': self.config.trust_env
            }

            if self.config.proxy_url.startswith(('http://', 'https://')):
                session_kwargs['proxy'] = self.config.proxy_url

                if self.config.proxy_auth:
                    session_kwargs['proxy_auth'] = aiohttp.BasicAuth(
                        self.config.proxy_auth[0],
                        self.config.proxy_auth[1]
                    )

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
                    raise ImportError("aiohttp-socks is required for SOCKS proxy support")
            else:
                raise ValueError(f"Unsupported proxy protocol: {self.config.proxy_url}")
        else:
            connector = aiohttp.TCPConnector(**connector_kwargs)
            session_kwargs = {
                'connector': connector,
                'timeout': self.config.timeout,
                'headers': {**self.config.headers, 'User-Agent': self.config.user_agent},
                'trust_env': self.config.trust_env
            }

        self.session = aiohttp.ClientSession(**session_kwargs)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit. Cleans up HTTP session."""
        if self.session:
            await self.session.close()

    def _extract_filename_from_url(self, url: str) -> typing.Optional[str]:
        """
        Extract filename from URL path.

        Args:
            url: URL to analyze

        Returns:
            Extracted filename or None if not found
        """
        try:
            parsed = urlparse(url)
            path = unquote(parsed.path)
            filename = basename(path)

            if filename and '.' in filename and len(filename) < 256:
                return filename
        except Exception:
            pass
        return None

    def _extract_filename_from_disposition(self, disposition: str) -> typing.Optional[str]:
        """
        Extract filename from Content-Disposition header.

        Args:
            disposition: Content-Disposition header value

        Returns:
            Extracted filename or None if not found
        """
        if not disposition:
            return None

        patterns = [
            r"filename\*=UTF-8''([^;]+)",
            r"filename\*=([^;]+)",
            r'filename="([^"]+)"',
            r"filename=([^;]+)",
        ]

        for pattern in patterns:
            if match := search(pattern, disposition, IGNORECASE):
                filename = unquote(match.group(1).strip())
                if filename:
                    return filename

        return None

    def _get_extension_from_filename(self, filename: str) -> typing.Optional[str]:
        """
        Extract file extension from filename.

        Args:
            filename: Filename to analyze

        Returns:
            File extension without dot, or None if not found
        """
        if not filename:
            return None

        _, ext = splitext(filename.lower())
        return ext[1:] if ext else None

    def _get_mime_from_extension(self, extension: str) -> typing.Optional[str]:
        """
        Get MIME type from file extension using system database.

        Args:
            extension: File extension (without dot)

        Returns:
            MIME type or None if not found
        """
        if not extension:
            return None

        mime_type, _ = mimetypes.guess_type(f"file.{extension}")
        return mime_type

    def _parse_content_type(self, content_type: str) -> typing.Tuple[typing.Optional[str], typing.Optional[str]]:
        """
        Parse Content-Type header to extract MIME type and charset.

        Args:
            content_type: Content-Type header value

        Returns:
            Tuple of (mime_type, charset)
        """
        if not content_type:
            return None, None

        parts = content_type.split(';')
        mime_type = parts[0].strip().lower()
        charset = None

        for part in parts[1:]:
            if 'charset=' in part:
                charset = part.split('charset=')[1].strip()
                break

        return mime_type, charset

    def _analyze_content_with_magic(self, content: bytes) -> typing.Tuple[typing.Optional[str], typing.Optional[str]]:
        """
        Analyze content using python-magic library.

        Args:
            content: Binary content to analyze

        Returns:
            Tuple of (mime_type, description)
        """
        if not self.config.libmagic_available or not content:
            return None, None

        try:
            import magic
            mime_type = magic.from_buffer(content, mime=True)
            description = magic.from_buffer(content)

            return mime_type, description
        except Exception:
            return None, None

    def _guess_filename_from_mime(self, mime_type: str, url: str) -> typing.Optional[str]:
        """
        Generate a reasonable filename based on MIME type and URL.

        Args:
            mime_type: MIME type of the content
            url: Original URL

        Returns:
            Generated filename or None
        """
        if not mime_type:
            return None

        mime_extensions = {
            'text/html': 'html',
            'text/plain': 'txt',
            'application/json': 'json',
            'application/pdf': 'pdf',
            'application/zip': 'zip',
            'image/jpeg': 'jpg',
            'image/png': 'png',
            'image/gif': 'gif',
            'video/mp4': 'mp4',
            'video/webm': 'webm',
            'audio/mpeg': 'mp3',
            'audio/wav': 'wav',
        }

        extension = mime_extensions.get(mime_type.lower())
        if extension:
            parsed = urlparse(url)
            base_name = basename(parsed.path) or "download"

            if '.' in base_name:
                base_name = splitext(base_name)[0]

            return f"{base_name}.{extension}"

        return None

    async def _try_head_request(self, url: str) -> typing.Tuple[URLInfo, bool]:
        """
        Try to fetch URL info using HTTP HEAD request.

        Args:
            url: URL to analyze

        Returns:
            Tuple of (URLInfo object, success_flag)
        """
        info = URLInfo(url=url)

        try:
            async with self.session.head(url, allow_redirects=True) as response:
                info.status_code = response.status
                info.headers = dict(response.headers)
                info.redirect_url = str(response.url) if response.url != url else None

                if response.status >= 400:
                    return info, False

                info.size = int(response.headers.get('Content-Length', 0)) or None
                info.content_type = response.headers.get('Content-Type')
                info.mime_type, _ = self._parse_content_type(info.content_type)
                info.last_modified = response.headers.get('Last-Modified')
                info.etag = response.headers.get('ETag')
                info.server = response.headers.get('Server')
                info.content_encoding = response.headers.get('Content-Encoding')
                info.supports_resume = 'bytes' in response.headers.get('Accept-Ranges', '')

                disposition = response.headers.get('Content-Disposition')
                if disposition:
                    info.filename = self._extract_filename_from_disposition(disposition)
                    info.fetch_methods.add(FetchMethod.CONTENT_DISPOSITION)

                info.fetch_methods.add(FetchMethod.HEAD_REQUEST)
                return info, True

        except Exception:
            return info, False

    async def _try_partial_get(self, url: str, existing_info: URLInfo) -> typing.Tuple[URLInfo, bool]:
        """
        Try to fetch additional info using partial GET request.

        Args:
            url: URL to analyze
            existing_info: Previously gathered information

        Returns:
            Tuple of (updated URLInfo object, success_flag)
        """
        headers = {'Range': f'bytes=0-{self.config.partial_size - 1}'}

        try:
            async with self.session.get(url, headers=headers, allow_redirects=True) as response:
                if response.status not in (200, 206):
                    return existing_info, False

                existing_info.headers.update(dict(response.headers))
                existing_info.redirect_url = str(response.url) if response.url != url else None

                content = await response.read()

                if content and self.config.enable_content_sniffing:
                    mime_type, description = self._analyze_content_with_magic(content)
                    if mime_type and not existing_info.mime_type:
                        existing_info.mime_type = mime_type
                        existing_info.fetch_methods.add(FetchMethod.CONTENT_SNIFFING)

                if response.status == 206:
                    content_range = response.headers.get('Content-Range', '')
                    if '/' in content_range:
                        total_size = content_range.split('/')[-1]
                        if total_size.isdigit():
                            existing_info.size = int(total_size)

                existing_info.fetch_methods.add(FetchMethod.PARTIAL_GET)
                return existing_info, True

        except Exception:
            return existing_info, False

    async def fetch_info(self, url: str) -> URLInfo:
        """
        Fetch comprehensive information about a URL.

        Uses multiple detection methods in order of efficiency and reliability:
        1. HTTP HEAD request for headers
        2. URL parsing for filename extraction
        3. Partial GET request for content analysis
        4. MIME database lookup

        Args:
            url: URL to analyze

        Returns:
            URLInfo object with all gathered information

        Raises:
            RuntimeError: If no session is available (use async context manager)

        Example:
            >>> async with fetcher:
            ...     info = await fetcher.fetch_info("https://example.com/video.mp4")
            ...     print(f"Filename: {info.filename}")
            ...     print(f"Size: {info.size} bytes")
            ...     print(f"MIME type: {info.mime_type}")
            ...     print(f"Supports resume: {info.supports_resume}")
        """
        if not self.session:
            raise RuntimeError("Use async context manager or call __aenter__ first")

        info = URLInfo(url=url)

        if self.config.use_head_request:
            info, success = await self._try_head_request(url)
            if not success and info.status_code and info.status_code >= 400:
                return info

        url_filename = self._extract_filename_from_url(info.redirect_url or url)
        if url_filename and not info.filename:
            info.filename = url_filename
            info.fetch_methods.add(FetchMethod.URL_PARSING)

        if self.config.use_partial_get:
            info, _ = await self._try_partial_get(info.redirect_url or url, info)

        if info.filename and not info.extension:
            info.extension = self._get_extension_from_filename(info.filename)

        if info.extension and not info.mime_type:
            mime_from_ext = self._get_mime_from_extension(info.extension)
            if mime_from_ext:
                info.mime_type = mime_from_ext
                info.fetch_methods.add(FetchMethod.MIME_DATABASE)

        if not info.filename and info.mime_type:
            info.filename = self._guess_filename_from_mime(info.mime_type, url)
            if info.filename:
                info.extension = self._get_extension_from_filename(info.filename)

        return info

    async def fetch_multiple(self, urls: typing.List[str], max_concurrent: int = 10) -> typing.Dict[str, URLInfo]:
        """
        Fetch information for multiple URLs concurrently.

        Args:
            urls: List of URLs to analyze
            max_concurrent: Maximum number of concurrent requests

        Returns:
            Dictionary mapping URLs to their URLInfo objects

        Example:
            >>> urls = [
            ...     "https://example.com/video.mp4",
            ...     "https://example.com/document.pdf",
            ...     "https://example.com/archive.zip"
            ... ]
            >>> async with fetcher:
            ...     results = await fetcher.fetch_multiple(urls, max_concurrent=5)
            ...     for url, info in results.items():
            ...         print(f"{info.filename}: {info.size} bytes ({info.mime_type})")
        """
        if not self.session:
            raise RuntimeError("Use async context manager or call __aenter__ first")

        semaphore = asyncio.Semaphore(max_concurrent)

        async def fetch_with_semaphore(url: str) -> typing.Tuple[str, URLInfo]:
            async with semaphore:
                info = await self.fetch_info(url)
                return url, info

        tasks = [fetch_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        info_dict = {}
        for result in results:
            if isinstance(result, Exception):
                error_info = URLInfo(url="unknown")
                error_info.fetch_methods.add(FetchMethod.HEAD_REQUEST)
                info_dict["error"] = error_info
            else:
                url, info = result
                info_dict[url] = info

        return info_dict

    async def validate_url(self, url: str) -> bool:
        """
        Quick validation to check if URL is accessible.

        Args:
            url: URL to validate

        Returns:
            True if URL is accessible, False otherwise

        Example:
            >>> async with fetcher:
            ...     is_valid = await fetcher.validate_url("https://example.com/file.zip")
            ...     if is_valid:
            ...         print("URL is accessible")
            ...     else:
            ...         print("URL is not accessible")
        """
        try:
            async with self.session.head(url, allow_redirects=True) as response:
                return response.status < 400
        except Exception:
            return False


async def get_url_info(url: str, config: FetchConfig = None) -> URLInfo:
    """
    Convenience function to fetch URL info without managing context.

    Args:
        url: URL to analyze
        config: Optional configuration

    Returns:
        URLInfo object with gathered information

    Example:
        >>> info = await get_url_info("https://example.com/video.mp4")
        >>> print(f"File: {info.filename} ({info.size} bytes)")
    """
    fetcher = URLInfoFetcher(config)
    async with fetcher:
        return await fetcher.fetch_info(url)


async def get_multiple_url_info(urls: typing.List[str], config: FetchConfig = None) -> typing.Dict[str, URLInfo]:
    """
    Convenience function to fetch multiple URL info without managing context.

    Args:
        urls: List of URLs to analyze
        config: Optional configuration

    Returns:
        Dictionary mapping URLs to URLInfo objects

    Example:
        >>> urls = ["https://example.com/file1.zip", "https://example.com/file2.pdf"]
        >>> results = await get_multiple_url_info(urls)
        >>> for url, info in results.items():
        ...     print(f"{url}: {info.filename}")
    """
    fetcher = URLInfoFetcher(config)
    async with fetcher:
        return await fetcher.fetch_multiple(urls)