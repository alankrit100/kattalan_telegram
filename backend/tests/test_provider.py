import pytest
import os
import pandas as pd
from datetime import datetime
from data.provider_csv import CSVMarketDataProvider

@pytest.fixture
def mock_csv_path():
    # Create a tiny mock CSV file for testing
    path = "tests/temp_mock_data.csv"
    data = {
        "timestamp": ["2023-01-01 09:15:00", "2023-01-01 09:16:00"],
        "symbol": ["BANKNIFTY", "BANKNIFTY"],
        "open": [48000.0, 48010.0],
        "high": [48020.0, 48030.0],
        "low": [47990.0, 48000.0],
        "close": [48010.0, 48020.0]
    }
    pd.DataFrame(data).to_csv(path, index=False)
    
    yield path # Provide path to the test
    
    # Teardown: Delete the file after the test finishes
    if os.path.exists(path):
        os.remove(path)

def test_csv_provider_loads_data(mock_csv_path):
    provider = CSVMarketDataProvider(mock_csv_path)
    
    start = datetime(2023, 1, 1, 9, 15, 0)
    end = datetime(2023, 1, 1, 9, 16, 0)
    
    # Fetch the data
    candles = provider.fetch_1m_data("BANKNIFTY", start, end)
    
    assert len(candles) == 2
    assert candles[0].open == 48000.0
    assert candles[1].close == 48020.0

def test_csv_provider_empty_window(mock_csv_path):
    provider = CSVMarketDataProvider(mock_csv_path)
    
    # Ask for data on a day that doesn't exist in the CSV
    start = datetime(2025, 1, 1, 9, 15, 0)
    end = datetime(2025, 1, 1, 9, 16, 0)
    
    candles = provider.fetch_1m_data("BANKNIFTY", start, end)
    
    # Should safely return an empty list, not crash
    assert len(candles) == 0