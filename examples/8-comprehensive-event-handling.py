from aioprogress import AsyncDownloader, DownloadConfig, ProgressData
from aioprogress.events import (
    DownloadStartEvent, DownloadCancelledEvent, DownloadCompleteEvent, DownloadFailureEvent,
    DownloadPausedEvent, DownloadResumedEvent,
    DownloadValidationEvent, DownloadRetryEvent, DownloadTimeoutEvent
)

import asyncio
import time


async def main():
    """
    Comprehensive example showcasing all available event handlers
    and how they can be used for monitoring and logging download activities.
    """

    # Configure download with validation and retry settings
    config = DownloadConfig(
        max_retries=3,
        retry_delay=1.0,
        validate_content_type=True,
        expected_content_types={'application/octet-stream', 'application/binary'},
        chunk_size=16384  # 16KB chunks
    )

    async def on_start(event: DownloadStartEvent):
        """Handle download start with detailed logging"""
        print(f"🚀 Download started: {event.url}")
        print(f"📁 Output path: {event.output_path}")
        print(f"📊 Total size: {event.total_bytes:,} bytes")
        print(f"⏰ Started at: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(event.timestamp))}")

    async def on_complete(event: DownloadCompleteEvent):
        """Handle successful completion with statistics"""
        print(f"✅ Download completed successfully!")
        print(f"📁 File saved: {event.output_path}")
        print(f"📊 File size: {event.file_size:,} bytes")
        print(f"⏱️ Duration: {event.duration:.2f} seconds")
        avg_speed = event.file_size / event.duration if event.duration > 0 else 0
        print(f"🚀 Average speed: {avg_speed / 1024 / 1024:.2f} MB/s")

    async def on_failure(event: DownloadFailureEvent):
        """Handle download failures with error details"""
        print(f"❌ Download failed on attempt {event.attempt}")
        print(f"🚫 Error: {event.error}")
        print(f"🔄 Will retry: {'Yes' if event.will_retry else 'No'}")

    async def on_timeout(event: DownloadTimeoutEvent):
        """Handle timeout events with specific timeout type"""
        print(f"⏰ Download timeout occurred!")
        print(f"🔍 Timeout type: {event.timeout_type}")
        print(f"🔄 Attempt: {event.attempt}")
        print(f"🔄 Will retry: {'Yes' if event.will_retry else 'No'}")

    async def on_retry(event: DownloadRetryEvent):
        """Handle retry attempts with delay information"""
        print(f"🔄 Retrying download...")
        print(f"📊 Attempt: {event.attempt}/{event.max_attempts}")
        print(f"⏱️ Delay: {event.delay} seconds")
        print(f"🚫 Last error: {event.last_error}")

    async def on_cancel(event: DownloadCancelledEvent):
        """Handle download cancellation"""
        print(f"🛑 Download cancelled!")
        print(f"📝 Reason: {event.reason}")
        print(f"⏰ Cancelled at: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(event.timestamp))}")

    async def on_pause(event: DownloadPausedEvent):
        """Handle download pause events"""
        print(f"⏸️ Download paused")
        print(f"📊 Downloaded so far: {event.downloaded_bytes:,} bytes")

    async def on_resume(event: DownloadResumedEvent):
        """Handle download resume events"""
        print(f"▶️ Download resumed")
        print(f"📊 Resuming from: {event.resume_position:,} bytes")

    async def on_validation(event: DownloadValidationEvent):
        """Handle file validation events"""
        status = "✅ Passed" if event.is_valid else "❌ Failed"
        print(f"🔍 Validation ({event.validation_type}): {status}")
        if not event.is_valid:
            print(f"📝 Message: {event.message}")

    def progress_callback(progress: ProgressData):
        """Simple progress display"""
        print(f"📥 {progress} | 🚀 {progress.speed_human_readable} | ⏰ ETA: {progress.eta_human_readable}")

    url = 'https://mirror.nforce.com/pub/speedtests/25mb.bin'

    # Create downloader with all event handlers
    async with AsyncDownloader(
            url,
            './downloads/',
            config=config,
            progress_callback=progress_callback,
            on_start=on_start,
            on_complete=on_complete,
            on_failure=on_failure,
            on_timeout=on_timeout,
            on_retry=on_retry,
            on_cancel=on_cancel,
            on_pause=on_pause,
            on_resume=on_resume,
            on_validation=on_validation
    ) as downloader:

        # Start download and handle result
        result = await downloader.start()

        if result:
            print(f"\nAll done! File available at: {result}")
        else:
            print("\nDownload did not complete successfully")


if __name__ == '__main__':
    asyncio.run(main())
