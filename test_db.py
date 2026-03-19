from datetime import datetime
from core.parser import SignalParser
from core.quant_engine import QuantEngine
from core.repository import SupabaseRepository
from core.schemas import OHLC

# 1. Initialize our components
parser = SignalParser()
engine = QuantEngine()
db = SupabaseRepository()

# 2. Parse a fake telegram message
raw_text = "BUY BANKNIFTY ABOVE 48000 SL 47900 TGT 48100 48200"
signal = parser.parse(
    raw_text=raw_text, 
    message_time=datetime(2023, 1, 1, 9, 59),
    channel_id="TEST_CHANNEL_01",
    message_id="MSG_001"
)

# 3. Create a winning market scenario
market_data = [
    OHLC(timestamp=datetime(2023, 1, 1, 10, 0), open=48000.0, high=48050.0, low=47990.0, close=48010.0),
    OHLC(timestamp=datetime(2023, 1, 1, 10, 1), open=48010.0, high=48210.0, low=48000.0, close=48200.0)
]

# 4. Run the math
evaluation = engine.evaluate(signal, market_data)

# 5. PUSH TO CLOUD
print("Pushing Signal to Supabase...")
db.upsert_signal(signal)

print("Pushing Evaluation to Supabase...")
db.upsert_evaluation(evaluation)

print("✅ Success! Go check your Supabase dashboard.")