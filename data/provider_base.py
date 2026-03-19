from abc import ABC, abstractmethod
from typing import List
from datetime import datetime
from core.schemas import OHLC # (Assuming the schemas from my previous message are here)

class MarketDataProvider(ABC):
    """
    Abstract Base Class for all market data ingestion.
    Forces all data sources to output uniform Pydantic OHLC objects.
    """
    
    @abstractmethod
    def fetch_1m_data(self, symbol: str, start_time: datetime, end_time: datetime) -> List[OHLC]:
        """
        Must return a chronological list of 1-minute OHLC candles.
        """
        pass