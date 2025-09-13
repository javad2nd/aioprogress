from asyncio import Semaphore, gather, sleep
from time import time
from aiohttp import ClientSession, ClientTimeout, TCPConnector
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from statistics import mean, median


@dataclass
class SpeedResult:
    """
    Results from a speed test measurement.

    Attributes:
        url: The URL that was tested
        bytes_downloaded: Total bytes downloaded during the test
        duration: Time taken for the download in seconds
        speed_mbps: Download speed in megabits per second
        speed_kbps: Download speed in kilobits per second
        status_code: HTTP status code returned by the server
        error: Error message if the test failed, None if successful
    """
    url: str
    bytes_downloaded: int
    duration: float
    speed_mbps: float
    speed_kbps: float
    status_code: int
    error: Optional[str] = None


@dataclass
class SpeedTestSummary:
    """
    Summary statistics from multiple speed tests.

    Attributes:
        avg_speed_mbps: Average download speed across all successful tests
        median_speed_mbps: Median download speed across all successful tests
        max_speed_mbps: Maximum download speed recorded
        min_speed_mbps: Minimum download speed recorded
        total_bytes: Total bytes downloaded across all tests
        total_duration: Total time spent downloading across all tests
        success_count: Number of successful tests
        failure_count: Number of failed tests
        results: List of individual SpeedResult objects
    """
    avg_speed_mbps: float
    median_speed_mbps: float
    max_speed_mbps: float
    min_speed_mbps: float
    total_bytes: int
    total_duration: float
    success_count: int
    failure_count: int
    results: List[SpeedResult]


class AsyncDownloadSpeedTester:
    """
    An asynchronous download speed tester that measures internet connection speed
    by downloading data from specified URLs using aiohttp.

    This class provides comprehensive speed testing capabilities including single URL tests,
    multiple concurrent URL tests, duration-based testing with optional size limits,
    benchmark analysis, and continuous monitoring.

    The tester uses connection pooling and implements retry logic with exponential backoff
    for robust performance across various network conditions.
    """

    def __init__(
            self,
            timeout: int = 30,
            chunk_size: int = 8192,
            max_retries: int = 3,
            max_connections: int = 10,
            user_agent: str = "AsyncSpeedTester/1.0",
            retry_delay: float = 1.0
    ):
        """
        Initialize the AsyncDownloadSpeedTester.

        Args:
            timeout: Total timeout for HTTP requests in seconds
            chunk_size: Size of each chunk to read during download
            max_retries: Maximum number of retry attempts for failed requests
            max_connections: Maximum number of concurrent connections
            user_agent: User-Agent header to use for requests
            retry_delay: Base delay between retries in seconds (uses exponential backoff)
        """
        self.timeout = ClientTimeout(total=timeout)
        self.chunk_size = chunk_size
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.connector = TCPConnector(limit=max_connections)
        self.session_headers = {'User-Agent': user_agent}
        self._session: Optional[ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def _ensure_session(self):
        """Ensure aiohttp session is created and ready for use."""
        if self._session is None or self._session.closed:
            self._session = ClientSession(
                connector=self.connector,
                headers=self.session_headers,
                timeout=self.timeout
            )

    async def close(self):
        """Close the aiohttp session and connector to free resources."""
        if self._session and not self._session.closed:
            await self._session.close()
        if self.connector:
            await self.connector.close()

    async def test_single_url(
            self,
            url: str,
            max_size: Optional[int] = None,
            progress_callback: Optional[Callable[[int, float], None]] = None,
            headers: Optional[Dict[str, str]] = None
    ) -> Optional[SpeedResult]:
        """
        Test download speed from a single URL asynchronously.

        Downloads data from the specified URL and measures the transfer speed.
        Can optionally limit the download size and provide progress updates.

        Args:
            url: URL to download from
            max_size: Maximum bytes to download (None for entire file)
            progress_callback: Optional callback function called with (bytes_downloaded, current_speed_mbps)
            headers: Optional additional headers for the request

        Returns:
            SpeedResult object containing test results, or None if all retries failed
        """
        await self._ensure_session()

        for attempt in range(self.max_retries + 1):
            try:
                start_time = time()
                bytes_downloaded = 0

                request_headers = headers or {}

                async with self._session.get(url, headers=request_headers) as response:
                    response.raise_for_status()

                    async for chunk in response.content.iter_chunked(self.chunk_size):
                        bytes_downloaded += len(chunk)

                        if progress_callback:
                            current_duration = time() - start_time
                            if current_duration > 0:
                                current_speed = (bytes_downloaded * 8) / (current_duration * 1_000_000)
                                progress_callback(bytes_downloaded, current_speed)

                        if max_size and bytes_downloaded >= max_size:
                            break

                duration = time() - start_time
                speed_bps = bytes_downloaded * 8 / duration if duration > 0 else 0
                speed_mbps = speed_bps / 1_000_000
                speed_kbps = speed_bps / 1_000

                return SpeedResult(
                    url=url,
                    bytes_downloaded=bytes_downloaded,
                    duration=duration,
                    speed_mbps=speed_mbps,
                    speed_kbps=speed_kbps,
                    status_code=response.status
                )

            except Exception as e:
                if attempt == self.max_retries:
                    return SpeedResult(
                        url=url,
                        bytes_downloaded=0,
                        duration=0,
                        speed_mbps=0,
                        speed_kbps=0,
                        status_code=0,
                        error=str(e)
                    )
                await sleep(self.retry_delay * (2 ** attempt))

    async def test_duration_based(
            self,
            url: str,
            duration_seconds: int,
            progress_callback: Optional[Callable[[int, float, float], None]] = None,
            headers: Optional[Dict[str, str]] = None
    ) -> Optional[SpeedResult]:
        """
        Test download speed for a specific duration in seconds.

        Downloads data for the specified time period, measuring how much data
        can be transferred within that timeframe.

        Args:
            url: URL to download from
            duration_seconds: Duration to run the test in seconds
            progress_callback: Optional callback with (bytes_downloaded, current_speed_mbps, elapsed_time)
            headers: Optional additional headers for the request

        Returns:
            SpeedResult object with results from the duration-based test or None
        """
        await self._ensure_session()

        for attempt in range(self.max_retries + 1):
            try:
                start_time = time()
                bytes_downloaded = 0
                target_end_time = start_time + duration_seconds

                request_headers = headers or {}

                async with self._session.get(url, headers=request_headers) as response:
                    response.raise_for_status()

                    async for chunk in response.content.iter_chunked(self.chunk_size):
                        current_time = time()

                        if current_time >= target_end_time:
                            break

                        bytes_downloaded += len(chunk)

                        if progress_callback:
                            elapsed_time = current_time - start_time
                            if elapsed_time > 0:
                                current_speed = (bytes_downloaded * 8) / (elapsed_time * 1_000_000)
                                progress_callback(bytes_downloaded, current_speed, elapsed_time)

                actual_duration = time() - start_time
                speed_bps = bytes_downloaded * 8 / actual_duration if actual_duration > 0 else 0
                speed_mbps = speed_bps / 1_000_000
                speed_kbps = speed_bps / 1_000

                return SpeedResult(
                    url=url,
                    bytes_downloaded=bytes_downloaded,
                    duration=actual_duration,
                    speed_mbps=speed_mbps,
                    speed_kbps=speed_kbps,
                    status_code=response.status
                )

            except Exception as e:
                if attempt == self.max_retries:
                    return SpeedResult(
                        url=url,
                        bytes_downloaded=0,
                        duration=0,
                        speed_mbps=0,
                        speed_kbps=0,
                        status_code=0,
                        error=str(e)
                    )
                await sleep(self.retry_delay * (2 ** attempt))

    async def test_duration_with_size_limit(
            self,
            url: str,
            duration_seconds: int,
            max_size: Optional[int] = None,
            progress_callback: Optional[Callable[[int, float, float], None]] = None,
            headers: Optional[Dict[str, str]] = None
    ) -> Optional[SpeedResult]:
        """
        Test download speed for a specific duration with optional size limit.

        This method combines both time-based and size-based constraints, stopping
        when either the duration is reached OR max_size is downloaded, whichever
        comes first. This is ideal for consistent testing across different
        connection speeds.

        Args:
            url: URL to download from
            duration_seconds: Maximum duration to run the test in seconds
            max_size: Maximum bytes to download (None for no size limit)
            progress_callback: Optional callback with (bytes_downloaded, current_speed_mbps, elapsed_time)
            headers: Optional additional headers for the request

        Returns:
            SpeedResult object with results from the duration/size-limited test or None
        """
        await self._ensure_session()

        for attempt in range(self.max_retries + 1):
            try:
                start_time = time()
                bytes_downloaded = 0
                target_end_time = start_time + duration_seconds

                request_headers = headers or {}

                async with self._session.get(url, headers=request_headers) as response:
                    response.raise_for_status()

                    async for chunk in response.content.iter_chunked(self.chunk_size):
                        current_time = time()

                        if current_time >= target_end_time:
                            break

                        bytes_downloaded += len(chunk)

                        if max_size and bytes_downloaded >= max_size:
                            break

                        if progress_callback:
                            elapsed_time = current_time - start_time
                            if elapsed_time > 0:
                                current_speed = (bytes_downloaded * 8) / (elapsed_time * 1_000_000)
                                progress_callback(bytes_downloaded, current_speed, elapsed_time)

                actual_duration = time() - start_time
                speed_bps = bytes_downloaded * 8 / actual_duration if actual_duration > 0 else 0
                speed_mbps = speed_bps / 1_000_000
                speed_kbps = speed_bps / 1_000

                return SpeedResult(
                    url=url,
                    bytes_downloaded=bytes_downloaded,
                    duration=actual_duration,
                    speed_mbps=speed_mbps,
                    speed_kbps=speed_kbps,
                    status_code=response.status
                )

            except Exception as e:
                if attempt == self.max_retries:
                    return SpeedResult(
                        url=url,
                        bytes_downloaded=0,
                        duration=0,
                        speed_mbps=0,
                        speed_kbps=0,
                        status_code=0,
                        error=str(e)
                    )
                await sleep(self.retry_delay * (2 ** attempt))

    async def test_multiple_urls(
            self,
            urls: List[str],
            max_size: Optional[int] = None,
            progress_callback: Optional[Callable[[str, int, float], None]] = None,
            headers: Optional[Dict[str, str]] = None,
            semaphore_limit: Optional[int] = None
    ) -> List[SpeedResult]:
        """
        Test download speed from multiple URLs concurrently.

        Performs speed tests on multiple URLs simultaneously, allowing for
        comparison between different servers or endpoints.

        Args:
            urls: List of URLs to test
            max_size: Maximum bytes to download per URL
            progress_callback: Optional callback with (url, bytes_downloaded, current_speed_mbps)
            headers: Optional additional headers for requests
            semaphore_limit: Optional limit for concurrent downloads (defaults to len(urls))

        Returns:
            List of SpeedResult objects in the same order as input URLs
        """
        semaphore = Semaphore(semaphore_limit or len(urls))

        async def test_with_semaphore(url: str) -> SpeedResult:
            async with semaphore:
                callback = None
                if progress_callback:
                    callback = lambda b, s, u=url: progress_callback(u, b, s)
                return await self.test_single_url(url, max_size, callback, headers)

        tasks = [test_with_semaphore(url) for url in urls]
        return await gather(*tasks, return_exceptions=False)

    async def test_multiple_urls_duration_based(
            self,
            urls: List[str],
            duration_seconds: int,
            max_size: Optional[int] = None,
            progress_callback: Optional[Callable[[str, int, float, float], None]] = None,
            headers: Optional[Dict[str, str]] = None,
            semaphore_limit: Optional[int] = None
    ) -> List[SpeedResult]:
        """
        Test download speed from multiple URLs for a specific duration concurrently.

        Performs duration-based speed tests on multiple URLs simultaneously with
        optional size limits for comprehensive server comparison.

        Args:
            urls: List of URLs to test
            duration_seconds: Duration to run each test in seconds
            max_size: Maximum bytes to download per URL (None for no size limit)
            progress_callback: Optional callback with (url, bytes_downloaded, current_speed_mbps, elapsed_time)
            headers: Optional additional headers for requests
            semaphore_limit: Optional limit for concurrent downloads (defaults to len(urls))

        Returns:
            List of SpeedResult objects in the same order as input URLs
        """
        semaphore = Semaphore(semaphore_limit or len(urls))

        async def test_with_semaphore(url: str) -> SpeedResult:
            async with semaphore:
                callback = None
                if progress_callback:
                    callback = lambda b, s, e, u=url: progress_callback(u, b, s, e)
                return await self.test_duration_with_size_limit(url, duration_seconds, max_size, callback, headers)

        tasks = [test_with_semaphore(url) for url in urls]
        return await gather(*tasks, return_exceptions=False)

    async def benchmark_url(
            self,
            url: str,
            num_runs: int = 5,
            max_size: Optional[int] = None,
            delay_between_runs: float = 1.0,
            progress_callback: Optional[Callable[[int, int, float], None]] = None
    ) -> SpeedTestSummary:
        """
        Benchmark a single URL multiple times for statistical analysis.

        Performs multiple speed tests on the same URL to gather statistical
        data about connection performance, including average, median, min, and max speeds.

        Args:
            url: URL to benchmark
            num_runs: Number of test runs to perform
            max_size: Maximum bytes to download per run
            delay_between_runs: Delay between consecutive runs in seconds
            progress_callback: Optional callback with (run_number, bytes_downloaded, current_speed_mbps)

        Returns:
            SpeedTestSummary with statistical analysis of all runs
        """
        results = []

        for run in range(num_runs):
            callback = None
            if progress_callback:
                callback = lambda b, s, r=run: progress_callback(r + 1, b, s)

            result = await self.test_single_url(url, max_size, callback)
            results.append(result)

            if run < num_runs - 1:
                await sleep(delay_between_runs)

        return self._calculate_summary(results)

    async def benchmark_duration_based(
            self,
            url: str,
            duration_seconds: int,
            num_runs: int = 5,
            max_size: Optional[int] = None,
            delay_between_runs: float = 1.0,
            progress_callback: Optional[Callable[[int, int, float, float], None]] = None
    ) -> SpeedTestSummary:
        """
        Benchmark a single URL multiple times with duration-based testing for statistical analysis.

        Performs multiple duration-based speed tests with optional size limits to gather
        comprehensive statistical data about connection performance over time.

        Args:
            url: URL to benchmark
            duration_seconds: Duration for each test run in seconds
            num_runs: Number of test runs to perform
            max_size: Maximum bytes to download per run (None for no size limit)
            delay_between_runs: Delay between consecutive runs in seconds
            progress_callback: Optional callback with (run_number, bytes_downloaded, current_speed_mbps, elapsed_time)

        Returns:
            SpeedTestSummary with statistical analysis of all runs
        """
        results = []

        for run in range(num_runs):
            callback = None
            if progress_callback:
                callback = lambda b, s, e, r=run: progress_callback(r + 1, b, s, e)

            result = await self.test_duration_with_size_limit(url, duration_seconds, max_size, callback)
            results.append(result)

            if run < num_runs - 1:
                await sleep(delay_between_runs)

        return self._calculate_summary(results)

    async def continuous_monitoring(
            self,
            url: str,
            duration_seconds: int,
            interval_seconds: float = 10.0,
            max_size: Optional[int] = None,
            callback: Optional[Callable[[SpeedResult], None]] = None
    ) -> List[SpeedResult]:
        """
        Continuously monitor download speed for a specified duration.

        Performs repeated speed tests at regular intervals to monitor connection
        performance over time, useful for detecting network variations.

        Args:
            url: URL to monitor
            duration_seconds: Total monitoring duration in seconds
            interval_seconds: Interval between tests in seconds
            max_size: Maximum bytes to download per test
            callback: Optional callback called after each test with SpeedResult

        Returns:
            List of SpeedResult objects from all monitoring tests
        """
        results = []
        start_time = time()

        while time() - start_time < duration_seconds:
            result = await self.test_single_url(url, max_size)
            results.append(result)

            if callback:
                callback(result)

            await sleep(interval_seconds)

        return results

    def _calculate_summary(self, results: List[SpeedResult]) -> SpeedTestSummary:
        """
        Calculate summary statistics from multiple speed test results.

        Processes a list of SpeedResult objects to compute comprehensive
        statistics including averages, medians, and success/failure counts.
        """
        successful_results = [r for r in results if r.error is None]

        if not successful_results:
            return SpeedTestSummary(
                avg_speed_mbps=0,
                median_speed_mbps=0,
                max_speed_mbps=0,
                min_speed_mbps=0,
                total_bytes=0,
                total_duration=0,
                success_count=0,
                failure_count=len(results),
                results=results
            )

        speeds = [r.speed_mbps for r in successful_results]

        return SpeedTestSummary(
            avg_speed_mbps=mean(speeds),
            median_speed_mbps=median(speeds),
            max_speed_mbps=max(speeds),
            min_speed_mbps=min(speeds),
            total_bytes=sum(r.bytes_downloaded for r in successful_results),
            total_duration=sum(r.duration for r in successful_results),
            success_count=len(successful_results),
            failure_count=len(results) - len(successful_results),
            results=results
        )


async def quick_speed_test(url: str, max_size_mb: float = 10) -> SpeedResult:
    """
    Convenience function for quick speed test with size limit.

    Performs a simple speed test downloading up to the specified amount of data
    from a single URL.

    Args:
        url: URL to test
        max_size_mb: Maximum download size in MB

    Returns:
        SpeedResult object containing test results
    """
    async with AsyncDownloadSpeedTester() as tester:
        return await tester.test_single_url(url, int(max_size_mb * 1024 * 1024))


async def quick_duration_speed_test(
        url: str,
        duration_seconds: int = 30,
        max_size_mb: Optional[float] = None
) -> SpeedResult:
    """
    Convenience function for duration-based speed test with optional size limit.

    Performs a speed test that stops when either the specified duration is reached
    OR the maximum size is downloaded, whichever comes first. This approach provides
    consistent test durations while preventing excessive data usage.

    Args:
        url: URL to test
        duration_seconds: Maximum duration to run the test in seconds
        max_size_mb: Maximum download size in MB (None for no size limit)

    Returns:
        SpeedResult object containing test results
    """
    max_size = int(max_size_mb * 1024 * 1024) if max_size_mb else None

    async with AsyncDownloadSpeedTester() as tester:
        return await tester.test_duration_with_size_limit(url, duration_seconds, max_size)


async def compare_urls(urls: List[str], max_size_mb: float = 5) -> SpeedTestSummary:
    """
    Convenience function to compare speeds across multiple URLs.

    Tests multiple URLs concurrently and provides comparative statistics
    to help identify the fastest servers or endpoints.

    Args:
        urls: List of URLs to compare
        max_size_mb: Maximum download size per URL in MB

    Returns:
        SpeedTestSummary with comparison results across all URLs
    """
    async with AsyncDownloadSpeedTester() as tester:
        results = await tester.test_multiple_urls(urls, int(max_size_mb * 1024 * 1024))
        return tester._calculate_summary(results)


async def compare_urls_duration_based(
        urls: List[str],
        duration_seconds: int = 30,
        max_size_mb: Optional[float] = None
) -> SpeedTestSummary:
    """
    Convenience function to compare speeds across multiple URLs with duration-based testing.

    Tests multiple URLs concurrently using duration-based testing with optional size limits,
    providing comprehensive comparative analysis of different servers.

    Args:
        urls: List of URLs to compare
        duration_seconds: Duration to run each test in seconds
        max_size_mb: Maximum download size per URL in MB (None for no size limit)

    Returns:
        SpeedTestSummary with comparison results across all URLs
    """
    max_size = int(max_size_mb * 1024 * 1024) if max_size_mb else None
    async with AsyncDownloadSpeedTester() as tester:
        results = await tester.test_multiple_urls_duration_based(urls, duration_seconds, max_size)
        return tester._calculate_summary(results)
