from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
import database
import models
import schemas

app = FastAPI(title="Traderjg API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

models.Base.metadata.create_all(bind=database.engine)


def _calc_pnl(trade: models.Trade) -> float | None:
    if trade.exit_price is None:
        return None
    diff = trade.exit_price - trade.entry_price
    if trade.side == models.TradeSide.SHORT:
        diff = -diff
    return round(diff * trade.quantity, 2)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/trades", response_model=List[schemas.TradeOut])
def list_trades(db: Session = Depends(database.get_db)):
    return db.query(models.Trade).order_by(models.Trade.entry_date.desc()).all()


@app.get("/trades/{trade_id}", response_model=schemas.TradeOut)
def get_trade(trade_id: int, db: Session = Depends(database.get_db)):
    trade = db.query(models.Trade).filter(models.Trade.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade


@app.post("/trades", response_model=schemas.TradeOut, status_code=201)
def create_trade(payload: schemas.TradeCreate, db: Session = Depends(database.get_db)):
    trade = models.Trade(**payload.model_dump())
    trade.pnl = _calc_pnl(trade)
    trade.status = (
        models.TradeStatus.CLOSED if trade.exit_price is not None
        else models.TradeStatus.OPEN
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade


@app.put("/trades/{trade_id}", response_model=schemas.TradeOut)
def update_trade(
    trade_id: int, payload: schemas.TradeUpdate, db: Session = Depends(database.get_db)
):
    trade = db.query(models.Trade).filter(models.Trade.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(trade, field, value)
    trade.pnl = _calc_pnl(trade)
    trade.status = (
        models.TradeStatus.CLOSED if trade.exit_price is not None
        else models.TradeStatus.OPEN
    )
    db.commit()
    db.refresh(trade)
    return trade


@app.delete("/trades/{trade_id}", status_code=204)
def delete_trade(trade_id: int, db: Session = Depends(database.get_db)):
    trade = db.query(models.Trade).filter(models.Trade.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    db.delete(trade)
    db.commit()


@app.get("/stats", response_model=schemas.Stats)
def get_stats(db: Session = Depends(database.get_db)):
    all_trades = db.query(models.Trade).all()
    closed = [t for t in all_trades if t.status == models.TradeStatus.CLOSED]
    open_ = [t for t in all_trades if t.status == models.TradeStatus.OPEN]
    pnls = [t.pnl for t in closed if t.pnl is not None]
    wins = [p for p in pnls if p > 0]
    return schemas.Stats(
        total_trades=len(all_trades),
        open_trades=len(open_),
        closed_trades=len(closed),
        total_pnl=round(sum(pnls), 2) if pnls else 0.0,
        win_rate=round(len(wins) / len(pnls) * 100, 1) if pnls else 0.0,
        avg_pnl=round(sum(pnls) / len(pnls), 2) if pnls else 0.0,
        best_trade=max(pnls) if pnls else 0.0,
        worst_trade=min(pnls) if pnls else 0.0,
    )
