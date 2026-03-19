import os
import sys
from telethon.sync import TelegramClient
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.parser import SignalParser
from core.repository import SupabaseRepository

load_dotenv()

API_ID = os.environ.get("TG_API_ID")
API_HASH = os.environ.get("TG_API_HASH")
TARGET_CHAT_NAME = "Trade With Logic (Index + Stock)" 
SIGNAL_KEYWORDS = ['BUY', 'SELL', 'SL', 'TGT', 'TARGET', 'CE', 'PE', 'CALL', 'PUT', 'ABOVE', 'BELOW']

def is_potential_signal(text: str) -> bool:
    text_upper = text.upper()
    return any(keyword in text_upper for keyword in SIGNAL_KEYWORDS)

def run():
    print("🚀 BOOTING KATTALAN INGESTION PIPELINE...\n")
    
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

        print(f"📥 Fetching last 30 messages from '{TARGET_CHAT_NAME}'...")
        messages = client.get_messages(target_entity, limit=30)
        
        saved_count = 0
        
        for msg in messages:
            if msg.text and is_potential_signal(msg.text):
                print(f"\n⚙️ Analyzing Message ID: {msg.id}...")
                
                try:
                    result = parser.parse(msg.text, msg.date, "Trade_With_Logic", str(msg.id))
                    signal = result['signal']
                    instr = result['instrument_data'] 
                    
                    repo.upsert_signal(signal)
                    
                    print(f"✅ SAVED TO DATABASE: {instr.underlying} {instr.strike} {instr.instrument_type}")
                    saved_count += 1
                    
                except ValueError as e:
                    print(f"⚠️ Ignored by AI: {e}")
                except Exception as e:
                    print(f"❌ DB Error: {e}")
                    
        print("\n=================================================")
        print(f"🎉 PIPELINE COMPLETE! Saved {saved_count} new trades to Supabase.")
        print("=================================================")

if __name__ == "__main__":
    run()