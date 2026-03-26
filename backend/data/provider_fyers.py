import os
import pytz
from datetime import datetime
from typing import List
from fyers_apiv3 import fyersModel
from dotenv import load_dotenv
from core.schemas import OHLC
from data.provider_base import MarketDataProvider

# Load the .env file
load_dotenv(override=True)

class FyersDataProvider(MarketDataProvider):
    """
    Fetches real 1-minute historical data from Fyers Data API.
    """
    def __init__(self):
        self.ist = pytz.timezone('Asia/Kolkata')
        self.client_id = os.environ.get("FYERS_CLIENT_ID")
        self.access_token = os.environ.get("FYERS_ACCESS_TOKEN")
        #debug
        print(f"DEBUG: Fyers Client ID: {self.client_id}| Token starts with: {str(self.access_token)[:10]}...")
        
        if not self.client_id or not self.access_token:
            raise ValueError("FATAL: Missing Fyers credentials in .env file.")
            
        # Initialize Fyers Model
        self.fyers = fyersModel.FyersModel(
            client_id=self.client_id, 
            is_async=False, 
            token=self.access_token, 
            log_path="" # Disables cluttering log files
        )

    def fetch_1m_data(self, symbol: str, start_time: datetime, end_time: datetime) -> List[OHLC]:
        # Enforce IST timezones
        if start_time.tzinfo is None:
            start_time = self.ist.localize(start_time)
        if end_time.tzinfo is None:
            end_time = self.ist.localize(end_time)

        # Fyers API expects dates in yyyy-mm-dd format
        start_str = start_time.strftime("%Y-%m-%d")
        end_str = end_time.strftime("%Y-%m-%d")

        data = {
            "symbol": symbol,
            "resolution": "1",
            "date_format": "1",
            "range_from": start_str,
            "range_to": end_str,
            "cont_flag": "1"
        }

        print(f"📡 Requesting Fyers Data: {symbol} | {start_str} to {end_str}...")
        response = self.fyers.history(data=data)

        if response.get("s") != "ok":
            raise ValueError(f"Fyers API Error: {response.get('message', response)}")

        candles = response.get("candles", [])
        if not candles:
            raise ValueError(f"No market data returned for {symbol}. Is it a weekend or invalid symbol?")

        ohlc_list = []
        for candle in candles:
            # Fyers returns Unix Epoch time (seconds). Convert to IST.
            epoch_time = candle[0]
            dt_utc = datetime.utcfromtimestamp(epoch_time).replace(tzinfo=pytz.utc)
            dt_ist = dt_utc.astimezone(self.ist)

            # Only append candles strictly within our evaluation window
            if start_time <= dt_ist <= end_time:
                ohlc_list.append(OHLC(
                    timestamp=dt_ist,
                    open=float(candle[1]),
                    high=float(candle[2]),
                    low=float(candle[3]),
                    close=float(candle[4])
                ))

        return ohlc_list