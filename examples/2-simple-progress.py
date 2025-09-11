from aioprogress import AsyncDownloader, ProgressData
from aioprogress.events import DownloadStartEvent, DownloadCompleteEvent
import asyncio


async def main():
    """
    Progress tracking example showing how to monitor download progress
    with custom progress callbacks and event handlers.
    """

    def show_progress(progress: ProgressData):
        """Display download progress with speed and ETA information"""
        print(f"{progress} | {progress.speed_human_readable} | ETA: {progress.eta_human_readable}")

    async def on_start(event: DownloadStartEvent):
        """Handle download start event"""
        print(f"Starting download of {event.total_bytes} bytes from {event.url}")

    async def on_complete(event: DownloadCompleteEvent):
        """Handle download completion event"""
        print(f"Download completed in {event.duration:.2f}s - File size: {event.file_size} bytes")

    url = 'https://mirror.nforce.com/pub/speedtests/25mb.bin'

    # Create downloader with progress callback and event handlers
    async with AsyncDownloader(
            url,
            "./downloads/",
            progress_callback=show_progress,
            on_start=on_start,
            on_complete=on_complete
    ) as downloader:
        filename = await downloader.start()
        if filename:
            print(f"File saved at: {filename}")
        else:
            print("Download failed or cancelled")


if __name__ == '__main__':
    asyncio.run(main())
