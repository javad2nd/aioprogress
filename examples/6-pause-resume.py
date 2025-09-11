from aioprogress import AsyncDownloader
from aioprogress.events import DownloadPausedEvent, DownloadResumedEvent, DownloadCompleteEvent
import asyncio


async def main():
    """
    Pause and resume example demonstrating download control capabilities
    with event handlers for pause/resume operations.
    """

    async def on_pause(event: DownloadPausedEvent):
        """Handle download pause event"""
        print(f"Download paused at {event.downloaded_bytes} bytes")

    async def on_resume(event: DownloadResumedEvent):
        """Handle download resume event"""
        print(f"Download resumed from position {event.resume_position}")

    async def on_complete(event: DownloadCompleteEvent):
        """Handle download completion"""
        print(f"Download completed - took {event.duration:.2f}s total")

    url = 'https://mirror.nforce.com/pub/speedtests/25mb.bin'

    # Create downloader with pause/resume event handlers
    async with AsyncDownloader(
            url,
            './downloads/',
            on_pause=on_pause,
            on_resume=on_resume,
            on_complete=on_complete
    ) as downloader:
        # Start download in background task
        task = asyncio.create_task(downloader.start())

        # Simulate user interaction after 2 seconds
        await asyncio.sleep(2)
        print("Pausing download...")
        await downloader.pause()

        # Keep paused for 3 seconds
        await asyncio.sleep(3)
        print("Resuming download...")
        await downloader.resume()

        # Wait for completion
        result = await task
        print(f"✅ Final result: {result}")


if __name__ == '__main__':
    asyncio.run(main())
