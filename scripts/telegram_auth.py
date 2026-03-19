import os
from telethon.sync import TelegramClient
from dotenv import load_dotenv

load_dotenv()

API_ID = os.environ.get("TG_API_ID")
API_HASH = os.environ.get("TG_API_HASH")
PHONE = os.environ.get("TG_PHONE")

print("🔌 Connecting to Telegram...")

# This creates a session file so you only do this once
with TelegramClient('kattalan_session', int(API_ID), API_HASH) as client:
    client.start(phone=PHONE)
    print("✅ SUCCESS! You are logged in as a Developer Node.")
    
    # Let's prove it works by grabbing your last saved message
    for msg in client.get_messages('me', limit=1):
        print(f"Your last saved message: {msg.text}")