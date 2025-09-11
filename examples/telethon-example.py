from telethon import TelegramClient, events
from aioprogress.progress import Progress, ProgressData
import os

# Telegram API credentials from https://my.telegram.org
api_id = 123456
api_hash = 'YOUR_API_HASH'
session_name = 'session'

# Setup download directory
download_path = './downloads'
os.makedirs(download_path, exist_ok=True)

# Create Telegram client
client = TelegramClient(session_name, api_id, api_hash)


@client.on(events.NewMessage())
async def handler(event):
    """
    Handle new messages and download any documents with progress tracking.
    Updates the user with download progress and completion status.
    """
    if event.message.document:
        # Notify user that download is starting
        message = await event.reply("Starting download...")

        async def progress_callback(progress: ProgressData):
            """Update message with current download progress"""
            await message.edit(f"""
📥 Downloading {progress}
🚀 Speed: {progress.speed_human_readable}
📊 Progress: {progress.current_human_readable} / {progress.total_human_readable}
⏰ ETA: {progress.eta_human_readable}
            """)

        try:
            # Download media with progress updates every 3 seconds
            file_path = await event.download_media(
                progress_callback=Progress(progress_callback, interval=3)
            )
            await message.edit(f"✅ Downloaded successfully to {file_path}")
        except Exception as e:
            await message.edit(f"❌ Download failed: {str(e)}")


# Run the client
with client:
    print("Telegram bot is running... Press Ctrl+C to stop.")
    client.run_until_disconnected()
