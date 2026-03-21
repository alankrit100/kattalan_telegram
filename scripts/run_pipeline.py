import os
import sys
import time
from telethon.sync import TelegramClient
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.parser import SignalParser
from core.repository import SupabaseRepository
from core.utils import is_potential_signal

load_dotenv()

API_ID = os.environ.get("TG_API_ID")
API_HASH = os.environ.get("TG_API_HASH")
TARGET_CHAT_NAME = "Trade With Logic (Index + Stock)" 
BATCH_SIZE = 30

def chunk_list(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def run():
    print("🚀 BOOTING BATCH INGESTION PIPELINE...\n")
    parser = SignalParser()
    repo = SupabaseRepository()
    
    with TelegramClient('kattalan_session', int(API_ID), API_HASH) as client:
        target_entity = None
        for dialog in client.get_dialogs(limit=150):
            if dialog.name == TARGET_CHAT_NAME:
                target_entity = dialog.entity
                break
                
        if not target_entity:
            print("❌ Could not find channel.")
            return

        print(f"📥 Fetching last 1000 messages from '{TARGET_CHAT_NAME}'...")
        messages = client.get_messages(target_entity, limit=1000)
        
        # Filter spam locally first
        filtered_messages = []
        for msg in messages:
            if msg.text and is_potential_signal(msg.text):
                filtered_messages.append({"message_id": str(msg.id), "text": msg.text, "time": msg.date})

        print(f"📦 Sending {len(filtered_messages)} potential signals to AI in batches of {BATCH_SIZE}...\n")
        saved_count = 0
        batches = list(chunk_list(filtered_messages, BATCH_SIZE))
        
        for index, batch in enumerate(batches):
            print(f"⚙️ Processing Batch {index + 1}/{len(batches)}...")
            
            try:
                parsed_results = parser.parse_batch(batch_data=batch, channel_id="Trade_With_Logic")
                
                for result in parsed_results:
                    signal = result['signal']
                    instr = result['instrument_data']
                    try:
                        repo.upsert_signal(signal)
                        print(f"  ✅ SAVED TO DATABASE: {instr.underlying} {instr.strike} {instr.instrument_type}")
                        saved_count += 1
                    except Exception as e:
                        print(f"  ❌ DB Error: {e}")

            except Exception as e:
                print(f"❌ Batch Error: {e}")
            
            if index < len(batches) - 1:
                print("⏳ Sleeping 12 seconds for rate limits...")
                time.sleep(12)
                
        print(f"\n🎉 COMPLETE! Saved {saved_count} historical trades.")

if __name__ == "__main__":
    run()