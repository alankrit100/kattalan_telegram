import os
import uuid
from datetime import datetime
from typing import List, Literal, Optional, Dict
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from dotenv import load_dotenv
from core.schemas import Signal

load_dotenv()

# 1. Single Signal Schema
class ExtractedSignal(BaseModel):
    underlying: str = Field(description="The base asset, e.g., BANKNIFTY, NIFTY, RELIANCE")
    instrument_type: Literal["CE", "PE", "EQ"] = Field(description="CE for Call, PE for Put, EQ for Equity/Spot")
    strike: Optional[int] = Field(description="Strike price if options, null if equity", default=None)
    direction: Literal["BUY", "SELL"]
    entry_price: float
    stop_loss: float
    targets: List[float]

# 2. Batch Signal Schema (Maps back to the Telegram message ID)
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
                model='gemini-2.5-flash-lite',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ExtractedSignal,
                    temperature=0.0,
                ),
            )
            extracted = ExtractedSignal.model_validate_json(response.text)
            
            # --- THE FIX: Fully populated Signal object ---
            signal = Signal(
                signal_id=str(uuid.uuid4()), 
                channel_id=channel_id, 
                message_id=message_id,
                raw_text=raw_text, 
                underlying=extracted.underlying,             # NEW
                instrument_type=extracted.instrument_type,   # NEW
                strike=extracted.strike,                     # NEW
                direction=extracted.direction, 
                entry_price=extracted.entry_price,
                stop_loss=extracted.stop_loss, 
                targets=extracted.targets, 
                is_intraday=True, 
                issued_at=message_time
            )
            
            # --- THE FIX: Return the dictionary contract ---
            return {"signal": signal, "instrument_data": extracted}
            
        except Exception as e:
            raise ValueError(f"LLM Parsing failed: {e}")

    def parse_batch(self, batch_data: List[Dict], channel_id: str):
        """Used by run_pipeline.py to process HISTORICAL messages at once."""
        if not batch_data: return []

        prompt = """You are a strict quantitative extraction engine. 
I am giving you a batch of Telegram messages. Most of them are useless spam.
Find ONLY the messages that contain a CLEAR trading signal.
A clear signal MUST have:
1. An instrument (e.g., BANKNIFTY, RELIANCE)
2. A direction (BUY or SELL)
3. An entry price
4. A stop loss (SL)
5. At least one target (TGT)

For every valid signal you find, extract the data and include the EXACT 'message_id' I provided. If a message is spam, conversational, or missing exact numbers, IGNORE IT completely.

Here is the batch:
"""
        for item in batch_data:
            prompt += f"--- MESSAGE ID: {item['message_id']} ---\nText: {item['text']}\n\n"

        try:
            response = self.client.models.generate_content(
                model='gemini-2.5-flash-lite',
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
                original_msg = next((msg for msg in batch_data if msg['message_id'] == extracted.message_id), None)
                if not original_msg: continue
                    
                signal = Signal(
                    signal_id=str(uuid.uuid4()), 
                    channel_id=channel_id, 
                    message_id=extracted.message_id, # Or message_id for the single parse method
                    raw_text=original_msg['text'],   # Or raw_text for the single parse method
                    underlying=extracted.underlying,           # <-- NEW
                    instrument_type=extracted.instrument_type, # <-- NEW
                    strike=extracted.strike,                   # <-- NEW
                    direction=extracted.direction, 
                    entry_price=extracted.entry_price,
                    stop_loss=extracted.stop_loss, 
                    targets=extracted.targets, 
                    is_intraday=True, 
                    issued_at=original_msg['time']   # Or message_time for the single parse method
                )
                results.append({"signal": signal, "instrument_data": extracted})
                
            return results
        except Exception as e:
            raise ValueError(f"Batch LLM Parsing failed: {e}")