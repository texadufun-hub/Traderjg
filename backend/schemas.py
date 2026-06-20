from datetime import date
from typing import Optional
from pydantic import BaseModel, field_validator
from models import TradeSide, TradeStatus


class TradeBase(BaseModel):
    symbol: str
    side: TradeSide
    quantity: float
    entry_price: float
    entry_date: date
    exit_price: Optional[float] = None
    exit_date: Optional[date] = None
    notes: Optional[str] = None

    @field_validator("symbol")
    @classmethod
    def symbol_uppercase(cls, v: str) -> str:
        return v.upper().strip()


class TradeCreate(TradeBase):
    pass


class TradeUpdate(BaseModel):
    symbol: Optional[str] = None
    side: Optional[TradeSide] = None
    quantity: Optional[float] = None
    entry_price: Optional[float] = None
    entry_date: Optional[date] = None
    exit_price: Optional[float] = None
    exit_date: Optional[date] = None
    notes: Optional[str] = None


class TradeOut(TradeBase):
    id: int
    status: TradeStatus
    pnl: Optional[float] = None

    model_config = {"from_attributes": True}


class Stats(BaseModel):
    total_trades: int
    open_trades: int
    closed_trades: int
    total_pnl: float
    win_rate: float
    avg_pnl: float
    best_trade: float
    worst_trade: float
