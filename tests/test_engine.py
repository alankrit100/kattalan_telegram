import pytest
from datetime import datetime
from core.schemas import Signal, OHLC
from core.quant_engine import QuantEngine

def make_time(h, m):
    return datetime(2023, 1, 1, h, m)

@pytest.fixture
def engine():
    return QuantEngine()

def test_wick_conflict_evaluates_to_loss(engine):
    signal = Signal(
        signal_id="KAT-001",
        channel_id="TEST_CH", # Added ID
        message_id="TEST_MSG", # Added ID
        direction="BUY",
        entry_price=100.0,
        targets=[110.0],
        stop_loss=90.0,
        is_intraday=True,
        issued_at=make_time(9, 15)
    )
    
    market_data = [
        OHLC(timestamp=make_time(9, 16), open=95.0, high=99.0, low=92.0, close=98.0), 
        OHLC(timestamp=make_time(9, 17), open=98.0, high=102.0, low=98.0, close=101.0), 
        OHLC(timestamp=make_time(9, 18), open=101.0, high=112.0, low=88.0, close=105.0), 
    ]
    
    result = engine.evaluate(signal, market_data)
    
    assert result.status == "LOSS"
    assert result.exit_executed_price == 90.0
    assert "WICK CONFLICT" in result.reason

def test_multi_target_trailing_sl(engine):
    signal = Signal(
        signal_id="KAT-002",
        channel_id="TEST_CH", # Added ID
        message_id="TEST_MSG", # Added ID
        direction="BUY",
        entry_price=100.0,
        targets=[110.0, 120.0],
        stop_loss=90.0,
        is_intraday=True,
        issued_at=make_time(10, 0)
    )
    
    market_data = [
        OHLC(timestamp=make_time(10, 1), open=99.0, high=101.0, low=99.0, close=100.5), 
        OHLC(timestamp=make_time(10, 2), open=100.5, high=111.0, low=100.0, close=109.0), 
        OHLC(timestamp=make_time(10, 3), open=109.0, high=110.0, low=95.0, close=96.0), 
    ]
    
    result = engine.evaluate(signal, market_data)
    
    assert result.status == "WIN" 
    assert result.exit_executed_price == 100.0
    assert "STOP LOSS HIT" in result.reason

def test_intraday_auto_square_off(engine):
    signal = Signal(
        signal_id="KAT-003",
        channel_id="TEST_CH", # Added ID
        message_id="TEST_MSG", # Added ID
        direction="SELL", 
        entry_price=200.0,
        targets=[180.0],
        stop_loss=210.0,
        is_intraday=True,
        issued_at=make_time(14, 0)
    )
    
    market_data = [
        OHLC(timestamp=make_time(14, 5), open=202.0, high=202.0, low=199.0, close=200.0), 
        OHLC(timestamp=make_time(15, 14), open=195.0, high=196.0, low=194.0, close=195.0), 
        OHLC(timestamp=make_time(15, 15), open=195.0, high=195.0, low=192.0, close=193.0), 
    ]
    
    result = engine.evaluate(signal, market_data)
    
    assert result.status == "SQUARED_OFF"
    assert result.exit_executed_price == 193.0
    assert "INTRADAY SQAURE-OFF" in result.reason