import asyncio
from pyrogram import Client, filters, idle
from pyrogram.types import Message
from aioprogress.progress import Progress, ProgressData
import os

# Telegram API credentials from https://my.telegram.org
api_id = 123456
api_hash = "YOUR_API_HASH"
session_name = "session"

# Setup download directory
download_path = "./downloads"
os.makedirs(download_path, exist_ok=True)


async def main():
    """
    Main function to run the Pyrogram client with document download handling.
    Provides real-time progress updates and error handling.
    """
    # Create and start Pyrogram client
    app = Client(session_name, api_id=api_id, api_hash=api_hash)

    async with app:
        @app.on_message(filters.document)
        async def download_document(_, message: Message):
            """
            Handle document messages with progress tracking and user feedback.
            Downloads files and provides real-time updates to the user.
            """
            # Send initial download notification
            sent = await message.reply("📥 Starting download...")

            async def progress_callback(progress: ProgressData):
                """Update user with current download progress"""
                try:
                    await sent.edit(f"""
📥 Downloading {progress}
🚀 Speed: {progress.speed_human_readable}
📊 Size: {progress.current_human_readable} / {progress.total_human_readable}
⏰ ETA: {progress.eta_human_readable}
                    """)
                except Exception:
                    # Ignore edit errors (too many requests, etc.)
                    pass

            try:
                # Download with progress updates every 3 seconds
                file_path = await message.download(
                    progress=Progress(progress_callback, interval=3)
                )
                await sent.edit(f"✅ Download completed!\nSaved to: {file_path}")
            except Exception as e:
                await sent.edit(f"❌ Download failed: {str(e)}")

        print("Pyrogram bot is running... Press Ctrl+C to stop.")
        await idle()


if __name__ == "__main__":
    asyncio.run(main())
