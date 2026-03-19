import pandas as pd
import os
from typing import List
from datetime import datetime
from core.schemas import OHLC
from data.provider_base import MarketDataProvider

class CSVMarketDataProvider(MarketDataProvider):
    """
    Local implementation for offline testing. 
    Swaps out seamlessly for APIMarketDataProvider in production.
    """
    
    def __init__(self, file_path: str):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Data Source Error: Cannot find CSV at {file_path}")
        
        self.file_path = file_path
        
        try:
            self.df = pd.read_csv(self.file_path)
            
            # Edge Case 1: Standardize column names to lowercase and strip whitespace
            self.df.columns = self.df.columns.str.strip().str.lower()
            
            # Edge Case 2: Ensure all required columns exist
            required_cols = {'timestamp', 'open', 'high', 'low', 'close'}
            if not required_cols.issubset(set(self.df.columns)):
                raise ValueError(f"CSV missing required columns. Found: {list(self.df.columns)}")

            # Edge Case 3: Enforce proper datetime conversion
            self.df['timestamp'] = pd.to_datetime(self.df['timestamp'])
            
            # Edge Case 4: Sort chronologically to prevent time-travel bugs in the engine
            self.df.sort_values('timestamp', inplace=True)
            self.df.set_index('timestamp', inplace=True) # Set as index for fast querying
            
        except Exception as e:
            raise RuntimeError(f"Failed to initialize CSV Provider: {str(e)}")

    def fetch_1m_data(self, symbol: str, start_time: datetime, end_time: datetime) -> List[OHLC]:
        # Create a time mask
        mask = (self.df.index >= start_time) & (self.df.index <= end_time)
        
        # If the CSV contains multiple symbols, filter by symbol. 
        # If it's a single-instrument CSV (like just BankNifty), ignore symbol filtering.
        if 'symbol' in self.df.columns:
            mask = mask & (self.df['symbol'] == symbol)
            
        filtered_df = self.df.loc[mask]
        
        # Edge Case 5: Safely return empty list if no data exists in that window
        if filtered_df.empty:
            return []
            
        ohlc_list = []
        for index, row in filtered_df.iterrows():
            ohlc_list.append(
                OHLC(
                    timestamp=index.to_pydatetime(),
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close'])
                )
            )
        return ohlc_list