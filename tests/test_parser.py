import pytest
from datetime import datetime
from core.parser import SignalParser

@pytest.fixture
def parser():
    return SignalParser()

def test_standard_buy_call(parser):
    raw_text = "🚀 BUY BANKNIFTY 48000 CE @ 500 \nSL 450 \nTGT 550 600 650 🔥"
    result = parser.parse(raw_text, datetime(2023, 1, 1, 10, 0), channel_id="TEST_CH", message_id="TEST_MSG")
    
    signal = result["signal"] # <-- FIXED: Extract from dictionary
    
    assert signal.direction == "BUY"
    assert signal.entry_price == 500.0
    assert signal.stop_loss == 450.0
    assert signal.targets == [550.0, 600.0, 650.0]
    assert signal.channel_id == "TEST_CH"
    assert signal.message_id == "TEST_MSG"

def test_messy_sell_call(parser):
    raw_text = "SELL NIFTY FUT BELOW 21000... STOPLOSS: 21100 TARGETS 20900, 20850"
    result = parser.parse(raw_text, datetime(2023, 1, 1, 10, 0), channel_id="TEST_CH", message_id="TEST_MSG")
    
    signal = result["signal"] # <-- FIXED: Extract from dictionary
    
    assert signal.direction == "SELL"
    assert signal.entry_price == 21000.0
    assert signal.stop_loss == 21100.0
    assert signal.targets == [20900.0, 20850.0] 

def test_parser_fails_safely_on_junk(parser):
    raw_text = "Good morning traders! Market looks bullish today."
    
    with pytest.raises(ValueError) as excinfo:
        parser.parse(raw_text, datetime(2023, 1, 1, 10, 0), channel_id="TEST_CH", message_id="TEST_MSG")
        
    assert "LLM Parsing failed" in str(excinfo.value) # <-- FIXED: Match new error string
    
import pytest
from datetime import datetime
from unittest.mock import patch # <-- ADD THIS IMPORT AT THE TOP
from core.parser import SignalParser

# ... (keep your fixture and first two tests exactly as they are) ...

@patch('core.parser.genai.Client') # Mocks the Gemini Client
def test_parser_fails_safely_on_junk(mock_client, parser):
    raw_text = "Good morning traders! Market looks bullish today."
    
    # Force the mock client to simulate an API crash/refusal
    mock_client.return_value.models.generate_content.side_effect = Exception("API Offline")
    
    with pytest.raises(ValueError) as excinfo:
        parser.parse(raw_text, datetime(2023, 1, 1, 10, 0), channel_id="TEST_CH", message_id="TEST_MSG")
        
    assert "LLM Parsing failed" in str(excinfo.value)