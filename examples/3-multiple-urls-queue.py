from aioprogress import AsyncDownloader
from aioprogress.events import DownloadFailureEvent, DownloadRetryEvent
import asyncio


async def main():
    """
    Sequential download example showing how to download multiple files
    one after another with event handling for each download.
    """
    urls = [
        'https://mirror.nforce.com/pub/speedtests/25mb.bin',
        'https://mirror.nforce.com/pub/speedtests/10mb.bin',
    ]

    async def on_failure(event: DownloadFailureEvent):
        """Handle download failure with retry information"""
        print(f"Download failed on attempt {event.attempt}: {event.error}")
        if event.will_retry:
            print("Will retry download...")

    async def on_retry(event: DownloadRetryEvent):
        """Handle retry attempts with delay information"""
        print(f"Retrying download (attempt {event.attempt}/{event.max_attempts}) in {event.delay}s")

    for i, url in enumerate(urls, 1):
        print(f"Starting download {i}/{len(urls)}")

        # Create downloader with comprehensive error handling
        async with AsyncDownloader(
                url,
                f"./downloads/{i}.bin",
                on_failure=on_failure,
                on_retry=on_retry
        ) as downloader:
            result = await downloader.start()
            print(f"Completed: {result}")


if __name__ == '__main__':
    asyncio.run(main())