import logging
from typing import List
from datetime import time
from core.schemas import Signal, OHLC, EvaluationResult

log = logging.getLogger(__name__)

_OPEN = time(9, 15)
_CLOSE = time(15, 30)
_SQUAREOFF = time(15, 15)

class QuantEngineLegacy:
    """Archived engine containing the spot-tracking logic for CE/PE options."""
    def evaluate(self, signal: Signal, market_data: List[OHLC]) -> EvaluationResult:
        trace = []
        status = "PENDING"
        entry_time = exit_time = None
        executed_entry = executed_exit = None
        mfe = mae = 0.0
        current_sl = signal.stop_loss
        active_target_idx = 0
        is_active = False
        is_option = signal.instrument_type in ("CE", "PE")
        is_buy_dir = signal.direction == "BUY" or signal.instrument_type == "CE"

        trace.append(f"INIT: {signal.instrument_type} {signal.direction} | entry={signal.entry_price}")

        if not market_data:
            return self._result(signal, "EXPIRED", trace, entry_time, exit_time, executed_entry, executed_exit, mfe, mae)

        for candle in market_data:
            c_time = candle.timestamp.time()
            if c_time < _OPEN or c_time > _CLOSE: continue

            # --- ENTRY ---
            if not is_active:
                if is_option:
                    is_active = True
                    entry_time = candle.timestamp
                    executed_entry = candle.open
                    trace.append(f"[{c_time}] OPTION ENTRY at spot {executed_entry}")
                else:
                    if signal.direction == "BUY" and candle.high >= signal.entry_price:
                        is_active = True
                        entry_time = candle.timestamp
                        executed_entry = max(candle.open, signal.entry_price)
                        trace.append(f"[{c_time}] BUY ENTRY at {executed_entry}")
                    elif signal.direction == "SELL" and candle.low <= signal.entry_price:
                        is_active = True
                        entry_time = candle.timestamp
                        executed_entry = min(candle.open, signal.entry_price)
                        trace.append(f"[{c_time}] SELL ENTRY at {executed_entry}")
                if not is_active: continue

            # --- MFE / MAE ---
            if executed_entry is None: break

            if is_buy_dir:
                mfe = max(mfe, candle.high - executed_entry)
                mae = max(mae, executed_entry - candle.low)
            else:
                mfe = max(mfe, executed_entry - candle.low)
                mae = max(mae, candle.high - executed_entry)

            # --- AUTO SQUARE-OFF ---
            if signal.is_intraday and c_time >= _SQUAREOFF:
                status = "SQUARED_OFF"
                exit_time = candle.timestamp
                executed_exit = candle.close
                trace.append(f"[{c_time}] SQUARED OFF at {executed_exit}. MFE={mfe:.2f} MAE={mae:.2f}")
                break

            # --- TARGET & SL LOGIC ---
            hit_sl = hit_tgt = False
            hit_price = 0.0
            sl_execution_price = current_sl

            if signal.direction == "BUY" or signal.instrument_type == "CE":
                if candle.low <= current_sl:
                    hit_sl = True
                    sl_execution_price = min(candle.open, current_sl)
                if active_target_idx < len(signal.targets) and candle.high >= signal.targets[active_target_idx]:
                    hit_tgt = True
                    hit_price = max(candle.open, signal.targets[active_target_idx])
            else:
                if candle.high >= current_sl:
                    hit_sl = True
                    sl_execution_price = max(candle.open, current_sl)
                if active_target_idx < len(signal.targets) and candle.low <= signal.targets[active_target_idx]:
                    hit_tgt = True
                    hit_price = min(candle.open, signal.targets[active_target_idx])

            if hit_sl and hit_tgt:
                status = "LOSS"
                exit_time = candle.timestamp
                executed_exit = sl_execution_price
                trace.append(f"[{c_time}] WICK CONFLICT: Worst-case LOSS at {executed_exit}.")
                break
            elif hit_sl:
                status = "LOSS" if active_target_idx == 0 else "WIN"
                exit_time = candle.timestamp
                executed_exit = sl_execution_price
                trace.append(f"[{c_time}] STOP LOSS HIT at {executed_exit}.")
                break
            elif hit_tgt:
                trace.append(f"[{c_time}] TARGET {active_target_idx + 1} HIT at {hit_price}.")
                current_sl = executed_entry if active_target_idx == 0 else signal.targets[active_target_idx - 1]
                active_target_idx += 1
                if active_target_idx >= len(signal.targets):
                    status = "WIN"
                    exit_time = candle.timestamp
                    executed_exit = hit_price
                    trace.append(f"[{c_time}] ALL TARGETS CLEARED. Exit {executed_exit}.")
                    break

        if status == "PENDING":
            if not is_active:
                status = "EXPIRED"
                trace.append("DATA ENDED: Entry never triggered → EXPIRED.")
            else:
                status = "SQUARED_OFF"
                executed_exit = market_data[-1].close if market_data else executed_entry
                trace.append("DATA ENDED: Active signal closed at last candle → SQUARED_OFF.")

        return self._result(signal, status, trace, entry_time, exit_time, executed_entry, executed_exit, mfe, mae)

    @staticmethod
    def _result(signal, status, trace, entry_time, exit_time, executed_entry, executed_exit, mfe, mae):
        pnl = 0.0
        if status in ("WIN", "LOSS", "SQUARED_OFF") and executed_entry and executed_exit:
            if signal.direction == "BUY" or signal.instrument_type == "CE":
                pnl = (executed_exit - executed_entry) / executed_entry * 100.0
            else:
                pnl = (executed_entry - executed_exit) / executed_entry * 100.0

        return EvaluationResult(
            signal_id=signal.signal_id, status=status, entry_time=entry_time, exit_time=exit_time,
            entry_executed_price=executed_entry, exit_executed_price=executed_exit,
            pnl_percentage=round(pnl, 4), max_favorable_excursion=round(mfe, 4), max_adverse_excursion=round(mae, 4),
            reason=trace[-1] if trace else "Unknown", trace_log=trace,
        )