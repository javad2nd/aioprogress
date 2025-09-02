from aioprogress import AsyncDownloader, DownloadConfig
import asyncio


async def main():
    config = DownloadConfig(
        proxy_url='http://proxy.example.com:8080',  # Replace with real proxy
        proxy_auth=('username', 'password'),  # Replace with real credentials
        proxy_headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
    )

    url = 'https://mirror.nforce.com/pub/speedtests/25mb.bin'

    async with AsyncDownloader(url, "./downloads/", config) as downloader:
        await downloader.start()


if __name__ == '__main__':
    asyncio.run(main())
