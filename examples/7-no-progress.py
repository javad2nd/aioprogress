from aioprogress import AsyncDownloader
import asyncio


async def main():
    url = 'https://mirror.nforce.com/pub/speedtests/25mb.bin'

    # its unusual, because its aioprogress ... :)
    # but maybe you do not like progress
    # so, you can do something like this:
    async with AsyncDownloader(url, './downloads', progress_callback=lambda: None) as downloader:
        filename = await downloader.download()
        print(filename)


if __name__ == '__main__':
    asyncio.run(main())
