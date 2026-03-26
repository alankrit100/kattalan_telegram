import os
import uuid
import json
from datetime import datetime
from typing import List, Literal, Optional, Dict
from pydantic import BaseModel, Field
from groq import Groq # <-- Swapped
from dotenv import load_dotenv
from core.schemas import Signal
from google import genai
from google.genai import types


load_dotenv()

# 1. Single Signal Schema
class ExtractedSignal(BaseModel):
    underlying: str = Field(description="The base asset, e.g., BANKNIFTY, NIFTY, RELIANCE")
    instrument_type: Literal["CE", "PE", "EQ", "FUT"] = Field(description="CE for Call, PE for Put, EQ for Equity/Spot, FUT for Futures")
    strike: Optional[int] = Field(description="Strike price if options, null if equity", default=None)
    direction: Literal["BUY", "SELL"]
    entry_price: float
    stop_loss: float
    targets: List[float]

# 2. Batch Signal Schema
class BatchExtractedSignal(ExtractedSignal):
    message_id: str = Field(description="The exact message ID provided in the prompt mapping to this signal")

class BatchResponse(BaseModel):
    valid_signals: List[BatchExtractedSignal] = Field(description="List of valid trading signals found in the batch.")

class SignalParser:
    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("FATAL: Missing GEMINI_API_KEY in .env file.")
        self.client = genai.Client(api_key=api_key)

    def parse(self, raw_text: str, message_time: datetime, channel_id: str, message_id: str):
        """Used by main.py for LIVE incoming messages."""
        prompt = f"""
        Analyze this Telegram trading signal posted on {message_time.strftime('%Y-%m-%d %H:%M:%S')}.
        Extract the exact trading parameters. If NOT a clear signal, fail.
        Raw Text: "{raw_text}"
        """
        try:
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ExtractedSignal,
                    temperature=0.0,
                ),
            )
            extracted = ExtractedSignal.model_validate_json(response.text)
            
            signal = Signal(
                signal_id=f"{channel_id}_{message_id}", # <-- DETERMINISTIC ID FIX
                channel_id=channel_id, 
                message_id=message_id,
                raw_text=raw_text, 
                underlying=extracted.underlying,
                instrument_type=extracted.instrument_type,
                strike=extracted.strike,
                direction=extracted.direction, 
                entry_price=extracted.entry_price,
                stop_loss=extracted.stop_loss, 
                targets=extracted.targets, 
                is_intraday=True, 
                issued_at=message_time
            )
            
            return {"signal": signal, "instrument_data": extracted}
            
        except Exception as e:
            raise ValueError(f"LLM Parsing failed: {e}")

    def parse_batch(self, batch_data: List[Dict], channel_id: str):
        """Used by run_pipeline.py to process HISTORICAL messages at once."""
        if not batch_data: return []

        prompt = """You are a strict quantitative extraction engine. 
I am giving you a batch of Telegram messages.
Find ONLY the messages that contain a CLEAR trading signal.
Return a JSON object with a key 'valid_signals' containing the list of extracted data.

CRITICAL RULES:
1. THE "PAID" STOP LOSS RULE: If the Stop Loss is "PAID", hidden, or missing, calculate a mechanical stop loss: 
   - For BUY signals: 15% below the entry_price (entry_price * 0.85)
   - For SELL signals: 15% above the entry_price (entry_price * 1.15)
   Output this calculated number as the stop_loss float.
2. All price fields MUST be numbers (floats). Absolutely no text.
3. message_id MUST be a string.
4. "instrument_type" MUST strictly be "CE", "PE", "EQ", or "FUT". NEVER use the words "CALL" or "PUT".

Here is the batch:
"""
        for item in batch_data:
            prompt += f"--- MESSAGE ID: {item['message_id']} ---\nText: {item['text']}\n\n"

        try:
            response = self.client.models.generate_content(
                model='gemini-2.5-flash', # Use flash instead of flash-lite for better math reasoning
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=BatchResponse,
                    temperature=0.0,
                ),
            )
            
            parsed_batch = BatchResponse.model_validate_json(response.text)
            results = []
            
            for extracted in parsed_batch.valid_signals:
                original_msg = next((msg for msg in batch_data if str(msg['message_id']) == extracted.message_id), None)
                if not original_msg: continue
                    
                signal = Signal(
                    signal_id=f"{channel_id}_{extracted.message_id}", # <-- DETERMINISTIC ID FIX
                    channel_id=channel_id, 
                    message_id=extracted.message_id, 
                    raw_text=original_msg['text'],
                    underlying=extracted.underlying,
                    instrument_type=extracted.instrument_type,
                    strike=extracted.strike,
                    direction=extracted.direction, 
                    entry_price=extracted.entry_price,
                    stop_loss=extracted.stop_loss, 
                    targets=extracted.targets, 
                    is_intraday=True, 
                    issued_at=original_msg['time']
                )
                results.append({"signal": signal, "instrument_data": extracted})
                
            return results
        except Exception as e:
            raise ValueError(f"Batch Gemini Parsing failed: {e}")