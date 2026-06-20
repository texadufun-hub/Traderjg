import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Date, Text, Enum, DateTime
from database import Base


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
    analysis_run_id = Column(String(36), nullable=True)


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(36), unique=True, nullable=False, index=True)
    ticker = Column(String(20), nullable=False, index=True)
    trade_date = Column(String(20), nullable=False)
    analysts = Column(Text, nullable=False)
    config_snapshot = Column(Text, nullable=True)
    status = Column(String(20), default="running", nullable=False)
    signal = Column(String(20), nullable=True)
    result_json = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
