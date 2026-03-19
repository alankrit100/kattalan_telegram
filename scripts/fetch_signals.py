import os
import sys
from telethon.sync import TelegramClient
from dotenv import load_dotenv

load_dotenv()

API_ID = os.environ.get("TG_API_ID")
API_HASH = os.environ.get("TG_API_HASH")

TARGET_CHAT_NAME = "Trade With Logic (Index + Stock)" 

# Our "Bouncer" keywords. If a message doesn't have at least one of these, it's spam.
SIGNAL_KEYWORDS = ['BUY', 'SELL', 'SL', 'TGT', 'TARGET', 'CE', 'PE', 'CALL', 'PUT', 'ABOVE', 'BELOW']

def is_potential_signal(text: str) -> bool:
    text_upper = text.upper()
    # Check if any of our keywords exist in the message
    return any(keyword in text_upper for keyword in SIGNAL_KEYWORDS)

with TelegramClient('kattalan_session', int(API_ID), API_HASH) as client:
    print(f"🔍 Locating '{TARGET_CHAT_NAME}'...")
    
    target_entity = None
    for dialog in client.get_dialogs(limit=50):
        if dialog.name == TARGET_CHAT_NAME:
            target_entity = dialog.entity
            break
            
    if not target_entity:
        print("❌ Could not find channel.")
        sys.exit()
        
    print(f"✅ Connected! Fetching last 100 messages to hunt for real signals...\n")
    
    messages = client.get_messages(target_entity, limit=100)
    
    signal_count = 0
    spam_count = 0
    
    for msg in messages:
        if msg.text:
            if is_potential_signal(msg.text):
                signal_count += 1
                print("-------------------------------------------------")
                print(f"🟢 POTENTIAL SIGNAL DETECTED (ID: {msg.id})")
                print(f"Text:\n{msg.text.strip()}")
            else:
                spam_count += 1

    print("\n=================================================")
    print(f"📊 REPORT: Scanned 100 messages.")
    print(f"🗑️ Spam/Marketing dropped: {spam_count}")
    print(f"🎯 Real Signals found: {signal_count}")
    print("=================================================")