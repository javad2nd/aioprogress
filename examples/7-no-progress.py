from aioprogress import AsyncDownloader, Progress
from aioprogress.events import DownloadStartEvent, DownloadCompleteEvent, DownloadFailureEvent
import asyncio


async def main():
    """
    No progress example showing how to disable progress reporting
    while still using event handlers for important lifecycle events.
    """

    async def on_start(event: DownloadStartEvent):
        """Handle download start without progress updates"""
        print(f"Starting silent download of {event.total_bytes} bytes")

    async def on_complete(event: DownloadCompleteEvent):
        """Handle completion with final statistics"""
        print(f"Silent download completed: {event.file_size} bytes in {event.duration:.2f}s")

    async def on_failure(event: DownloadFailureEvent):
        """Handle any failures during silent download"""
        print(f"Silent download failed: {event.error}")

    url = 'https://mirror.nforce.com/pub/speedtests/25mb.bin'

    # Disable progress reporting but keep event handlers for important events
    async with AsyncDownloader(
            url,
            './downloads',
            progress_callback=Progress.NONE,  # No progress updates
            on_start=on_start,
            on_complete=on_complete,
            on_failure=on_failure
    ) as downloader:
        filename = await downloader.start()
        print(f"Final result: {filename}")


if __name__ == '__main__':
    asyncio.run(main())
