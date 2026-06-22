"""
TradingAgents integration layer.

Wraps TradingAgentsGraph in a thread-pool worker so the async FastAPI
event loop is never blocked. SSE events are pushed into per-run asyncio
queues via run_coroutine_threadsafe.
"""

import asyncio
import json
import os
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

LOG_DIR = Path("/app/data/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── Tool dedup patch ───────────────────────────────────────────────────────
# Replaces every tool in ANALYST_TOOL_REGISTRY with a wrapper that returns a
# stop signal after 3 identical calls. Prevents small models from looping.
# _DEDUP_SEEN is cleared at the start of each run.

_DEDUP_SEEN: dict[str, int] = {}   # keyed by tool+args (exact duplicate detection)
_NAME_SEEN: dict[str, int] = {}    # keyed by tool name only (total call cap)

# Max identical (tool+args) calls per key
_EXACT_LIMITS: dict[str, int] = {
    "get_stock_data": 2,
    "get_indicators": 2,
}
_DEFAULT_EXACT_LIMIT = 1

# Max TOTAL calls per tool name, regardless of args — stops indicator-set cycling
_NAME_LIMITS: dict[str, int] = {
    "get_stock_data": 2,
    "get_indicators": 4,   # enough for 2 real calls, blocks cycling after that
}
_DEFAULT_NAME_LIMIT = 2

def _apply_dedup_patch() -> None:
    try:
        from langchain_core.tools import StructuredTool
        from tradingagents.agents.utils.tool_registry import ANALYST_TOOL_REGISTRY

        def _wrap(tool):  # type: ignore[return]
            exact_limit = _EXACT_LIMITS.get(tool.name, _DEFAULT_EXACT_LIMIT)
            name_limit = _NAME_LIMITS.get(tool.name, _DEFAULT_NAME_LIMIT)

            def _guarded(**kwargs: Any) -> str:
                # Level 1: total calls by name
                _NAME_SEEN[tool.name] = _NAME_SEEN.get(tool.name, 0) + 1
                if _NAME_SEEN[tool.name] > name_limit:
                    return (
                        "[STOP] You have already retrieved sufficient data from this tool. "
                        "Your earlier tool responses contained real data — use those values now. "
                        "Write your final report using the data already returned to you."
                    )
                # Level 2: exact duplicate check
                key = f"{tool.name}:{json.dumps(kwargs, sort_keys=True, default=str)}"
                _DEDUP_SEEN[key] = _DEDUP_SEEN.get(key, 0) + 1
                if _DEDUP_SEEN[key] > exact_limit:
                    return (
                        "[STOP] You already have this exact data from an earlier call. "
                        "Use the values from your previous successful tool response to write your report."
                    )
                result = tool.invoke(kwargs)
                # Post-process fundamentals output: format decimals as % so the
                # model doesn't misinterpret raw ratios (e.g. 1.14 → 114.29%)
                if tool.name == "get_fundamentals" and isinstance(result, str):
                    import re
                    def _pct(m: "re.Match[str]") -> str:
                        return f"{m.group(1)}: {float(m.group(2)) * 100:.2f}%"
                    for field in ("Return on Equity", "Return on Assets",
                                  "Profit Margins", "Operating Margins",
                                  "Gross Margins", "Ebitda Margins"):
                        result = re.sub(
                            rf"({re.escape(field)}): (-?\d+\.\d+(?:[eE][+-]?\d+)?)",
                            _pct, result,
                        )
                return result

            return StructuredTool.from_function(
                func=_guarded,
                name=tool.name,
                description=tool.description,
                args_schema=getattr(tool, "args_schema", None),
            )

        for analyst_type, tools in list(ANALYST_TOOL_REGISTRY.items()):
            ANALYST_TOOL_REGISTRY[analyst_type] = tuple(_wrap(t) for t in tools)  # type: ignore[assignment]

    except Exception:
        pass  # best-effort

_apply_dedup_patch()

# ── Context window patch ───────────────────────────────────────────────────
# Ollama defaults to num_ctx=2048 — too small for debate context.
# Force 8192 so Conservative/Neutral agents don't get truncated mid-sentence.

def _apply_num_ctx_patch() -> None:
    try:
        from langchain_ollama import ChatOllama
        _orig_post_init = ChatOllama.model_post_init

        def _patched_post_init(self, context: Any) -> None:
            _orig_post_init(self, context)
            if self.num_ctx is None:
                object.__setattr__(self, "num_ctx", 8192)

        ChatOllama.model_post_init = _patched_post_init  # type: ignore[method-assign]
    except Exception:
        pass

_apply_num_ctx_patch()

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

    def _node(self, serialized: dict | None, kwargs: dict) -> str:
        meta = kwargs.get("metadata") or {}
        return meta.get("langgraph_node") or (serialized or {}).get("name", "")

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


# ── Logging callback ───────────────────────────────────────────────────────

class LoggingCallbackHandler(_BaseCallback):  # type: ignore[misc]
    """Writes every agent turn, prompt, response, and token count to a per-run JSONL file."""

    def __init__(self, run_id: str):
        super().__init__()
        self._path = LOG_DIR / f"{run_id}.jsonl"
        self._tokens = {"prompt": 0, "completion": 0, "total": 0}
        self._current_agent: str = ""

    def _log(self, entry: dict) -> None:
        entry.setdefault("ts", datetime.utcnow().isoformat())
        entry["agent"] = self._current_agent
        with self._path.open("a") as f:
            f.write(json.dumps(entry, default=str) + "\n")

    def _node(self, serialized: dict | None, kwargs: dict) -> str:
        meta = kwargs.get("metadata") or {}
        return meta.get("langgraph_node") or (serialized or {}).get("name", "")

    def on_chain_start(self, serialized: dict, inputs: dict, **kwargs: Any) -> None:
        node = self._node(serialized, kwargs)
        agent = NODE_TO_AGENT.get(node)
        if agent:
            self._current_agent = agent
            self._log({"type": "agent_start", "node": node})

    def on_chain_end(self, outputs: dict, **kwargs: Any) -> None:
        node = self._node({}, kwargs)
        from agent_runner import NODE_TO_AGENT
        agent = NODE_TO_AGENT.get(node)
        if agent:
            self._log({"type": "agent_end", "node": node})

    def on_chat_model_start(self, serialized: dict, messages: list, **kwargs: Any) -> None:
        # Capture full prompt sent to the model
        prompt_text = ""
        if messages:
            for msg_list in messages:
                for msg in (msg_list if isinstance(msg_list, list) else [msg_list]):
                    role = getattr(msg, "type", getattr(msg, "role", "unknown"))
                    content = getattr(msg, "content", str(msg))
                    if isinstance(content, list):
                        content = " ".join(c.get("text", "") if isinstance(c, dict) else str(c) for c in content)
                    prompt_text += f"[{role}]: {content}\n\n"
        self._log({
            "type": "llm_prompt",
            "model": serialized.get("name", ""),
            "prompt": prompt_text[:8000],  # cap at 8k chars
        })

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        # Extract response text and token usage
        text = ""
        usage: dict = {}
        try:
            gen = response.generations[0][0] if response.generations else None
            if gen:
                text = getattr(gen, "text", "") or str(getattr(gen, "message", ""))
            raw = response.llm_output or {}
            usage = raw.get("token_usage") or raw.get("usage") or {}
            # Ollama puts usage at top level sometimes
            if not usage and hasattr(response, "generations"):
                for g_list in response.generations:
                    for g in g_list:
                        msg = getattr(g, "message", None)
                        if msg:
                            resp_meta = getattr(msg, "response_metadata", {})
                            if resp_meta:
                                usage = {
                                    "prompt": resp_meta.get("prompt_eval_count", 0),
                                    "completion": resp_meta.get("eval_count", 0),
                                    "total": resp_meta.get("prompt_eval_count", 0) + resp_meta.get("eval_count", 0),
                                }
        except Exception:
            pass

        prompt_t = int(usage.get("prompt_tokens") or usage.get("prompt") or 0)
        completion_t = int(usage.get("completion_tokens") or usage.get("completion") or 0)
        total_t = int(usage.get("total_tokens") or usage.get("total") or prompt_t + completion_t)

        self._tokens["prompt"] += prompt_t
        self._tokens["completion"] += completion_t
        self._tokens["total"] += total_t

        self._log({
            "type": "llm_response",
            "response": text[:8000],
            "tokens": {"prompt": prompt_t, "completion": completion_t, "total": total_t},
            "tokens_cumulative": dict(self._tokens),
        })

    def on_tool_start(self, serialized: dict, input_str: str, **kwargs: Any) -> None:
        self._log({"type": "tool_call", "tool": serialized.get("name", ""), "input": str(input_str)[:2000]})

    def on_tool_end(self, output: Any, **kwargs: Any) -> None:
        self._log({"type": "tool_result", "output": str(output)[:4000]})

    def on_llm_error(self, error: Exception, **kwargs: Any) -> None:
        self._log({"type": "llm_error", "error": str(error)})

    def on_tool_error(self, error: Exception, **kwargs: Any) -> None:
        self._log({"type": "tool_error", "error": str(error)})

    def write_summary(self) -> None:
        self._log({"type": "summary", "total_tokens": dict(self._tokens)})

    @property
    def log_path(self) -> Path:
        return self._path


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


# ── Helpers ────────────────────────────────────────────────────────────────

def _get(obj: Any, key: str) -> Any:
    """Attribute access that works on both dicts and Pydantic models (AgentState)."""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


import re as _re
_TEMPLATE_TOKEN_RE = _re.compile(
    r"<\|[^|>]*\|>|<channel\|[^>]*>|\[INST\]|\[/INST\]|<<SYS>>|<</SYS>>|<\|im_start\|>|<\|im_end\|>"
)

def _clean_llm_output(text: str) -> str:
    """Strip stray chat-template tokens that small models leak into output."""
    return _TEMPLATE_TOKEN_RE.sub("", text).strip()


# ── Result extraction ──────────────────────────────────────────────────────

def extract_result(final_state: Any, signal: Any) -> dict:

    def to_json(v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, str):
            return _clean_llm_output(v)
        if hasattr(v, "model_dump"):
            d = v.model_dump()
            # Sanity-check stop_loss / target_price — small models often swap them
            entry = d.get("entry_reference_price")
            stop = d.get("stop_loss")
            target = d.get("target_price")
            signal = d.get("signal", "")
            if entry and stop:
                buy = signal == "BUY"
                sell = signal == "SELL"
                # BUY: stop should be BELOW entry; SELL: stop should be ABOVE entry
                stop_on_wrong_side = (buy and stop > entry) or (sell and stop < entry)
                if stop_on_wrong_side:
                    # Looks like stop and target were swapped
                    if target is None:
                        d["target_price"] = stop  # move misplaced stop to target
                    d["stop_loss"] = None
                elif stop > entry * 3 or stop < 0:
                    d["stop_loss"] = None
            return d
        if isinstance(v, dict):
            return v
        return str(v)

    def debate_to_text(debate_state: Any) -> str | None:
        if not debate_state:
            return None
        msgs = _get(debate_state, "messages") or []
        if msgs:
            lines = []
            for m in msgs:
                role = getattr(m, "name", None) or getattr(m, "role", None) or type(m).__name__
                content = getattr(m, "content", str(m))
                if content:
                    lines.append(f"**{role}**: {content}")
            return "\n\n---\n\n".join(lines)
        # Fallback: pull readable text from known history fields rather than Python repr
        for field in ("history", "bear_history", "conservative_history", "neutral_history"):
            val = _get(debate_state, field)
            if isinstance(val, str) and len(val.strip()) > 40:
                return val.strip()
        return None

    # Normalize the TradeRecommendation signal object into a clean string + dict
    signal_str: str | None = None
    signal_detail: dict | None = None
    if signal is not None:
        if hasattr(signal, "model_dump"):
            d = signal.model_dump()
            # Apply stop_loss / target_price sanity check on the structured signal
            entry = d.get("entry_reference_price")
            stop = d.get("stop_loss")
            target = d.get("target_price")
            sig_name = d.get("signal", "")
            if entry and stop:
                buy, sell = sig_name == "BUY", sig_name == "SELL"
                wrong_side = (buy and stop > entry) or (sell and stop < entry)
                if wrong_side:
                    d["target_price"] = stop if target is None else target
                    d["stop_loss"] = None
                    d["warning_message"] = (
                        (d.get("warning_message") or "") +
                        f" [AUTO-CORRECTED: stop_loss={stop} was above entry on BUY; moved to target_price.]"
                    ).strip()
                elif stop > entry * 3 or stop < 0:
                    d["stop_loss"] = None
            signal_str = d.get("signal") or str(signal)
            signal_detail = d
        else:
            signal_str = str(signal)

    # Build final_trade_decision: prefer state value, fall back to signal_detail repr
    raw_decision = _get(final_state, "final_trade_decision")
    decision = to_json(raw_decision)
    if not decision and signal_detail:
        decision = signal_detail

    # Fundamentals: if empty string, try to surface a data-unavailable note
    fundamentals = to_json(_get(final_state, "fundamentals_report")) or None

    return {
        "signal": signal_str,
        "signal_detail": signal_detail,
        "market_report": to_json(_get(final_state, "market_report")),
        "fundamentals_report": fundamentals,
        "sentiment_report": to_json(_get(final_state, "sentiment_report")),
        "news_report": to_json(_get(final_state, "news_report")),
        "trader_investment_plan": to_json(_get(final_state, "trader_investment_plan")),
        "final_trade_decision": decision,
        "investment_debate": debate_to_text(_get(final_state, "investment_debate_state")),
        "risk_debate": debate_to_text(_get(final_state, "risk_debate_state")),
    }


# ── Price sanity check ────────────────────────────────────────────────────

_PRICE_DEVIATION_THRESHOLD = 0.50  # flag / auto-correct if >50% off real price

def _fetch_real_price(ticker: str, trade_date: str) -> float | None:
    """Return the actual closing price for ticker on or just before trade_date."""
    try:
        import yfinance as yf
        import pandas as pd
        end = (pd.Timestamp(trade_date) + pd.Timedelta(days=4)).strftime("%Y-%m-%d")
        hist = yf.Ticker(ticker).history(start=trade_date, end=end)
        if not hist.empty:
            return float(hist["Close"].iloc[0])
    except Exception:
        pass
    return None


def _sanity_check_price(result: dict, ticker: str, trade_date: str) -> dict:
    """Auto-correct entry_reference_price if it deviates >50% from yfinance close."""
    real = _fetch_real_price(ticker, trade_date)
    if real is None:
        return result

    decision = result.get("final_trade_decision")
    if not isinstance(decision, dict):
        return result

    model_price = decision.get("entry_reference_price")
    if not model_price or real <= 0:
        return result

    deviation = abs(model_price - real) / real
    if deviation <= _PRICE_DEVIATION_THRESHOLD:
        return result

    # Auto-correct the structured price field
    decision["entry_reference_price"] = real
    warning = (
        f"[PRICE SANITY] Model stated entry ${model_price:.2f} but yfinance close is "
        f"${real:.2f} ({deviation * 100:.0f}% deviation — likely pre-split or hallucinated price). "
        "entry_reference_price auto-corrected to real close."
    )
    existing = decision.get("warning_message") or ""
    decision["warning_message"] = (warning + " " + existing).strip()

    # Also prepend a visible banner to the market report so it's obvious in the UI
    banner = (
        f"\n\n> ⚠️ **PRICE WARNING**: Technical report may contain hallucinated prices. "
        f"Model stated ~${model_price:.0f}; real yfinance close is ${real:.2f}. "
        f"Treat any price figures in this report with caution.\n\n"
    )
    if result.get("market_report") and isinstance(result["market_report"], str):
        result["market_report"] = banner + result["market_report"]

    return result


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
    _saved_fa: Any = None  # saved for fundamentals-patch restore in finally

    try:
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        q = run_manager.get(run_id)["queue"]
        callback = SSECallbackHandler(q, loop)
        logger = LoggingCallbackHandler(run_id)

        # Reset per-run dedup counters (see module-level patch below)
        _DEDUP_SEEN.clear()
        _NAME_SEEN.clear()

        # ── Fundamentals → Gemini override ────────────────────────────────
        # Route the Fundamentals Analyst to Gemini regardless of the run's
        # llm_provider — local models (7B and below) consistently hallucinate
        # balance-sheet values while fluently ignoring the real tool output.
        # Must be applied before TradingAgentsGraph() calls _build_analyst_nodes().
        # Restored unconditionally in the finally block below.
        if "fundamentals" in analysts:
            try:
                import tradingagents.graph.setup as _gs
                from tradingagents.llm import build_chat_model as _bcm
                _saved_fa = _gs.create_fundamentals_analyst
                _gemini_llm = _bcm(
                    "google_genai", "gemini-2.5-pro",
                    callbacks=[callback, logger],
                )
                _gs.create_fundamentals_analyst = lambda _: _saved_fa(_gemini_llm)
            except Exception:
                _saved_fa = None  # patch failed silently — run without override

        ta = TradingAgentsGraph(
            selected_analysts=tuple(analysts),
            debug=False,
            config=ta_config,
            callbacks=[callback, logger],
        )

        # Emit a start event so the frontend knows analysis is underway
        asyncio.run_coroutine_threadsafe(
            q.put({"type": "analysis_started", "ticker": ticker, "date": trade_date,
                   "ts": datetime.utcnow().isoformat()}),
            loop,
        )

        # Track agent progress via on_state — fires after each node with full state.
        # Maps newly-populated state fields → agent timeline events.
        _STATE_FIELD_TO_AGENT: list[tuple[str, str]] = [
            ("market_report",          "Technical Analyst"),
            ("sentiment_report",       "Sentiment Analyst"),
            ("news_report",            "News Analyst"),
            ("fundamentals_report",    "Fundamentals Analyst"),
            ("investment_plan",        "Research Manager"),
            ("trader_investment_plan", "Trader"),
            ("final_trade_decision",   "Portfolio Manager"),
        ]
        _prev_fields: set[str] = set()
        _prev_invest_msgs = 0
        _prev_risk_msgs = 0

        def _emit(event: dict) -> None:
            event.setdefault("ts", datetime.utcnow().isoformat())
            asyncio.run_coroutine_threadsafe(q.put(event), loop)

        def _msg_count(state: Any, field: str) -> int:
            debate = _get(state, field)
            if not debate:
                return 0
            msgs = _get(debate, "messages") or []
            return len(msgs)

        def _on_state(state: Any) -> None:
            nonlocal _prev_invest_msgs, _prev_risk_msgs

            # Detect analyst/manager/trader completion from newly-set fields
            for field, agent in _STATE_FIELD_TO_AGENT:
                val = _get(state, field)
                if val and field not in _prev_fields:
                    _prev_fields.add(field)
                    _emit({"type": "agent_start", "agent": agent})
                    _emit({"type": "agent_end",   "agent": agent})

            # Detect Bull/Bear debate progress from message count
            inv = _msg_count(state, "investment_debate_state")
            if inv > _prev_invest_msgs:
                debaters = ["Bull Researcher", "Bear Researcher"]
                idx = min(_prev_invest_msgs, len(debaters) - 1)
                agent = debaters[idx % len(debaters)]
                _emit({"type": "agent_start", "agent": agent})
                _emit({"type": "agent_end",   "agent": agent})
                _prev_invest_msgs = inv

            # Detect risk debate progress from message count
            risk = _msg_count(state, "risk_debate_state")
            if risk > _prev_risk_msgs:
                risk_agents = ["Aggressive Risk Analyst", "Neutral Risk Analyst", "Conservative Risk Analyst"]
                idx = min(_prev_risk_msgs, len(risk_agents) - 1)
                agent = risk_agents[idx % len(risk_agents)]
                _emit({"type": "agent_start", "agent": agent})
                _emit({"type": "agent_end",   "agent": agent})
                _prev_risk_msgs = risk

        final_state, signal = ta.propagate(ticker, trade_date, on_state=_on_state)
        result = extract_result(final_state, signal)
        result = _sanity_check_price(result, ticker, trade_date)

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

        logger.write_summary()
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

    finally:
        # Always restore the fundamentals analyst creator regardless of
        # success, failure, or exception anywhere in graph construction or execution.
        if _saved_fa is not None:
            try:
                import tradingagents.graph.setup as _gs
                _gs.create_fundamentals_analyst = _saved_fa
            except Exception:
                pass
