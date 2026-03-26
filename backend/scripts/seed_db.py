import sys
import os
from datetime import datetime, timedelta
import pytz

# Adjust path to import from core/
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.parser import SignalParser
from core.quant_engine import QuantEngine
from core.repository import SupabaseRepository
from data.provider_fyers import FyersDataProvider

def run_production_seed():
    print("🚀 STARTING KATTALAN PRODUCTION SEED...")
    ist = pytz.timezone('Asia/Kolkata')
    
    # 1. Init Components
    parser = SignalParser()
    engine = QuantEngine()
    db = SupabaseRepository()
    provider = FyersDataProvider()

    # 2. REAL TEST BATCH (Replace these with 5-10 actual messages from your Telegram channels)
    # Ensure the dates are within the last few days so Fyers has 1m data!
    raw_batch = [
        {
            "channel": "PRO_TRADERS_INDIA",
            "msg_id": "MSG_999",
            "time": datetime(2026, 3, 4, 10, 15), # Yesterday
            "text": "BANKNIFTY 48200 CE BUY ABOVE 420 SL 380 TGT 460 500"
        },
        # Add more real messages here...
    ]

    for item in raw_batch:
        try:
            print(f"\n📦 Processing {item['msg_id']}...")
            
            # STEP A: AI EXTRACTION
            parsed_data = parser.parse(
                raw_text=item["text"],
                message_time=item["time"],
                channel_id=item["channel"],
                message_id=item["msg_id"]
            )
            signal = parsed_data["signal"]
            instr = parsed_data["instrument_data"]

            # STEP B: TICKER CONSTRUCTION
            # For Phase B, we use the Index Spot for math to ensure 100% data availability
            ticker = "NSE:BANKNIFTY-INDEX" if "BANK" in instr.underlying else "NSE:NIFTY50-INDEX"
            
            # STEP C: FETCH DATA
            start_time = ist.localize(item["time"])
            end_time = start_time.replace(hour=15, minute=30)
            market_data = provider.fetch_1m_data(ticker, start_time, end_time)

            # STEP D: EVALUATE
            result = engine.evaluate(signal, market_data)

            # STEP E: CLOUD PUSH
            db.upsert_signal(signal)
            db.upsert_evaluation(result)
            
            print(f"✅ SUCCESS: {item['msg_id']} | Status: {result.status} | Exit: {result.exit_executed_price}")

        except Exception as e:
            print(f"❌ FAILED {item['msg_id']}: {e}")

if __name__ == "__main__":
    run_production_seed()