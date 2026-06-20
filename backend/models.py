from datetime import date
from sqlalchemy import Column, Integer, String, Float, Date, Text, Enum
from database import Base
import enum


class TradeSide(str, enum.Enum):
    LONG = "long"
    SHORT = "short"


class TradeStatus(str, enum.Enum):
    OPEN = "open"
    CLOSED = "closed"


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(Enum(TradeSide), nullable=False)
    status = Column(Enum(TradeStatus), default=TradeStatus.OPEN, nullable=False)
    quantity = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    entry_date = Column(Date, nullable=False)
    exit_date = Column(Date, nullable=True)
    pnl = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
