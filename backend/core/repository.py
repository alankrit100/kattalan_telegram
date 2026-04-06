import os
import asyncio
import logging
from datetime import timezone
from supabase import create_client, Client
from core.schemas import Signal, EvaluationResult

log = logging.getLogger(__name__)


class RepositoryError(Exception):
    def __init__(self, message: str, original: Exception = None):
        super().__init__(message)
        self.original = original


class SupabaseRepository:
    def __init__(self):
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        if not url or not key:
            raise ValueError("FATAL: Missing SUPABASE_URL or SUPABASE_KEY in .env")
        self.supabase: Client = create_client(url, key)
        
        # Use single underscore to avoid strict python name mangling
        self._db_semaphore = asyncio.Semaphore(15)

    def get_unseen_messages(self, channel_id: str, message_ids: list[str]) -> list[str]:
        """
        Returns subset of message_ids not yet in processed_messages for this channel.
        Set-difference executed in Postgres via LEFT JOIN / IS NULL.
        """
        if not message_ids:
            return []
        try:
            # Use Postgres unnest + LEFT JOIN to do the set-difference server-side
            # Supabase Python SDK doesn't support unnest directly, so we use rpc
            response = self.supabase.rpc(
                "get_unseen_message_ids",
                {"p_channel_id": channel_id, "p_message_ids": message_ids},
            ).execute()
            return [row["message_id"] for row in (response.data or [])]
        except Exception as e:
            log.error("get_unseen_messages failed: %s", e)
            raise RepositoryError("Failed to query unseen messages", e)

    def upsert_signal(self, signal: Signal):
        try:
            data = signal.model_dump()
            data["issued_at"] = _to_utc_iso(data["issued_at"])
            response = self.supabase.table("signals").upsert(
                data, on_conflict="signal_id"
            ).execute()
            if response.data is None:
                raise RepositoryError("upsert_signal returned no data")
            return response
        except RepositoryError:
            raise
        except Exception as e:
            log.error("upsert_signal failed for %s: %s", signal.signal_id, e)
            raise RepositoryError(f"upsert_signal failed: {e}", e)

    def upsert_evaluation(self, result: EvaluationResult):
        try:
            data = result.model_dump()
            data["entry_time"] = _to_utc_iso(data["entry_time"])
            data["exit_time"] = _to_utc_iso(data["exit_time"])
            response = self.supabase.table("evaluations").upsert(
                data, on_conflict="signal_id"
            ).execute()
            if response.data is None:
                raise RepositoryError("upsert_evaluation returned no data")
            return response
        except RepositoryError:
            raise
        except Exception as e:
            log.error("upsert_evaluation failed for %s: %s", result.signal_id, e)
            raise RepositoryError(f"upsert_evaluation failed: {e}", e)

    def get_evaluations_by_channel(self, channel_id: str) -> list[EvaluationResult]:
        """Fetches all past evaluations for a specific channel to build the final audit card."""
        try:
            # 1. Get all signal IDs belonging to this channel
            sig_res = self.supabase.table("signals").select("signal_id").eq("channel_id", channel_id).execute()
            sig_ids = [row["signal_id"] for row in (sig_res.data or [])]
            
            if not sig_ids:
                return []
                
            # 2. Fetch the evaluations matching those IDs
            eval_res = self.supabase.table("evaluations").select("*").in_("signal_id", sig_ids).execute()
            
            # 3. Convert raw database rows back into Pydantic models
            return [EvaluationResult(**row) for row in (eval_res.data or [])]
        except Exception as e:
            log.error("Failed to fetch historical evaluations: %s", e)
            return []

    async def mark_processed(self, channel_id: str, message_id: str, is_signal: bool):
        """Fire-and-forget — guarded by semaphore to prevent socket exhaustion."""
        try:
            # The async with lock forces Python to wait if 15 DB calls are already happening
            async with self._db_semaphore:
                await asyncio.to_thread(
                    self._sync_mark_processed, channel_id, message_id, is_signal
                )
        except Exception as e:
            log.error("mark_processed failed (%s, %s): %s", channel_id, message_id, e)

    def _sync_mark_processed(self, channel_id: str, message_id: str, is_signal: bool):
        self.supabase.table("processed_messages").upsert(
            {"channel_id": channel_id, "message_id": message_id, "is_signal": is_signal},
            on_conflict="channel_id,message_id",
        ).execute()


def _to_utc_iso(dt) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()