from aioprogress import AsyncDownloader, ProgressData
import asyncio


async def main():
    def show_progress(progress: ProgressData):
        print(f"{progress} | {progress.speed_human_readable} | ETA: {progress.eta_human_readable}")

    url = 'https://mirror.nforce.com/pub/speedtests/25mb.bin'
    async with AsyncDownloader(url, "./downloads/", progress_callback=show_progress) as downloader:
        filename = await downloader.start()
        if filename:
            print(f"File saved at: {filename}")
        else:
            print("Download failed or cancelled")


if __name__ == '__main__':
    asyncio.run(main())
