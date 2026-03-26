import sys
import os
from datetime import datetime
import pytz

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.parser import SignalParser
from core.quant_engine import QuantEngine
from data.provider_fyers import FyersDataProvider

def verify_trades():
    print("🔍 KATTALAN ENGINE AUDIT: VERIFYING REAL TELEGRAM DATA")
    ist = pytz.timezone('Asia/Kolkata')
    
    parser = SignalParser()
    engine = QuantEngine()
    provider = FyersDataProvider()

    test_batch = [
        {
            "id": "EQUITY_VERIFY_003",
            "time": datetime(2026, 3, 4, 9, 20), 
            "text": "BUY HDFCBANK ABOVE 865 SL 855 TGT 875", # Entry is now above the open price
            "symbol": "NSE:HDFCBANK-EQ" 
        }
    ]

    for item in test_batch:
        try:
            print(f"\n--- Testing {item['id']} ---")
            
            res = parser.parse(item['text'], item['time'], "AUDIT", item['id'])
            signal = res['signal']
            
            start_time = ist.localize(item['time'])
            end_time = start_time.replace(hour=15, minute=30)
            market_data = provider.fetch_1m_data(item['symbol'], start_time, end_time)
            
            if not market_data:
                print("❌ No market data returned from Fyers.")
                continue

            print(f"📊 First candle price: {market_data[0].open} | Signal Entry: {signal.entry_price}")
            
            eval_result = engine.evaluate(signal, market_data)
            
            # FIX: Using .status and .reason (matching our QuantEngine schema)
            print(f"RESULT: {eval_result.status}")
            print(f"EXIT PRICE: {eval_result.exit_executed_price}")
            print(f"EXIT TIME: {eval_result.exit_time}")
            print(f"REASON: {getattr(eval_result, 'reason', 'No reason provided')}")
            
            print("\nTRACE LOG (Top 5):")
            for log in eval_result.trace_log[:5]:
                print(f"  - {log}")

        except Exception as e:
            print(f"❌ Verification Failed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    verify_trades()