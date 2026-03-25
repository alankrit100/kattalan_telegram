from datetime import datetime
from core.parser import SignalParser
from core.quant_engine import QuantEngine
from core.schemas import EvaluationResult
from data.provider_base import MarketDataProvider
from core.repository import SupabaseRepository

def build_fyers_symbol(underlying: str, instr_type: str) -> str:
    """Converts the Telegram asset name into a valid Fyers ticker."""
    underlying = underlying.upper().strip()
    if "BANK" in underlying: return "NSE:NIFTYBANK-INDEX"
    if "NIFTY" in underlying: return "NSE:NIFTY50-INDEX"
    if "SENSEX" in underlying: return "BSE:SENSEX-INDEX"
    return f"NSE:{underlying}-EQ"

class KattalanOrchestrator:
    """
    The main nervous system of the backend. 
    Wires the Parser, Data Provider, and Engine together.
    """
    
    def __init__(self, data_provider: MarketDataProvider):
        self.db = SupabaseRepository()
        self.provider = data_provider
        self.parser = SignalParser()
        self.engine = QuantEngine()

    # NOTE: I removed the hardcoded `symbol` argument here. 
    def process_live_message(self, raw_text: str, message_time: datetime, channel_id: str, message_id: str) -> EvaluationResult:
        try:
            # 1. Parse the chaotic human text
            parsed_data = self.parser.parse(raw_text, message_time, channel_id, message_id)
            
            # --- THE FIX: Extract the actual Pydantic object ---
            signal = parsed_data["signal"]
            
            # 2. Dynamically build the ticker (Handles Equities AND Options now)
            dynamic_symbol = build_fyers_symbol(signal.underlying, signal.instrument_type)
            
            # 3. Define the evaluation window 
            end_time = message_time.replace(hour=15, minute=30, second=0)
            
            # 4. Fetch the pristine 1-minute OHLC data 
            market_data = self.provider.fetch_1m_data(dynamic_symbol, message_time, end_time)
            
            # 5. Run the deterministic math
            result = self.engine.evaluate(signal, market_data)
            
            self.db.upsert_signal(signal)
            self.db.upsert_evaluation(result)
            
            return result
            
        except Exception as e:
            raise RuntimeError(f"Orchestration Failed: {str(e)}")