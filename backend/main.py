"""
Traderjg FastAPI backend — wraps TradingAgents framework.

Endpoints
─────────
GET  /health
GET  /config
PUT  /config

POST /runs                    start a new analysis run
GET  /runs                    list past runs
GET  /runs/{run_id}           get run detail
DELETE /runs/{run_id}         delete a run
GET  /runs/{run_id}/stream    SSE stream of live agent events

GET  /memory                  read TradingAgents memory log

GET  /trades
POST /trades
GET  /trades/{id}
PUT  /trades/{id}
DELETE /trades/{id}
GET  /stats
"""

import asyncio
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

import database
import models
import schemas
from agent_runner import AGENT_ORDER, run_analysis_worker, run_manager, executor

load_dotenv()

app = FastAPI(title="Traderjg API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

models.Base.metadata.create_all(bind=database.engine)

DATA_DIR = Path("/app/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
MEMORY_LOG = DATA_DIR / "memory.json"
RESULTS_DIR = DATA_DIR / "results"
CACHE_DIR = DATA_DIR / "cache"


# ── helpers ───────────────────────────────────────────────────────────────

def _build_ta_config(req: schemas.RunCreate) -> dict:
    from tradingagents.default_config import DEFAULT_CONFIG
    cfg = DEFAULT_CONFIG.copy()
    cfg["project_dir"] = str(DATA_DIR)
    cfg["results_dir"] = str(RESULTS_DIR)
    cfg["data_cache_dir"] = str(CACHE_DIR)
    cfg["memory_log_path"] = str(MEMORY_LOG)
    cfg["llm_provider"] = req.llm_provider
    cfg["deep_think_llm"] = req.deep_think_llm
    cfg["quick_think_llm"] = req.quick_think_llm
    cfg["max_debate_rounds"] = req.max_debate_rounds
    cfg["max_risk_discuss_rounds"] = req.max_risk_discuss_rounds
    cfg["analyst_concurrency_limit"] = req.analyst_concurrency
    cfg["output_language"] = req.output_language
    cfg["checkpoint_enabled"] = req.checkpoint_enabled
    if req.backend_url:
        cfg["backend_url"] = req.backend_url
    if req.temperature is not None:
        cfg["temperature"] = req.temperature
    if req.benchmark_ticker:
        cfg["benchmark_ticker"] = req.benchmark_ticker
    return cfg


def _calc_pnl(trade: models.Trade) -> float | None:
    if trade.exit_price is None:
        return None
    diff = trade.exit_price - trade.entry_price
    if trade.side == models.TradeSide.SHORT:
        diff = -diff
    return round(diff * trade.quantity, 2)


# ── health ────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}


# ── config ────────────────────────────────────────────────────────────────

@app.get("/config", response_model=schemas.ConfigOut)
def get_config():
    def masked(key: str) -> str | None:
        v = os.getenv(key)
        return "***" if v else None

    return schemas.ConfigOut(
        openai_api_key=masked("OPENAI_API_KEY"),
        anthropic_api_key=masked("ANTHROPIC_API_KEY"),
        google_api_key=masked("GOOGLE_API_KEY"),
        xai_api_key=masked("XAI_API_KEY"),
        deepseek_api_key=masked("DEEPSEEK_API_KEY"),
        dashscope_api_key=masked("DASHSCOPE_API_KEY"),
        fred_api_key=masked("FRED_API_KEY"),
        default_llm_provider=os.getenv("TRADINGAGENTS_LLM_PROVIDER", "openai"),
        default_deep_think_llm=os.getenv("TRADINGAGENTS_DEEP_THINK_LLM", "gpt-4o"),
        default_quick_think_llm=os.getenv("TRADINGAGENTS_QUICK_THINK_LLM", "gpt-4o-mini"),
    )


@app.put("/config")
def update_config(payload: schemas.ConfigUpdate):
    env_map = {
        "openai_api_key": "OPENAI_API_KEY",
        "anthropic_api_key": "ANTHROPIC_API_KEY",
        "google_api_key": "GOOGLE_API_KEY",
        "xai_api_key": "XAI_API_KEY",
        "deepseek_api_key": "DEEPSEEK_API_KEY",
        "dashscope_api_key": "DASHSCOPE_API_KEY",
        "fred_api_key": "FRED_API_KEY",
    }
    updated = []
    for field, env_var in env_map.items():
        v = getattr(payload, field, None)
        if v and v != "***":
            os.environ[env_var] = v
            updated.append(env_var)

    if payload.default_llm_provider:
        os.environ["TRADINGAGENTS_LLM_PROVIDER"] = payload.default_llm_provider
        updated.append("TRADINGAGENTS_LLM_PROVIDER")
    if payload.default_deep_think_llm:
        os.environ["TRADINGAGENTS_DEEP_THINK_LLM"] = payload.default_deep_think_llm
    if payload.default_quick_think_llm:
        os.environ["TRADINGAGENTS_QUICK_THINK_LLM"] = payload.default_quick_think_llm

    return {"status": "updated", "updated_keys": updated}


# ── analysis runs ─────────────────────────────────────────────────────────

@app.get("/agents/order")
def get_agent_order():
    return {"agents": AGENT_ORDER}


@app.post("/runs", response_model=schemas.RunOut, status_code=202)
async def create_run(payload: schemas.RunCreate, db: Session = Depends(database.get_db)):
    run_id = str(uuid.uuid4())

    row = models.Analysis(
        run_id=run_id,
        ticker=payload.ticker,
        trade_date=payload.trade_date,
        analysts=json.dumps(payload.analysts),
        config_snapshot=json.dumps({
            "llm_provider": payload.llm_provider,
            "deep_think_llm": payload.deep_think_llm,
            "quick_think_llm": payload.quick_think_llm,
            "max_debate_rounds": payload.max_debate_rounds,
            "max_risk_discuss_rounds": payload.max_risk_discuss_rounds,
            "analyst_concurrency": payload.analyst_concurrency,
            "output_language": payload.output_language,
            "benchmark_ticker": payload.benchmark_ticker,
        }),
        status="running",
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    loop = asyncio.get_event_loop()
    run_manager.create(run_id, loop)
    ta_config = _build_ta_config(payload)

    executor.submit(
        run_analysis_worker,
        run_id,
        payload.ticker,
        payload.trade_date,
        payload.analysts,
        ta_config,
        loop,
        database.SessionLocal,
    )

    return schemas.RunOut.model_validate(row)


@app.get("/runs", response_model=list[schemas.RunOut])
def list_runs(db: Session = Depends(database.get_db)):
    return db.query(models.Analysis).order_by(models.Analysis.created_at.desc()).all()


@app.get("/runs/{run_id}", response_model=schemas.RunDetailOut)
def get_run(run_id: str, db: Session = Depends(database.get_db)):
    row = db.query(models.Analysis).filter(models.Analysis.run_id == run_id).first()
    if not row:
        raise HTTPException(404, "Run not found")
    return schemas.RunDetailOut.model_validate(row)


@app.delete("/runs/{run_id}", status_code=204)
def delete_run(run_id: str, db: Session = Depends(database.get_db)):
    row = db.query(models.Analysis).filter(models.Analysis.run_id == run_id).first()
    if not row:
        raise HTTPException(404, "Run not found")
    db.delete(row)
    db.commit()


@app.get("/runs/{run_id}/stream")
async def stream_run(run_id: str, request: Request, db: Session = Depends(database.get_db)):
    row = db.query(models.Analysis).filter(models.Analysis.run_id == run_id).first()
    if not row:
        raise HTTPException(404, "Run not found")

    # Already finished — replay the terminal event immediately
    if row.status == "complete" and row.result_json:
        result = json.loads(row.result_json)
        async def done():
            yield f"data: {json.dumps({'type': 'complete', 'result': result})}\n\n"
        return StreamingResponse(done(), media_type="text/event-stream")

    if row.status == "error":
        async def err():
            yield f"data: {json.dumps({'type': 'error', 'message': row.error or 'unknown error'})}\n\n"
        return StreamingResponse(err(), media_type="text/event-stream")

    async def live():
        async for chunk in run_manager.stream(run_id):
            if await request.is_disconnected():
                break
            yield chunk

    return StreamingResponse(live(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


# ── memory log ────────────────────────────────────────────────────────────

@app.get("/memory")
def get_memory():
    if not MEMORY_LOG.exists():
        return []
    try:
        data = json.loads(MEMORY_LOG.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


# ── trades ────────────────────────────────────────────────────────────────

@app.get("/trades", response_model=list[schemas.TradeOut])
def list_trades(db: Session = Depends(database.get_db)):
    return db.query(models.Trade).order_by(models.Trade.entry_date.desc()).all()


@app.get("/trades/{trade_id}", response_model=schemas.TradeOut)
def get_trade(trade_id: int, db: Session = Depends(database.get_db)):
    t = db.query(models.Trade).filter(models.Trade.id == trade_id).first()
    if not t:
        raise HTTPException(404, "Trade not found")
    return t


@app.post("/trades", response_model=schemas.TradeOut, status_code=201)
def create_trade(payload: schemas.TradeCreate, db: Session = Depends(database.get_db)):
    t = models.Trade(**payload.model_dump())
    t.pnl = _calc_pnl(t)
    t.status = models.TradeStatus.CLOSED if t.exit_price is not None else models.TradeStatus.OPEN
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@app.put("/trades/{trade_id}", response_model=schemas.TradeOut)
def update_trade(trade_id: int, payload: schemas.TradeUpdate, db: Session = Depends(database.get_db)):
    t = db.query(models.Trade).filter(models.Trade.id == trade_id).first()
    if not t:
        raise HTTPException(404, "Trade not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(t, field, value)
    t.pnl = _calc_pnl(t)
    t.status = models.TradeStatus.CLOSED if t.exit_price is not None else models.TradeStatus.OPEN
    db.commit()
    db.refresh(t)
    return t


@app.delete("/trades/{trade_id}", status_code=204)
def delete_trade(trade_id: int, db: Session = Depends(database.get_db)):
    t = db.query(models.Trade).filter(models.Trade.id == trade_id).first()
    if not t:
        raise HTTPException(404, "Trade not found")
    db.delete(t)
    db.commit()


@app.get("/stats", response_model=schemas.PortfolioStats)
def get_stats(db: Session = Depends(database.get_db)):
    all_trades = db.query(models.Trade).all()
    closed = [t for t in all_trades if t.status == models.TradeStatus.CLOSED]
    open_ = [t for t in all_trades if t.status == models.TradeStatus.OPEN]
    pnls = [t.pnl for t in closed if t.pnl is not None]
    wins = [p for p in pnls if p > 0]
    return schemas.PortfolioStats(
        total_trades=len(all_trades),
        open_trades=len(open_),
        closed_trades=len(closed),
        total_pnl=round(sum(pnls), 2) if pnls else 0.0,
        win_rate=round(len(wins) / len(pnls) * 100, 1) if pnls else 0.0,
        avg_pnl=round(sum(pnls) / len(pnls), 2) if pnls else 0.0,
        best_trade=max(pnls) if pnls else 0.0,
        worst_trade=min(pnls) if pnls else 0.0,
    )
