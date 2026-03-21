import os
import sys
import pytz
from datetime import datetime

# Point to your core modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.repository import SupabaseRepository
from data.provider_fyers import FyersDataProvider
from core.quant_engine import QuantEngine
from core.schemas import Signal

def build_fyers_symbol(underlying: str, instr_type: str) -> str:
    """Converts the Telegram asset name into a valid Fyers ticker."""
    underlying = underlying.upper().strip()
    
    # Map the exact Index names Fyers expects
    if "BANK" in underlying:
        return "NSE:NIFTYBANK-INDEX"
    elif "NIFTY" in underlying:
        return "NSE:NIFTY50-INDEX"
    elif "SENSEX" in underlying:
        return "BSE:SENSEX-INDEX"
    
    # Standard equity stocks (like ONGC, ABB, NTPC)
    return f"NSE:{underlying}-EQ"

def run_evaluation():
    print("🚀 BOOTING KATTALAN BACKTESTER...\n")
    
    repo = SupabaseRepository()
    provider = FyersDataProvider()
    engine = QuantEngine()
    ist = pytz.timezone('Asia/Kolkata')

    print("📥 Fetching trades from Supabase `signals` table...")
    # Get up to 50 recent trades from your database
    response = repo.supabase.table('signals').select('*').order('issued_at', desc=True).limit(50).execute()
    
    if not response.data:
        print("❌ No trades found in database.")
        return

    success_count = 0

    for row in response.data:
        try:
            # 1. Rebuild the Signal object from the Supabase row
            issued_at = datetime.fromisoformat(row['issued_at'])
            
            signal = Signal(
                signal_id=row['signal_id'],
                channel_id=row['channel_id'],
                message_id=row['message_id'],
                raw_text=row['raw_text'],
                underlying=row.get('underlying', 'UNKNOWN'),
                instrument_type=row.get('instrument_type', 'EQ'),
                strike=row.get('strike'),
                direction=row['direction'],
                entry_price=row['entry_price'],
                stop_loss=row['stop_loss'],
                targets=row['targets'],
                is_intraday=row['is_intraday'],
                issued_at=issued_at
            )

            symbol = build_fyers_symbol(signal.underlying, signal.instrument_type)
            print(f"\n⚙️ Evaluating {signal.direction} {symbol} (from {issued_at.strftime('%Y-%m-%d')})")

            # 2. Define the exact market window (Time of Telegram post -> 15:30)
            start_time = issued_at.astimezone(ist) if issued_at.tzinfo else ist.localize(issued_at)
            end_time = start_time.replace(hour=15, minute=30, second=0)

            # 3. Ask Fyers for the exact 1-minute chart for that window
            market_data = provider.fetch_1m_data(symbol, start_time, end_time)
            
            if not market_data:
                print(f"  ⏭️ Skipped: No Fyers data found (Holiday, Weekend, or market closed).")
                continue

            # 4. Run the math
            evaluation = engine.evaluate(signal, market_data)

            # 5. Save the WIN/LOSS result to the Supabase `evaluations` table
            repo.upsert_evaluation(evaluation)
            print(f"  ✅ SAVED EVALUATION: {evaluation.status} | Exit Price: {evaluation.exit_executed_price}")
            success_count += 1

        except Exception as e:
            print(f"  ❌ Execution Error: {e}")

    print("\n=================================================")
    print(f"🎉 BACKTEST COMPLETE! Calculated Win/Loss for {success_count} trades.")
    print("=================================================")

if __name__ == "__main__":
    run_evaluation()