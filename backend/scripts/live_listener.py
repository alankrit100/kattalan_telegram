import os
import requests
from telethon import TelegramClient, events
from dotenv import load_dotenv

load_dotenv()

API_ID = os.environ.get("TG_API_ID")
API_HASH = os.environ.get("TG_API_HASH")
TARGET_CHAT_NAME = "Trade With Logic (Index + Stock)" 
WEBHOOK_URL = "http://127.0.0.1:8000/webhook/telegram"

# Connect using the session we already created
client = TelegramClient('kattalan_session', int(API_ID), API_HASH)

def forward_to_engine(message_obj, is_edit=False):
    """Packages the Telegram event and fires it to our local FastAPI server."""
    payload = {
        "message": {
            "message_id": message_obj.id,
            "date": int(message_obj.date.timestamp()),
            "chat": {"id": str(message_obj.chat_id)},
            "text": message_obj.text
        }
    }
    
    # If it's an edit, tweak the JSON key so main.py knows
    if is_edit:
        payload["edited_message"] = payload.pop("message")

    try:
        response = requests.post(WEBHOOK_URL, json=payload)
        if response.status_code == 200:
            print(f"  ✅ Engine Processed. Response: {response.json().get('status')}")
        else:
            print(f"  ⚠️ Engine Error: {response.status_code} - {response.text}")
    except requests.exceptions.ConnectionError:
        print("  ❌ FATAL: Could not reach FastAPI server. Is uvicorn running?")

# --- 1. CATCH NEW MESSAGES INSTANTLY ---
@client.on(events.NewMessage(chats=TARGET_CHAT_NAME))
async def handle_new_message(event):
    if not event.message.text: return
    print(f"\n🚨 NEW MESSAGE CAUGHT: {event.message.text[:50]}...")
    forward_to_engine(event.message)

# --- 2. CATCH SCAMMERS CHANGING TARGETS MID-TRADE ---
@client.on(events.MessageEdited(chats=TARGET_CHAT_NAME))
async def handle_edit(event):
    if not event.message.text: return
    print(f"\n⚠️ MESSAGE EDITED CAUGHT: {event.message.text[:50]}...")
    forward_to_engine(event.message, is_edit=True)

# --- 3. CATCH SCAMMERS DELETING LOSSES ---
@client.on(events.MessageDeleted(chats=TARGET_CHAT_NAME))
async def handle_delete(event):
    # event.deleted_ids contains the message IDs they just tried to wipe
    print(f"\n🗑️ DELETE DETECTED! They tried to hide Message IDs: {event.deleted_ids}")

print("🎧 KATTALAN LIVE LISTENER ACTIVE. Waiting for signals...")
client.start()
client.run_until_disconnected()