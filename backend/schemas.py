import json
from datetime import date, datetime
from typing import Any, Optional
from pydantic import BaseModel, field_validator
from models import TradeSide, TradeStatus


# ── Trade schemas ──────────────────────────────────────────────

class TradeBase(BaseModel):
    symbol: str
    side: TradeSide
    quantity: float
    entry_price: float
    entry_date: date
    exit_price: Optional[float] = None
    exit_date: Optional[date] = None
    notes: Optional[str] = None
    analysis_run_id: Optional[str] = None

    @field_validator("symbol")
    @classmethod
    def upper(cls, v: str) -> str:
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
    analysis_run_id: Optional[str] = None


class TradeOut(TradeBase):
    id: int
    status: TradeStatus
    pnl: Optional[float] = None
    model_config = {"from_attributes": True}


class PortfolioStats(BaseModel):
    total_trades: int
    open_trades: int
    closed_trades: int
    total_pnl: float
    win_rate: float
    avg_pnl: float
    best_trade: float
    worst_trade: float


# ── Analysis / Run schemas ─────────────────────────────────────

LLM_PROVIDERS = [
    "openai", "anthropic", "google_genai", "google",  # google=alias for google_genai
    "xai", "openrouter", "ollama", "huggingface", "litellm",
]

ANALYST_KEYS = ["market", "social", "news", "fundamentals"]


class RunCreate(BaseModel):
    ticker: str
    trade_date: str
    analysts: list[str] = ANALYST_KEYS
    llm_provider: str = "google_genai"
    deep_think_llm: str = "gemini-2.5-pro"
    quick_think_llm: str = "gemini-2.5-pro"
    max_debate_rounds: int = 1
    max_risk_discuss_rounds: int = 1
    analyst_concurrency: int = 1
    output_language: str = "English"
    temperature: Optional[float] = None
    backend_url: Optional[str] = None
    benchmark_ticker: Optional[str] = None
    checkpoint_enabled: bool = False

    @field_validator("ticker")
    @classmethod
    def upper_ticker(cls, v: str) -> str:
        return v.upper().strip()

    @field_validator("analysts")
    @classmethod
    def validate_analysts(cls, v: list[str]) -> list[str]:
        valid = set(ANALYST_KEYS)
        bad = [a for a in v if a not in valid]
        if bad:
            raise ValueError(f"Unknown analysts: {bad}. Valid: {ANALYST_KEYS}")
        if not v:
            raise ValueError("At least one analyst required")
        return v


class RunOut(BaseModel):
    run_id: str
    ticker: str
    trade_date: str
    status: str
    signal: Optional[str] = None
    created_at: datetime
    llm_provider: Optional[str] = None
    deep_think_llm: Optional[str] = None
    model_config = {"from_attributes": True}


class RunDetailOut(RunOut):
    analysts: str
    config_snapshot: Optional[str] = None
    result_json: Optional[str] = None
    error: Optional[str] = None

    def parsed_result(self) -> Optional[dict]:
        if self.result_json:
            return json.loads(self.result_json)
        return None


# ── Config schemas ─────────────────────────────────────────────

class ConfigOut(BaseModel):
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    xai_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    dashscope_api_key: Optional[str] = None
    fred_api_key: Optional[str] = None
    default_llm_provider: str = "openai"
    default_deep_think_llm: str = "gpt-4o"
    default_quick_think_llm: str = "gpt-4o-mini"


class ConfigUpdate(BaseModel):
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    xai_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    dashscope_api_key: Optional[str] = None
    fred_api_key: Optional[str] = None
    default_llm_provider: Optional[str] = None
    default_deep_think_llm: Optional[str] = None
    default_quick_think_llm: Optional[str] = None
