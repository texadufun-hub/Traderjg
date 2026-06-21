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

# ── Secret Manager bootstrap ───────────────────────────────────────────────
# Fetch API keys from GCP Secret Manager if not already in the environment.
# Works locally via ADC (gcloud auth application-default login) and on
# Cloud Run via the service account. load_dotenv() below can still override.
_GCP_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "733349864865")
_SECRET_MAP = {
    "GOOGLE_API_KEY": f"projects/{_GCP_PROJECT}/secrets/GEMINI_API_KEY/versions/latest",
    "FRED_API_KEY":   f"projects/{_GCP_PROJECT}/secrets/FRED_API_KEY/versions/latest",
}

def _load_gcp_secrets() -> None:
    try:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        for env_var, secret_path in _SECRET_MAP.items():
            if not os.environ.get(env_var):
                try:
                    resp = client.access_secret_version(name=secret_path)
                    os.environ[env_var] = resp.payload.data.decode("utf-8").strip()
                except Exception as e:
                    print(f"[secrets] Could not load {env_var}: {e}")
    except ImportError:
        pass  # google-cloud-secret-manager not installed

_load_gcp_secrets()
load_dotenv()

# Gemini 2.5 models reject an explicit thinking_level parameter — they manage
# thinking internally. Patch _apply_reasoning to skip google_genai so the
# model call goes through without the unsupported parameter.
try:
    import tradingagents.llm as _ta_llm
    _orig_apply_reasoning = _ta_llm._apply_reasoning
    def _patched_apply_reasoning(provider, effort, kwargs):
        if provider == "google_genai":
            return
        _orig_apply_reasoning(provider, effort, kwargs)
    _ta_llm._apply_reasoning = _patched_apply_reasoning
except Exception:
    pass

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

# Clear corrupt cache CSVs on startup — TradingAgents writes partial files on
# failed runs; pandas then chokes on them next time.
_data_cache = RESULTS_DIR / "data_cache"
if _data_cache.exists():
    for _f in _data_cache.glob("*.csv"):
        try:
            import csv
            with open(_f, newline="") as _fh:
                rows = list(csv.reader(_fh))
            if rows:
                expected = len(rows[0])
                if any(len(r) != expected for r in rows[1:] if r):
                    _f.unlink()
                    print(f"[startup] Removed corrupt cache: {_f.name}")
        except Exception:
            _f.unlink()
            print(f"[startup] Removed unreadable cache: {_f.name}")


# ── helpers ───────────────────────────────────────────────────────────────

_LANG_MAP = {
    "English": "en-US",
    "Chinese": "zh-CN",
    "TraditionalChinese": "zh-TW",
    "Japanese": "ja-JP",
    "Korean": "ko-KR",
    "German": "de-DE",
    # pass-through for already-BCP47 values
    "en-US": "en-US", "zh-CN": "zh-CN", "zh-TW": "zh-TW",
    "ja-JP": "ja-JP", "ko-KR": "ko-KR", "de-DE": "de-DE",
}

_PROVIDER_MAP = {
    "google": "google_genai",  # old alias
}


def _build_ta_config(req: schemas.RunCreate):
    from tradingagents.config import TradingAgentsConfig
    provider = _PROVIDER_MAP.get(req.llm_provider, req.llm_provider)
    language = _LANG_MAP.get(req.output_language, "en-US")
    if req.backend_url:
        # ollama client reads OLLAMA_HOST (no /v1 path)
        os.environ["OLLAMA_HOST"] = req.backend_url.rstrip("/").removesuffix("/v1")
    return TradingAgentsConfig(
        results_dir=RESULTS_DIR,
        llm_provider=provider,
        deep_think_llm=req.deep_think_llm,
        quick_think_llm=req.quick_think_llm,
        max_debate_rounds=req.max_debate_rounds,
        max_risk_discuss_rounds=req.max_risk_discuss_rounds,
        max_recur_limit=300,
        response_language=language,
    )


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

    return _enrich_run(schemas.RunOut.model_validate(row), row)


def _enrich_run(out: schemas.RunOut, row: models.Analysis) -> schemas.RunOut:
    """Populate llm_provider / deep_think_llm from config_snapshot."""
    if row.config_snapshot:
        try:
            cfg = json.loads(row.config_snapshot)
            out.llm_provider = cfg.get("llm_provider")
            out.deep_think_llm = cfg.get("deep_think_llm")
        except Exception:
            pass
    return out


@app.get("/runs", response_model=list[schemas.RunOut])
def list_runs(db: Session = Depends(database.get_db)):
    rows = db.query(models.Analysis).order_by(models.Analysis.created_at.desc()).all()
    return [_enrich_run(schemas.RunOut.model_validate(r), r) for r in rows]


@app.get("/runs/{run_id}", response_model=schemas.RunDetailOut)
def get_run(run_id: str, db: Session = Depends(database.get_db)):
    row = db.query(models.Analysis).filter(models.Analysis.run_id == run_id).first()
    if not row:
        raise HTTPException(404, "Run not found")
    return schemas.RunDetailOut.model_validate(row)


@app.get("/runs/{run_id}/log")
def get_run_log(run_id: str):
    from agent_runner import LOG_DIR
    log_path = LOG_DIR / f"{run_id}.jsonl"
    if not log_path.exists():
        raise HTTPException(404, "Log not found")
    entries = []
    with log_path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except Exception:
                    pass
    return {"run_id": run_id, "entries": entries}


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
