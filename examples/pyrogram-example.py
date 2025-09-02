import asyncio

from pyrogram import Client, filters, idle
from pyrogram.types import Message
from aioprogress.progress import Progress, ProgressData
import os

api_id = 123456  # Your API ID from https://my.telegram.org
api_hash = "YOUR_API_HASH"
session_name = "session"

download_path = "./downloads"
os.makedirs(download_path, exist_ok=True)


async def main():
    app = Client(session_name, api_id=api_id, api_hash=api_hash)
    async with app:
        @app.on_message(filters.document)
        async def download_document(_, message: Message):
            # show progress to user
            sent = await message.reply("Downloading...")
            async def progress_callback(progress: ProgressData):
                await sent.edit(f"""
                    Downloading {progress}
                    Speed: {progress.speed_human_readable}
                    {progress.current_human_readable} / {progress.total_human_readable}
                """)

            file_path = await message.download(
                progress=Progress(progress_callback, interval=3)   # update progress bar every 3 seconds
            )
            await message.edit(f"Downloaded to {file_path}")

        await idle()


if __name__ == "__main__":
    asyncio.run(main())
