from aioprogress import DownloadManager, DownloadConfig
import asyncio


async def main():
    manager = DownloadManager(max_concurrent=3)

    urls = [
        'https://mirror.nforce.com/pub/speedtests/25mb.bin',
        'https://mirror.nforce.com/pub/speedtests/10mb.bin',
        'https://mirror.nforce.com/pub/speedtests/50mb.bin',
        'https://mirror.nforce.com/pub/speedtests/100mb.bin',
    ]

    for url in urls:
        config = DownloadConfig(progress_interval=1.0)
        await manager.add_download(
            url,
            f"./downloads/",
            config,
        )

    print(f"Starting {len(urls)} concurrent downloads...")

    results = await manager.start_all()

    for download_id, result in results.items():
        if isinstance(result, Exception):
            print(f"❌ {download_id} failed: {result}")
        elif result:
            print(f"✅ {download_id} completed: {result}")
        else:
            print(f"⏸️ {download_id} was cancelled")


if __name__ == '__main__':
    asyncio.run(main())
