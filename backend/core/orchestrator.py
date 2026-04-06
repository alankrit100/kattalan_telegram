import os
import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Callable

from core.parser import SignalParser
from core.quant_engine import QuantEngine
from core.repository import SupabaseRepository, RepositoryError
from core.schemas import ChannelAuditResult, EvaluationResult
from data.provider_base import MarketDataProvider
from data.fyers_provider import build_fyers_symbol

log = logging.getLogger(__name__)

_LOOKBACK = int(os.environ.get("LOOKBACK_MONTHS", "6"))
_SEM_LIMIT = int(os.environ.get("SEMAPHORE_LIMIT", "8"))


class KattalanOrchestrator:
    def __init__(self, data_provider: MarketDataProvider):
        self.db = SupabaseRepository()
        self.provider = data_provider
        self.parser = SignalParser()
        self.engine = QuantEngine()
        self.semaphore = asyncio.Semaphore(_SEM_LIMIT)

    async def audit_channel(
        self,
        channel_input: str,
        timeframe_months: int,
        raw_messages: list,
        resolved_id: str,
        resolved_name: str,
        ws_send: Callable,
    ) -> ChannelAuditResult:
        total_msgs = len(raw_messages)
        channel_id = resolved_id or channel_input

        async def emit(progress: int, status: str, results=None):
            frame = {"progress": progress, "status": status}
            if results:
                frame["results"] = results
            try:
                await ws_send(json.dumps(frame))
            except Exception:
                pass  # Client disconnected — continue pipeline, results saved to DB

        if total_msgs == 0:
            await emit(100, "No messages found in timeframe.")
            return ChannelAuditResult(
                channel_name=resolved_name or channel_input,
                channel_id=channel_id,
                total_messages_scraped=0,
            )

        await emit(15, f"Scraped {total_msgs} messages. Checking cache...")

        # --- SPAM CACHE: get only unseen message IDs ---
        all_ids = [m["message_id"] for m in raw_messages]
        try:
            unseen_ids = set(self.db.get_unseen_messages(channel_id, all_ids))
        except RepositoryError:
            log.warning("Spam cache unavailable — processing all messages.")
            unseen_ids = set(all_ids)

        unseen_messages = [m for m in raw_messages if m["message_id"] in unseen_ids]
        await emit(25, f"{len(unseen_messages)} new messages to parse ({total_msgs - len(unseen_messages)} cached).")

        # --- PARSE ---
        all_signals = await self.parser.parse_all(
            unseen_messages,
            channel_id,
            mark_processed_fn=self.db.mark_processed,
        )
        await emit(40, f"Parsed {len(all_signals)} valid signals.")

        # --- FETCH MARKET DATA & EVALUATE (ONLY FOR NEW SIGNALS) ---
        if all_signals:
            await emit(70, f"Fetching market data for {len(all_signals)} new signals...")
            
            fyers_rate_limiter = asyncio.Semaphore(5)  # Fyers allows 5 requests/sec — this is a simple in-memory throttle
            
            # 1. Parallelize Fyers Network Calls
            async def fetch_data(item):
                sig = item["signal"]
                symbol = build_fyers_symbol(sig.underlying, sig.instrument_type)
                end_of_day = sig.issued_at.replace(hour=15, minute=30, second=0, microsecond=0)
                if end_of_day.tzinfo is None:
                    end_of_day = end_of_day.replace(tzinfo=timezone.utc)
                
                # Prevent Fyers SDK from blocking the main thread
                data = await asyncio.to_thread(
                    self.provider.fetch_1m_data, symbol, sig.issued_at, end_of_day
                )
                return sig.signal_id, data

            fetch_tasks = [fetch_data(item) for item in all_signals]
            fetch_results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

            candles_map: dict[str, list] = {}
            for res in fetch_results:
                if isinstance(res, Exception):
                    log.error("Fyers fetch failed: %s", res)
                else:
                    candles_map[res[0]] = res[1]

            # 2. Parallelize Quant Engine Math
            async def evaluate_one(item):
                sig = item["signal"]
                candles = candles_map.get(sig.signal_id, [])
                async with self.semaphore:
                    return await asyncio.to_thread(self.engine.evaluate, sig, candles)

            tasks = [evaluate_one(item) for item in all_signals]
            eval_results: list[EvaluationResult] = await asyncio.gather(*tasks, return_exceptions=True)

            await emit(90, "Evaluations complete. Saving new results to database...")

            for item, result in zip(all_signals, eval_results):
                if isinstance(result, Exception):
                    log.error("evaluate() raised: %s", result)
                    continue
                try:
                    self.db.upsert_signal(item["signal"])
                    self.db.upsert_evaluation(result)
                except RepositoryError as e:
                    log.error("DB write failed for %s: %s", result.signal_id, e)

        # --- AGGREGATE ALL HISTORICAL DATA FOR THIS CHANNEL ---
        await emit(95, "Aggregating historical audit data...")
        
        # Pull everything we have ever evaluated for this channel
        all_evals = self.db.get_evaluations_by_channel(channel_id)
        
        if not all_evals:
            await emit(100, "No valid trade signals found.")
            return ChannelAuditResult(
                channel_name=resolved_name or channel_input,
                channel_id=channel_id,
                total_messages_scraped=total_msgs,
            )

        wins = losses = squared = expired = 0
        win_pnls, loss_pnls, mfes, maes = [], [], [], []

        for result in all_evals:
            if result.status == "WIN":
                wins += 1
                win_pnls.append(result.pnl_percentage)
            elif result.status == "LOSS":
                losses += 1
                loss_pnls.append(result.pnl_percentage)
            elif result.status == "SQUARED_OFF":
                squared += 1
            elif result.status == "EXPIRED":
                expired += 1

            mfes.append(result.max_favorable_excursion)
            maes.append(result.max_adverse_excursion)

        decided = wins + losses
        win_rate = (wins / decided * 100) if decided > 0 else 0.0

        avg_win = (sum(win_pnls) / len(win_pnls)) if win_pnls else 0.0
        avg_loss = (sum(loss_pnls) / len(loss_pnls)) if loss_pnls else 0.0
        #prevent 0.0 edge ration if channel as a 100% win rate:
        if avg_loss != 0:
            edge_ratio = avg_win / abs(avg_loss)
        else:
            edge_ratio = avg_win if avg_win > 0 else 0.0
            
        audit = ChannelAuditResult(
            channel_name=resolved_name or channel_input,
            channel_id=channel_id,
            total_messages_scraped=total_msgs,
            total_trades=decided,
            total_wins=wins,
            total_losses=losses,
            total_squared_off=squared,
            total_expired=expired,
            win_rate_pct=round(win_rate, 2),
            edge_ratio=round(edge_ratio, 3),
            avg_mfe=round(sum(mfes) / len(mfes), 2) if mfes else 0.0,
            avg_mae=round(sum(maes) / len(maes), 2) if maes else 0.0,
        )

        await emit(100, "Audit complete.", results=audit.model_dump())
        return audit