import os
import asyncio
import json
import logging
from typing import List, Dict, Optional, Literal
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from google.api_core.exceptions import ResourceExhausted

from core.schemas import Signal, make_signal_id

log = logging.getLogger(__name__)

BATCH_SIZE = int(os.environ.get("GEMINI_BATCH_SIZE", "25"))

_PROMPT_PREFIX = """You are a strict quantitative extraction engine for Indian equity/commodity markets.
I am giving you a batch of Telegram messages. Find ONLY messages with a CLEAR trading signal.
Return JSON: {"valid_signals": [...]}

RULES:
1. PAID/HIDDEN SL: compute mechanically. BUY → entry*0.85, SELL → entry*1.15
2. All price fields MUST be floats. No text.
3. message_id MUST be the exact string from the batch.
4. instrument_type: ONLY "EQ" or "FUT". If the message is an options trade (CE, PE, CALL, PUT), OMIT IT ENTIRELY.
5. Normalise underlying to official NSE/BSE/MCX ticker. Examples:
   adaniprt→ADANIPORTS, sbi→SBIN, crude→CRUDEOIL, nifty bank→BANKNIFTY
6. Messages may be in English, Hindi, or mixed language.
7. If a message is not a trade signal, omit it entirely.

BATCH:
"""

class _ExtractedSignal(BaseModel):
    message_id: str
    underlying: str
    instrument_type: Literal["EQ", "FUT"]
    strike: Optional[int] = None
    direction: Literal["BUY", "SELL"]
    entry_price: float
    stop_loss: float
    targets: List[float]

class _BatchResponse(BaseModel):
    valid_signals: List[_ExtractedSignal] = Field(default_factory=list)


class SignalParser:
    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("FATAL: Missing GEMINI_API_KEY")
        self.client = genai.Client(api_key=api_key)
        self.model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")

    async def parse_all(
        self,
        messages: List[Dict],
        channel_id: str,
        mark_processed_fn=None,
    ) -> List[Dict]:
        """
        Splits messages into batches, dispatches all batches concurrently,
        returns flat list of {"signal": Signal, ...} dicts.
        """
        batches = [
            messages[i: i + BATCH_SIZE]
            for i in range(0, len(messages), BATCH_SIZE)
        ]
        tasks = [
            self._parse_batch(batch, channel_id, mark_processed_fn)
            for batch in batches
        ]
        results_nested = await asyncio.gather(*tasks, return_exceptions=True)

        flat = []
        for r in results_nested:
            if isinstance(r, Exception):
                log.error("Batch parse error: %s", r)
            else:
                flat.extend(r)
        return flat

    async def _parse_batch(
        self,
        batch: List[Dict],
        channel_id: str,
        mark_processed_fn=None,
    ) -> List[Dict]:
        if not batch:
            return []

        prompt = _PROMPT_PREFIX
        for item in batch:
            prompt += f"--- MESSAGE ID: {item['message_id']} ---\n{item['text']}\n\n"

        raw_text = await self._call_gemini_with_backoff(prompt)
        if raw_text is None:
            # Mark all as unprocessed so they can be retried
            if mark_processed_fn:
                for item in batch:
                    asyncio.create_task(
                        mark_processed_fn(channel_id, item["message_id"], False)
                    )
            return []

        try:
            clean = raw_text.replace("```json", "").replace("```", "").strip()
            parsed = _BatchResponse.model_validate_json(clean)
        except Exception as e:
            log.error("JSON parse failed for batch: %s | raw: %.200s", e, raw_text)
            if mark_processed_fn:
                for item in batch:
                    asyncio.create_task(
                        mark_processed_fn(channel_id, item["message_id"], False)
                    )
            return []

        msg_map = {str(m["message_id"]): m for m in batch}
        results = []

        for extracted in parsed.valid_signals:
            original = msg_map.get(extracted.message_id)
            if not original:
                continue

            # Sort targets per direction
            extracted.targets = (
                sorted(extracted.targets)
                if extracted.direction == "BUY"
                else sorted(extracted.targets, reverse=True)
            )

            try:
                signal = Signal(
                    channel_id=channel_id,
                    message_id=extracted.message_id,
                    raw_text=original["text"],
                    underlying=extracted.underlying,
                    instrument_type=extracted.instrument_type,
                    strike=extracted.strike,
                    direction=extracted.direction,
                    entry_price=extracted.entry_price,
                    stop_loss=extracted.stop_loss,
                    targets=extracted.targets,
                    is_intraday=True,
                    issued_at=original["time"],
                )
            except Exception as e:
                log.warning("Signal validation failed (msg %s): %s", extracted.message_id, e)
                if mark_processed_fn:
                    asyncio.create_task(
                        mark_processed_fn(channel_id, extracted.message_id, False)
                    )
                continue

            if mark_processed_fn:
                asyncio.create_task(
                    mark_processed_fn(channel_id, extracted.message_id, True)
                )
            results.append({"signal": signal})

        # Mark non-signal messages
        parsed_ids = {e.message_id for e in parsed.valid_signals}
        if mark_processed_fn:
            for item in batch:
                if item["message_id"] not in parsed_ids:
                    asyncio.create_task(
                        mark_processed_fn(channel_id, item["message_id"], False)
                    )

        return results

    async def _call_gemini_with_backoff(self, prompt: str) -> str | None:
        for attempt in range(3):
            try:
                response = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=_BatchResponse,
                        temperature=0.0,
                    ),
                )
                return response.text
            except ResourceExhausted:
                wait = 2 ** (attempt + 1)
                log.warning("Gemini 429. Waiting %ds (attempt %d/3)", wait, attempt + 1)
                await asyncio.sleep(wait)
            except Exception as e:
                log.error("Gemini call failed: %s", e)
                return None
        log.error("Gemini failed after 3 attempts.")
        return None