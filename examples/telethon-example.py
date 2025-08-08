from telethon import TelegramClient, events
from aioprogress import Progress
import os

api_id = 123456  # Your API ID from https://my.telegram.org
api_hash = 'YOUR_API_HASH'
session_name = 'session'

download_path = './downloads'
os.makedirs(download_path, exist_ok=True)

client = TelegramClient(session_name, api_id, api_hash)


@client.on(events.NewMessage())
async def handler(event):
    if event.message.document:
        # show progress to user
        message = await event.reply("Downloading...")

        async def progress_callback(progress):
            await message.edit(f"Downloading {progress:.2f}%")

        file_path = await event.download_media(
            progress_callback=Progress(progress_callback, interval=3)  # update progress bar every 3 seconds
        )
        await message.edit(f"Downloaded to {file_path}")


with client:
    print("Bot is running... Press Ctrl+C to stop.")
    client.run_until_disconnected()
