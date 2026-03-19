from datetime import datetime
from core.parser import SignalParser
from core.quant_engine import QuantEngine
from core.schemas import EvaluationResult
from data.provider_base import MarketDataProvider

class KattalanOrchestrator:
    """
    The main nervous system of the backend. 
    Wires the Parser, Data Provider, and Engine together.
    """
    
    def __init__(self, data_provider: MarketDataProvider):
        self.provider = data_provider
        self.parser = SignalParser()
        self.engine = QuantEngine()

    def process_live_message(self, raw_text: str, message_time: datetime, symbol: str, channel_id: str, message_id: str) -> EvaluationResult:
        try:
            # 1. Parse the chaotic human text into a strict Signal object (Now with IDs!)
            signal = self.parser.parse(raw_text, message_time, channel_id, message_id)
            
            # 2. Define the evaluation window 
            end_time = message_time.replace(hour=15, minute=30, second=0)
            
            # 3. Fetch the pristine 1-minute OHLC data 
            market_data = self.provider.fetch_1m_data(symbol, message_time, end_time)
            
            # 4. Run the deterministic math
            result = self.engine.evaluate(signal, market_data)
            
            return result
            
        except Exception as e:
            raise RuntimeError(f"Orchestration Failed: {str(e)}")