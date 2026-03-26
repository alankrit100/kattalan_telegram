import os
from telethon.sync import TelegramClient
from dotenv import load_dotenv

load_dotenv()

API_ID = os.environ.get("TG_API_ID")
API_HASH = os.environ.get("TG_API_HASH")

print("🔍 Scanning your recent Telegram chats...")

with TelegramClient('kattalan_session', int(API_ID), API_HASH) as client:
    # Gets your 20 most recent conversations/channels
    for dialog in client.get_dialogs(limit=20):
        print(f"ID: {dialog.id} | Name: {dialog.name}")