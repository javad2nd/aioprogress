from aioprogress import DownloadManager, DownloadConfig
from aioprogress.events import DownloadStartEvent, DownloadCompleteEvent, DownloadFailureEvent
import asyncio


async def main():
    """
    Concurrent download example using DownloadManager to handle multiple
    downloads simultaneously with individual event handlers.
    """
    # Create download manager with concurrency limit
    manager = DownloadManager(max_concurrent=3)

    urls = [
        'https://mirror.nforce.com/pub/speedtests/25mb.bin',
        'https://mirror.nforce.com/pub/speedtests/10mb.bin',
        'https://mirror.nforce.com/pub/speedtests/50mb.bin',
        'https://mirror.nforce.com/pub/speedtests/100mb.bin',
    ]

    async def on_start(event: DownloadStartEvent):
        """Handle download start for any download"""
        filename = event.url.split('/')[-1]
        print(f"Started downloading {filename}")

    async def on_complete(event: DownloadCompleteEvent):
        """Handle download completion for any download"""
        filename = event.url.split('/')[-1]
        print(f"Completed {filename} in {event.duration:.2f}s")

    async def on_failure(event: DownloadFailureEvent):
        """Handle download failures with detailed error information"""
        filename = event.url.split('/')[-1]
        print(f"Failed to download {filename}: {event.error}")

    # Add downloads with event handlers and configuration
    for url in urls:
        config = DownloadConfig(progress_interval=1.0)
        await manager.add_download(
            url,
            "./downloads/",
            config,
            on_start=on_start,
            on_complete=on_complete,
            on_failure=on_failure
        )

    print(f"Starting {len(urls)} concurrent downloads...")

    # Start all downloads and wait for completion
    results = await manager.start_all()

    # Report final results
    for download_id, result in results.items():
        if isinstance(result, Exception):
            print(f"❌ {download_id} failed: {result}")
        elif result:
            print(f"✅ {download_id} completed: {result}")
        else:
            print(f"⏸️ {download_id} was cancelled")


if __name__ == '__main__':
    asyncio.run(main())
