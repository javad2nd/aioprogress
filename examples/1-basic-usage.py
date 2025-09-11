from aioprogress import AsyncDownloader
import asyncio


async def main():
    """
    Basic download example demonstrating the simplest usage of AsyncDownloader.
    Downloads a test file to the local downloads directory.
    """
    url = 'https://mirror.nforce.com/pub/speedtests/25mb.bin'

    # Create downloader with basic configuration
    async with AsyncDownloader(url, './downloads/') as downloader:
        filename = await downloader.start()
        if filename:
            print(f"File saved in {filename}")
        else:
            print("Download failed or cancelled")


if __name__ == '__main__':
    asyncio.run(main())
