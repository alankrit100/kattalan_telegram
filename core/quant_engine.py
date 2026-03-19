from typing import List
from datetime import time
from core.schemas import Signal, OHLC, EvaluationResult

class QuantEngine:
    def __init__(self):
        self.market_open = time(9, 15)
        self.market_close = time(15, 30)
        self.auto_square_off = time(15, 15)

    def evaluate(self, signal: Signal, market_data: List[OHLC]) -> EvaluationResult:
        trace = []
        status = "PENDING"
        entry_time = None
        exit_time = None
        executed_entry = None
        executed_exit = None
        
        mfe = 0.0 # Max Favorable Excursion
        mae = 0.0 # Max Adverse Excursion
        
        current_sl = signal.stop_loss
        active_target_idx = 0
        is_active = False

        trace.append(f"INIT: Evaluating {signal.direction} signal at {signal.entry_price}.")

        for candle in market_data:
            c_time = candle.timestamp.time()
            
            # Market hours check
            if c_time < self.market_open or c_time > self.market_close:
                continue

            # 1. ENTRY LOGIC
            if not is_active:
                if candle.low <= signal.entry_price <= candle.high:
                    is_active = True
                    entry_time = candle.timestamp
                    executed_entry = signal.entry_price
                    trace.append(f"[{c_time}] ENTRY TRIGERRED at {executed_entry}.")
                continue

            # 2. EXCURSION TRACKING
            assert executed_entry is not None, "Executed entry price should be set after entry is triggered."
            if signal.direction == "BUY":
                curr_mfe = candle.high - executed_entry
                curr_mae = executed_entry - candle.low
            else: # SELL
                curr_mfe = executed_entry - candle.low
                curr_mae = candle.high - executed_entry
                
            mfe = max(mfe, curr_mfe)
            mae = max(mae, curr_mae)

            # 3. AUTO-SQUARE OFF (Intraday)
            if signal.is_intraday and c_time >= self.auto_square_off:
                status = "SQUARED_OFF"
                exit_time = candle.timestamp
                executed_exit = candle.close
                trace.append(f"[{c_time}] INTRADAY SQAURE-OFF at {executed_exit}. SL was {current_sl}.")
                break

            # 4. TARGET & STOP LOSS LOGIC
            hit_sl = False
            hit_target = False

            if signal.direction == "BUY":
                if candle.low <= current_sl: hit_sl = True
                if active_target_idx < len(signal.targets) and candle.high >= signal.targets[active_target_idx]: 
                    hit_target = True
            else: # SELL
                if candle.high >= current_sl: hit_sl = True
                if active_target_idx < len(signal.targets) and candle.low <= signal.targets[active_target_idx]: 
                    hit_target = True

            # Resolution
            if hit_sl and hit_target:
                status = "LOSS"
                exit_time = candle.timestamp
                executed_exit = current_sl
                trace.append(f"[{c_time}] WICK CONFLICT: Both Target and SL hit. Defaulting to worst-case (LOSS) at {executed_exit}.")
                break
                
            elif hit_sl:
                status = "LOSS" if active_target_idx == 0 else "WIN"
                exit_time = candle.timestamp
                executed_exit = current_sl
                trace.append(f"[{c_time}] STOP LOSS HIT at {executed_exit}.")
                break
                
            elif hit_target:
                hit_price = signal.targets[active_target_idx]
                trace.append(f"[{c_time}] TARGET {active_target_idx + 1} HIT at {hit_price}.")
                
                if active_target_idx == 0:
                    current_sl = executed_entry
                    trace.append(f"[{c_time}] SL trailed to Entry ({current_sl}).")
                else:
                    current_sl = signal.targets[active_target_idx - 1]
                    trace.append(f"[{c_time}] SL trailed to previous Target ({current_sl}).")
                
                active_target_idx += 1
                
                if active_target_idx >= len(signal.targets):
                    status = "WIN"
                    exit_time = candle.timestamp
                    executed_exit = hit_price
                    trace.append(f"[{c_time}] ALL TARGETS CLEARED. Exiting at {executed_exit}.")
                    break

        # 5. END OF DATA CHECK
        if status == "PENDING":
            if not is_active:
                status = "EXPIRED"
                trace.append("DATA ENDED: Entry never triggered.")
            else:
                trace.append("DATA ENDED: Signal active but unresolved.")

        return EvaluationResult(
            signal_id=signal.signal_id,
            status=status,
            entry_time=entry_time,
            exit_time=exit_time,
            entry_executed_price=executed_entry,
            exit_executed_price=executed_exit,
            max_favorable_excursion=mfe,
            max_adverse_excursion=mae,
            reason=trace[-1] if trace else "Unknown",
            trace_log=trace
        )