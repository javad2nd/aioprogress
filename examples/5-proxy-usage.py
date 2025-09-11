from aioprogress import AsyncDownloader, DownloadConfig
from aioprogress.events import DownloadTimeoutEvent, DownloadFailureEvent
import asyncio


async def main():
    """
    Proxy usage example demonstrating how to download files through
    HTTP proxies with authentication and custom headers.
    """
    # Configure proxy settings and download behavior
    config = DownloadConfig(
        proxy_url='http://proxy.example.com:8080',  # Replace with real proxy
        proxy_auth=('username', 'password'),  # Replace with real credentials
        proxy_headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
        max_retries=5,  # Increase retries for proxy connections
        retry_delay=2.0  # Longer delay between retries
    )

    async def on_timeout(event: DownloadTimeoutEvent):
        """Handle timeout events which may be more common with proxies"""
        print(f"Timeout occurred ({event.timeout_type}) on attempt {event.attempt}")
        if event.will_retry:
            print("Will retry with proxy...")

    async def on_failure(event: DownloadFailureEvent):
        """Handle failures that might be proxy-related"""
        print(f"Download failed through proxy: {event.error}")

    url = 'https://mirror.nforce.com/pub/speedtests/25mb.bin'

    # Create downloader with proxy configuration and event handling
    async with AsyncDownloader(
            url,
            "./downloads/",
            config,
            on_timeout=on_timeout,
            on_failure=on_failure
    ) as downloader:
        result = await downloader.start()
        if result:
            print(f"Successfully downloaded through proxy: {result}")
        else:
            print("Proxy download failed or was cancelled")


if __name__ == '__main__':
    asyncio.run(main())