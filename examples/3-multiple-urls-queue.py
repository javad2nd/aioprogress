from aioprogress import AsyncDownloader
import asyncio


async def main():
    urls = [
        'https://mirror.nforce.com/pub/speedtests/25mb.bin',
        'https://mirror.nforce.com/pub/speedtests/10mb.bin',
    ]

    for i, url in enumerate(urls, 1):
        print(f"Starting download {i}/{len(urls)}")
        async with AsyncDownloader(url, f"./downloads/{i}.bin") as downloader:
            result = await downloader.start()
            print(f"Completed: {result}")


if __name__ == '__main__':
    asyncio.run(main())
