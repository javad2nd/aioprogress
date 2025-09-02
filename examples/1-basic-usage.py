from aioprogress import AsyncDownloader
import asyncio

async def main():
    url = 'https://mirror.nforce.com/pub/speedtests/25mb.bin'
    async with AsyncDownloader(url, './downloads/') as downloader:
        filename = await downloader.start()
        if filename:
            print(f"File saved in {filename}")
        else:
            print("Download failed or cancelled")

if __name__ == '__main__':
    asyncio.run(main())
