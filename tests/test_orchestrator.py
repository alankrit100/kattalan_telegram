import pytest
import os
import pandas as pd
from datetime import datetime
from core.orchestrator import KattalanOrchestrator
from data.provider_csv import CSVMarketDataProvider

@pytest.fixture
def mock_csv_path():
    path = "tests/temp_orchestrator_data.csv"
    data = {
        "timestamp": [
            "2023-01-01 10:00:00", 
            "2023-01-01 10:01:00", 
            "2023-01-01 10:02:00",
            "2023-01-01 10:03:00" 
        ],
        "symbol": ["BANKNIFTY", "BANKNIFTY", "BANKNIFTY", "BANKNIFTY"],
        "open": [48000.0, 48010.0, 48050.0, 48100.0],
        "high": [48020.0, 48060.0, 48110.0, 48210.0], 
        "low": [47990.0, 48000.0, 48040.0, 48090.0],
        "close": [48010.0, 48050.0, 48100.0, 48200.0]
    }
    pd.DataFrame(data).to_csv(path, index=False)
    yield path
    if os.path.exists(path):
        os.remove(path)

def test_full_pipeline_success(mock_csv_path):
    provider = CSVMarketDataProvider(mock_csv_path)
    orchestrator = KattalanOrchestrator(provider)
    
    raw_telegram_message = "🚀 BUY BANKNIFTY ABOVE 48000... SL: 47900 TGT 48100, 48200"
    message_time = datetime(2023, 1, 1, 9, 59, 0) 
    
    # Passing the required mock IDs
    result = orchestrator.process_live_message(
        raw_text=raw_telegram_message, 
        message_time=message_time, 
        symbol="BANKNIFTY",
        channel_id="TEST_CH",
        message_id="TEST_MSG"
    )
    
    assert result.status == "WIN"
    assert result.entry_executed_price == 48000.0
    assert result.exit_executed_price == 48200.0