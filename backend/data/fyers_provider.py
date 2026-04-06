import os
import asyncio
import logging
from datetime import datetime, timezone
from typing import List

from fyers_apiv3 import fyersModel
from data.provider_base import MarketDataProvider
from core.schemas import OHLC

log = logging.getLogger(__name__)

_MCX = frozenset({"CRUDEOIL", "NATURALGAS", "GOLD", "SILVER"})
_INDICES = {
    "NIFTY": "NSE:NIFTY50-INDEX",
    "BANKNIFTY": "NSE:NIFTYBANK-INDEX",
    "FINNIFTY": "NSE:FINNIFTY-INDEX",
    "MIDCPNIFTY": "NSE:MIDCPNIFTY-INDEX",
    "SENSEX": "BSE:SENSEX-INDEX",
    "BANKEX": "BSE:BANKEX-INDEX",
}


class TokenExpiredError(Exception):
    pass


def build_fyers_symbol(underlying: str, instrument_type: str = "EQ") -> str:
    u = underlying.upper().strip()
    if u in _MCX:
        return f"MCX:{u}-INDEX"
    if u in _INDICES:
        return _INDICES[u]
    return f"NSE:{u}-EQ"


class FyersDataProvider(MarketDataProvider):
    def __init__(self):
        client_id = os.environ.get("FYERS_CLIENT_ID")
        token = os.environ.get("FYERS_ACCESS_TOKEN")
        if not client_id or not token:
            raise ValueError("FATAL: Missing FYERS_CLIENT_ID or FYERS_ACCESS_TOKEN")
        self.fyers = fyersModel.FyersModel(
            client_id=client_id,
            token=token,
            log_path="",
        )
        self._last_call_time = 0.0

    def fetch_1m_data(self, symbol: str, start: datetime, end: datetime) -> List[OHLC]:
        import time as _time

        # Rate limit: 10 req/sec → sleep 0.12s between calls
        elapsed = _time.monotonic() - self._last_call_time
        if elapsed < 0.12:
            import time as t; t.sleep(0.12 - elapsed)
        self._last_call_time = _time.monotonic()

        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)

        data = {
            "symbol": symbol,
            "resolution": "1",
            "date_format": "0",  # epoch
            "range_from": str(int(start.timestamp())),
            "range_to": str(int(end.timestamp())),
            "cont_flag": "1",
        }

        try:
            response = self.fyers.history(data=data)
        except Exception as e:
            log.error("Fyers API call failed for %s: %s", symbol, e)
            return []

        if not response or response.get("s") == "error":
            err = response.get("message", "") if response else ""
            if "token" in err.lower() or "401" in str(err):
                raise TokenExpiredError(
                    "Fyers token expired. Run scripts/fyers_auth.py to refresh."
                )
            log.warning("Fyers empty/error response for %s: %s", symbol, err)
            return []

        candles = []
        for row in response.get("candles", []):
            try:
                ts = datetime.fromtimestamp(row[0], tz=timezone.utc)
                candles.append(OHLC(
                    timestamp=ts,
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                ))
            except Exception as e:
                log.warning("Skipping malformed candle %s: %s", row, e)

        return candles