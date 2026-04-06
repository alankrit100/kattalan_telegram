import pytest
from datetime import datetime, timezone
from core.schemas import Signal, OHLC
from core.quant_engine import QuantEngine


def ts(h, m):
    """Timezone-aware timestamp for tests."""
    return datetime(2023, 1, 2, h, m, tzinfo=timezone.utc)


def make_signal(**kwargs):
    defaults = dict(
        channel_id="TEST_CH",
        message_id="TEST_MSG",
        raw_text="mock signal",
        underlying="BANKNIFTY",
        instrument_type="EQ",
        direction="BUY",
        entry_price=100.0,
        targets=[110.0],
        stop_loss=90.0,
        is_intraday=True,
        issued_at=ts(9, 15),
    )
    defaults.update(kwargs)
    return Signal(**defaults)


@pytest.fixture
def engine():
    return QuantEngine()


def test_wick_conflict_evaluates_to_loss(engine):
    signal = make_signal(entry_price=100.0, targets=[110.0], stop_loss=90.0)
    market_data = [
        OHLC(timestamp=ts(9, 16), open=95.0, high=99.0, low=92.0, close=98.0),
        OHLC(timestamp=ts(9, 17), open=98.0, high=102.0, low=98.0, close=101.0),
        OHLC(timestamp=ts(9, 18), open=101.0, high=112.0, low=88.0, close=105.0),
    ]
    result = engine.evaluate(signal, market_data)
    assert result.status == "LOSS"
    assert result.exit_executed_price == 90.0
    assert "WICK CONFLICT" in result.reason


def test_multi_target_trailing_sl(engine):
    signal = make_signal(entry_price=100.0, targets=[110.0, 120.0], stop_loss=90.0)
    market_data = [
        OHLC(timestamp=ts(10, 1), open=99.0, high=101.0, low=99.0, close=100.5),
        OHLC(timestamp=ts(10, 2), open=100.5, high=111.0, low=100.0, close=109.0),
        OHLC(timestamp=ts(10, 3), open=109.0, high=110.0, low=95.0, close=96.0),
    ]
    result = engine.evaluate(signal, market_data)
    assert result.status == "WIN"
    assert result.exit_executed_price == 100.0
    assert "STOP LOSS HIT" in result.reason


def test_intraday_auto_square_off(engine):
    signal = make_signal(direction="SELL", entry_price=200.0, targets=[180.0], stop_loss=210.0)
    market_data = [
        OHLC(timestamp=ts(14, 5), open=202.0, high=202.0, low=199.0, close=200.0),
        OHLC(timestamp=ts(15, 14), open=195.0, high=196.0, low=194.0, close=195.0),
        OHLC(timestamp=ts(15, 15), open=195.0, high=195.0, low=192.0, close=193.0),
    ]
    result = engine.evaluate(signal, market_data)
    assert result.status == "SQUARED_OFF"
    assert result.exit_executed_price == 193.0


def test_entry_never_triggered_returns_expired(engine):
    """Req: if entry price never touched, status = EXPIRED."""
    signal = make_signal(entry_price=200.0, targets=[210.0], stop_loss=190.0)
    market_data = [
        OHLC(timestamp=ts(9, 16), open=100.0, high=110.0, low=99.0, close=105.0),
        OHLC(timestamp=ts(9, 17), open=105.0, high=115.0, low=104.0, close=110.0),
    ]
    result = engine.evaluate(signal, market_data)
    assert result.status == "EXPIRED"
    assert result.entry_executed_price is None
    assert result.pnl_percentage == 0.0


def test_option_mfe_tracking(engine):
    """Req: CE options enter immediately and track directional MFE/MAE on spot."""
    signal = make_signal(
        instrument_type="CE",
        direction="BUY",
        entry_price=48000.0,
        targets=[48200.0],
        stop_loss=47800.0,
    )
    market_data = [
        OHLC(timestamp=ts(10, 0), open=48000.0, high=48150.0, low=47950.0, close=48100.0),
        OHLC(timestamp=ts(10, 1), open=48100.0, high=48300.0, low=48050.0, close=48250.0),
    ]
    result = engine.evaluate(signal, market_data)
    # Entry at 48000 open, T1=48200 hit in candle 2 high=48300
    assert result.status == "WIN"
    assert result.entry_executed_price == 48000.0
    assert result.max_favorable_excursion >= 200.0  # at least 48200-48000
    assert result.max_adverse_excursion >= 0.0


def test_empty_market_data_returns_expired(engine):
    signal = make_signal()
    result = engine.evaluate(signal, [])
    assert result.status == "EXPIRED"


def test_sell_signal_win(engine):
    signal = make_signal(direction="SELL", entry_price=200.0, targets=[190.0], stop_loss=205.0)
    market_data = [
        OHLC(timestamp=ts(9, 16), open=201.0, high=202.0, low=199.0, close=200.0),
        OHLC(timestamp=ts(9, 17), open=200.0, high=200.0, low=188.0, close=190.0),
    ]
    result = engine.evaluate(signal, market_data)
    assert result.status == "WIN"
    assert result.pnl_percentage > 0