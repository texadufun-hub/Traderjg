"""
TradingAgents integration layer.

Wraps TradingAgentsGraph in a thread-pool worker so the async FastAPI
event loop is never blocked. SSE events are pushed into per-run asyncio
queues via run_coroutine_threadsafe.
"""

import asyncio
import json
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

try:
    from langchain_core.callbacks import BaseCallbackHandler as _BaseCallback
except ImportError:
    _BaseCallback = object  # type: ignore[assignment,misc]

# Ordered pipeline — matches LangGraph node execution order
NODE_TO_AGENT: dict[str, str] = {
    "market_analyst": "Technical Analyst",
    "social_analyst": "Sentiment Analyst",
    "news_analyst": "News Analyst",
    "fundamentals_analyst": "Fundamentals Analyst",
    "bull_researcher": "Bull Researcher",
    "bear_researcher": "Bear Researcher",
    "research_manager": "Research Manager",
    "trader": "Trader",
    "aggressive_debater": "Aggressive Risk Analyst",
    "neutral_debater": "Neutral Risk Analyst",
    "conservative_debater": "Conservative Risk Analyst",
    "portfolio_manager": "Portfolio Manager",
}

AGENT_ORDER: list[str] = list(dict.fromkeys(NODE_TO_AGENT.values()))

executor = ThreadPoolExecutor(max_workers=4)


# ── SSE callback ───────────────────────────────────────────────────────────

class SSECallbackHandler(_BaseCallback):  # type: ignore[misc]
    """Converts LangChain/LangGraph callbacks → SSE events in an asyncio queue."""

    def __init__(self, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
        super().__init__()
        self._q = queue
        self._loop = loop

    def _emit(self, event: dict) -> None:
        event.setdefault("ts", datetime.utcnow().isoformat())
        asyncio.run_coroutine_threadsafe(self._q.put(event), self._loop)

    def _node(self, serialized: dict, kwargs: dict) -> str:
        meta = kwargs.get("metadata") or {}
        return meta.get("langgraph_node") or serialized.get("name", "")

    def on_chain_start(self, serialized: dict, inputs: dict, **kwargs: Any) -> None:
        node = self._node(serialized, kwargs)
        agent = NODE_TO_AGENT.get(node)
        if agent and "_tools" not in node and "_clear" not in node:
            self._emit({"type": "agent_start", "agent": agent})

    def on_chain_end(self, outputs: dict, **kwargs: Any) -> None:
        node = self._node({}, kwargs)
        agent = NODE_TO_AGENT.get(node)
        if agent and "_tools" not in node and "_clear" not in node:
            self._emit({"type": "agent_end", "agent": agent})

    def on_tool_start(self, serialized: dict, input_str: str, **kwargs: Any) -> None:
        self._emit({
            "type": "tool_call",
            "tool": serialized.get("name", "tool"),
            "input": str(input_str)[:500],
        })

    def on_tool_end(self, output: Any, **kwargs: Any) -> None:
        self._emit({"type": "tool_result", "preview": str(output)[:400]})

    def on_llm_start(self, serialized: dict, prompts: list, **kwargs: Any) -> None:
        self._emit({"type": "llm_start", "model": serialized.get("name", "LLM")})

    def on_llm_error(self, error: Exception, **kwargs: Any) -> None:
        self._emit({"type": "llm_error", "error": str(error)})

    def on_tool_error(self, error: Exception, **kwargs: Any) -> None:
        self._emit({"type": "tool_error", "error": str(error)})


# ── Run manager ────────────────────────────────────────────────────────────

class RunManager:
    def __init__(self) -> None:
        self._runs: dict[str, dict] = {}

    def create(self, run_id: str, loop: asyncio.AbstractEventLoop) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._runs[run_id] = {
            "status": "running",
            "queue": q,
            "result": None,
            "error": None,
            "loop": loop,
        }
        return q

    def _put(self, run_id: str, event: dict) -> None:
        r = self._runs.get(run_id)
        if r:
            asyncio.run_coroutine_threadsafe(r["queue"].put(event), r["loop"])

    def complete(self, run_id: str, result: dict) -> None:
        r = self._runs.get(run_id)
        if r:
            r["status"] = "complete"
            r["result"] = result
        self._put(run_id, {
            "type": "complete",
            "result": result,
            "ts": datetime.utcnow().isoformat(),
        })

    def fail(self, run_id: str, error: str) -> None:
        r = self._runs.get(run_id)
        if r:
            r["status"] = "error"
            r["error"] = error
        self._put(run_id, {
            "type": "error",
            "message": error,
            "ts": datetime.utcnow().isoformat(),
        })

    def get(self, run_id: str) -> dict | None:
        return self._runs.get(run_id)

    async def stream(self, run_id: str):
        r = self._runs.get(run_id)
        if not r:
            yield f"data: {json.dumps({'type': 'error', 'message': 'run not found'})}\n\n"
            return
        q = r["queue"]
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=300)
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                continue
            yield f"data: {json.dumps(event, default=str)}\n\n"
            if event.get("type") in ("complete", "error"):
                break


run_manager = RunManager()


# ── Result extraction ──────────────────────────────────────────────────────

def extract_result(final_state: dict, signal: Any) -> dict:
    def to_json(v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, str):
            return v
        if hasattr(v, "model_dump"):
            return v.model_dump()
        if isinstance(v, dict):
            return v
        return str(v)

    def debate_to_text(debate_state: Any) -> str | None:
        if not debate_state:
            return None
        if isinstance(debate_state, dict):
            msgs = debate_state.get("messages", [])
            if msgs:
                lines = []
                for m in msgs:
                    role = getattr(m, "name", None) or getattr(m, "role", None) or type(m).__name__
                    content = getattr(m, "content", str(m))
                    if content:
                        lines.append(f"**{role}**: {content}")
                return "\n\n---\n\n".join(lines)
        return str(debate_state)

    return {
        "signal": str(signal) if signal else None,
        "market_report": to_json(final_state.get("market_report")),
        "fundamentals_report": to_json(final_state.get("fundamentals_report")),
        "sentiment_report": to_json(final_state.get("sentiment_report")),
        "news_report": to_json(final_state.get("news_report")),
        "trader_investment_plan": to_json(final_state.get("trader_investment_plan")),
        "final_trade_decision": to_json(final_state.get("final_trade_decision")),
        "investment_debate": debate_to_text(final_state.get("investment_debate_state")),
        "risk_debate": debate_to_text(final_state.get("risk_debate_state")),
    }


# ── Thread worker ──────────────────────────────────────────────────────────

def run_analysis_worker(
    run_id: str,
    ticker: str,
    trade_date: str,
    analysts: list[str],
    ta_config: dict,
    loop: asyncio.AbstractEventLoop,
    session_factory,
) -> None:
    """Runs TradingAgents synchronously in a thread-pool worker."""
    try:
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        q = run_manager.get(run_id)["queue"]
        callback = SSECallbackHandler(q, loop)

        ta = TradingAgentsGraph(
            selected_analysts=tuple(analysts),
            debug=False,
            config=ta_config,
            callbacks=[callback],
        )

        # Emit a start event so the frontend knows analysis is underway
        asyncio.run_coroutine_threadsafe(
            q.put({"type": "analysis_started", "ticker": ticker, "date": trade_date,
                   "ts": datetime.utcnow().isoformat()}),
            loop,
        )

        final_state, signal = ta.propagate(ticker, trade_date)
        result = extract_result(final_state, signal)

        # Persist to DB
        db = session_factory()
        try:
            from models import Analysis
            row = db.query(Analysis).filter(Analysis.run_id == run_id).first()
            if row:
                row.status = "complete"
                row.signal = result["signal"]
                row.result_json = json.dumps(result, default=str)
                db.commit()
        finally:
            db.close()

        run_manager.complete(run_id, result)

    except Exception as exc:
        error_msg = str(exc)
        detail = traceback.format_exc()

        db = session_factory()
        try:
            from models import Analysis
            row = db.query(Analysis).filter(Analysis.run_id == run_id).first()
            if row:
                row.status = "error"
                row.error = f"{error_msg}\n\n{detail}"
                db.commit()
        finally:
            db.close()

        run_manager.fail(run_id, error_msg)
