import os
import sys
import time
from datetime import datetime, timedelta, timezone
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
CHANNEL_DB_ID = "Trade_With_Logic" # Used to identify the channel in Supabase
BATCH_SIZE = 100

def chunk_list(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def run():
    print("🚀 BOOTING RESUMABLE INGESTION PIPELINE...\n")
    parser = SignalParser()
    repo = SupabaseRepository()
    
    # --- 1. THE CHECKPOINT: Ask DB what we already have ---
    print("🗄️ Checking database for previously parsed messages...")
    try:
        # Fetch only the message_ids to save bandwidth
        existing_records = repo.supabase.table('signals').select('message_id').eq('channel_id', CHANNEL_DB_ID).execute()
        existing_ids = {str(row['message_id']) for row in existing_records.data}
        print(f"✅ Found {len(existing_ids)} trades already secured in Supabase. These will be skipped.")
    except Exception as e:
        print(f"❌ Failed to connect to Supabase: {e}")
        return

    with TelegramClient('kattalan_session', int(API_ID), API_HASH) as client:
        target_entity = None
        for dialog in client.get_dialogs(limit=150):
            if dialog.name == TARGET_CHAT_NAME:
                target_entity = dialog.entity
                break
                
        if not target_entity:
            print("❌ Could not find channel.")
            return

        # --- 2. THE TIME MACHINE: Exactly 6 Months ---
        six_months_ago = datetime.now(timezone.utc) - timedelta(days=180)
        print(f"\n📥 Fetching Telegram history back to {six_months_ago.strftime('%Y-%m-%d')}...")
        
        filtered_messages = []
        
        for msg in client.iter_messages(target_entity):
            # Stop downloading if we pass the 6-month mark
            if msg.date < six_months_ago:
                break 
                
            msg_id_str = str(msg.id)
            
            # Skip if we already parsed this exact message in a previous run
            if msg_id_str in existing_ids:
                continue

            # Run the strict Python Regex Bouncer (Costs $0)
            if msg.text and is_potential_signal(msg.text):
                filtered_messages.append({"message_id": msg_id_str, "text": msg.text, "time": msg.date})

        if not filtered_messages:
            print("\n🎉 Pipeline is 100% up to date! No new signals to process.")
            return

        print(f"📦 Found {len(filtered_messages)} NEW potential signals. Sending to AI in batches of {BATCH_SIZE}...\n")
        
        saved_count = 0
        batches = list(chunk_list(filtered_messages, BATCH_SIZE))
        
        for index, batch in enumerate(batches):
            print(f"⚙️ Processing Batch {index + 1}/{len(batches)}...")
            
            try:
                parsed_results = parser.parse_batch(batch_data=batch, channel_id=CHANNEL_DB_ID)
                
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
                error_str = str(e).lower()
                # --- 3. THE GRACEFUL CRASH (Rate Limit & Auth Handling) ---
                critical_errors = ["429", "quota", "exhausted", "403", "permission_denied", "leaked", "api key"]
                
                if any(keyword in error_str for keyword in critical_errors):
                    print(f"\n🛑 CRITICAL AI ERROR HIT: {e}")
                    print("--> ACTION REQUIRED: Pipeline paused to save resources.")
                    print("    1. Generate a brand new GEMINI_API_KEY and update your .env file.")
                    print("    2. Run this script again. It will safely resume exactly where it stopped.")
                    sys.exit(0) # Immediately terminates the entire script
                else:
                    print(f"❌ Batch Error: {e}")
            
            # Sleep to prevent spamming the API too fast
            if index < len(batches) - 1:
                print("⏳ Sleeping 12 seconds for rate limits...")
                time.sleep(12)
                
        print(f"\n🎉 COMPLETE! Added {saved_count} new historical trades to the database.")

if __name__ == "__main__":
    run()