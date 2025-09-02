from aioprogress import AsyncDownloader
import asyncio

async def main():
    url = 'https://mirror.nforce.com/pub/speedtests/25mb.bin'
    async with AsyncDownloader(url, './downloads/') as downloader:
        task = asyncio.create_task(downloader.start())

        # Simulate user interaction
        await asyncio.sleep(2)
        print("Pausing download...")
        downloader.pause()

        await asyncio.sleep(3)
        print("Resuming download...")
        downloader.resume()

        # Wait for completion
        result = await task
        print(f"✅ Final result: {result}")

if __name__ == '__main__':
    asyncio.run(main())
