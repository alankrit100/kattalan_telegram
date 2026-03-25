from pydantic import BaseModel
from typing import List, Optional, Literal
from datetime import datetime

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Literal
from datetime import datetime

class Signal(BaseModel):
    signal_id: str
    channel_id: str  
    message_id: str  
    raw_text: str
    
    # --- NEW MANDATORY FIELDS ---
    underlying: str
    instrument_type: str = Field(..., description="Must be EQ, CE, or PE")
    strike: Optional[float] = None
    # ----------------------------
    
    direction: Literal["BUY", "SELL"]
    entry_price: float
    targets: List[float] 
    stop_loss: float
    is_intraday: bool = True
    issued_at: datetime

    # The Fail-Fast Bouncer
    @field_validator('instrument_type')
    def validate_instrument(cls, v):
        v = v.upper()
        if v not in ['EQ', 'CE', 'PE']:
            raise ValueError(f"CRITICAL: Invalid instrument_type '{v}'. Must be EQ, CE, or PE.")
        return v

class OHLC(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float

class EvaluationResult(BaseModel):
    signal_id: str
    status: Literal["PENDING", "WIN", "LOSS", "SQUARED_OFF", "EXPIRED"]
    entry_time: Optional[datetime] = None
    exit_time: Optional[datetime] = None
    entry_executed_price: Optional[float] = None
    exit_executed_price: Optional[float] = None
    max_favorable_excursion: float = 0.0
    max_adverse_excursion: float = 0.0
    reason: str
    trace_log: List[str]
    
    # NEW: Auditability fields
    engine_version: str = "1.0.0"
    parser_version: str = "1.0.0"