import uuid
from pydantic import BaseModel, Field, field_validator, model_validator, computed_field
from typing import List, Optional, Literal
from datetime import datetime


def make_signal_id(channel_id: str, message_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{channel_id}_{message_id}"))


class Signal(BaseModel):
    signal_id: str = Field(default="")
    channel_id: str
    message_id: str
    raw_text: str
    underlying: str
    instrument_type: str = Field(..., description="Must be EQ, CE, PE, or FUT")
    strike: Optional[int] = None
    direction: Literal["BUY", "SELL"]
    entry_price: float
    targets: List[float]
    stop_loss: float
    is_intraday: bool = True
    issued_at: datetime

    @model_validator(mode="before")
    @classmethod
    def auto_signal_id(cls, values):
        ch = values.get("channel_id", "")
        msg = values.get("message_id", "")
        if ch and msg and not values.get("signal_id"):
            values["signal_id"] = make_signal_id(ch, msg)
        return values

    @field_validator("instrument_type", mode="before")
    @classmethod
    def validate_instrument(cls, v):
        v = v.upper()
        if v not in {"EQ", "CE", "PE", "FUT"}:
            raise ValueError(f"Invalid instrument_type '{v}'. Must be EQ, CE, PE, or FUT.")
        return v

    @field_validator("entry_price", mode="before")
    @classmethod
    def validate_entry_price(cls, v):
        if float(v) <= 0:
            raise ValueError(f"entry_price must be > 0, got {v}")
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
    pnl_percentage: float = 0.0
    reason: str
    trace_log: List[str]
    engine_version: str = "1.0.0"


class ChannelAuditResult(BaseModel):
    channel_name: str
    channel_id: str
    total_messages_scraped: int = 0
    total_trades: int = 0
    total_wins: int = 0
    total_losses: int = 0
    total_squared_off: int = 0
    total_expired: int = 0
    win_rate_pct: float = 0.0
    edge_ratio: float = 0.0
    avg_mfe: float = 0.0
    avg_mae: float = 0.0

    @computed_field
    @property
    def color_grade(self) -> Literal["green", "red"]:
        return "green" if self.win_rate_pct > 55.0 and self.edge_ratio > 1.0 else "red"