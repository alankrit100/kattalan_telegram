from datetime import datetime
from core.parser import SignalParser

parser = SignalParser()

# Notice how messy this is, and it includes "27th march expiry"
messy_telegram_text = "guys load up on banknifty 48k calls right now above 400. 27th march expiry!! keep strict stoploss at 350. aim for 450 and 500. don't miss this one 🔥🚀"

print("Sending messy text to AI Parser...")
result = parser.parse(
    raw_text=messy_telegram_text,
    message_time=datetime.now(),
    channel_id="ALPHA_TRADERS",
    message_id="MSG_002" # changed ID for the test
)

print("\n✅ AI Successfully Extracted Instrument Data:")
print(result["instrument_data"].model_dump_json(indent=2))