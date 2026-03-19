import os
import uuid
from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from dotenv import load_dotenv
from core.schemas import Signal

# Load API keys
load_dotenv()

# 1. The Strict JSON Schema
# We force the LLM to return data exactly in this format. No exceptions.
class ExtractedSignal(BaseModel):
    underlying: str = Field(description="The base asset, e.g., BANKNIFTY, NIFTY, RELIANCE")
    instrument_type: Literal["CE", "PE", "EQ"] = Field(description="CE for Call, PE for Put, EQ for Equity/Spot")
    strike: Optional[int] = Field(description="Strike price if options, null if equity", default=None)
    direction: Literal["BUY", "SELL"]
    entry_price: float
    stop_loss: float
    targets: List[float]
    mentioned_expiry: Optional[str] = Field(description="Expiry mentioned in the text, e.g., '30th Nov', 'Dec 28', or null if not mentioned",
    default=None)

class SignalParser:
    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("FATAL: Missing GEMINI_API_KEY in .env file.")
        # Initialize the lightning-fast Gemini Flash model
        self.client = genai.Client(api_key=api_key)

    def parse(self, raw_text: str, message_time: datetime, channel_id: str, message_id: str):
        prompt = f"""
        You are a quantitative data extraction engine.
        Analyze this Telegram trading signal posted on {message_time.strftime('%Y-%m-%d %H:%M:%S')}.
        Extract the exact trading parameters. 
        If it is NOT a clear trading signal, you must fail or return empty arrays.
        
        Raw Text: "{raw_text}"
        """
        
        try:
            # 2. Call the LLM with strict Structured Outputs
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ExtractedSignal,
                    temperature=0.0, # Zero creativity, maximum mathematical precision
                ),
            )
            
            # 3. Validate the JSON returned by the AI
            extracted = ExtractedSignal.model_validate_json(response.text)
            
            # 4. Convert it into our standard pipeline Signal object
            signal = Signal(
                signal_id=str(uuid.uuid4()),
                channel_id=channel_id,
                message_id=message_id,
                raw_text=raw_text,
                direction=extracted.direction,
                entry_price=extracted.entry_price,
                stop_loss=extracted.stop_loss,
                targets=extracted.targets,
                is_intraday=True, # Defaulting to intraday for Phase B
                issued_at=message_time
            )
            
            # We return both the standard signal and the extra instrument data (for Fyers)
            return {
                "signal": signal,
                "instrument_data": extracted 
            }
            
        except Exception as e:
            # If the AI fails to extract a valid signal, we crash safely
            raise ValueError(f"LLM Parsing failed or invalid signal text: {e}")