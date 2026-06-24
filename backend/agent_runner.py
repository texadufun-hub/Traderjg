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

_DEDUP_SEEN: dict[str, int] = {}    # keyed by tool+args (exact duplicate detection)
_NAME_SEEN: dict[str, int] = {}    # keyed by tool name only (total call cap)
_DEDUP_CACHE: dict[str, str] = {}  # tool+args → last successful result text
_TOOL_LAST: dict[str, str] = {}    # tool name → most recent successful result text

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
                    cached = _TOOL_LAST.get(tool.name, "")
                    if cached:
                        return (
                            f"[STOP — call limit reached for {tool.name}. "
                            f"Use the data below from your earlier call — do not call this tool again.]\n\n"
                            f"{cached}"
                        )
                    return (
                        "[STOP] You have called this tool enough times. "
                        "Write your final report using the data from your earlier tool responses."
                    )
                # Level 2: exact duplicate check
                key = f"{tool.name}:{json.dumps(kwargs, sort_keys=True, default=str)}"
                _DEDUP_SEEN[key] = _DEDUP_SEEN.get(key, 0) + 1
                if _DEDUP_SEEN[key] > exact_limit:
                    cached = _DEDUP_CACHE.get(key, _TOOL_LAST.get(tool.name, ""))
                    if cached:
                        return (
                            f"[STOP — duplicate call blocked for {tool.name}. "
                            f"Here is the data you already retrieved — use these values now.]\n\n"
                            f"{cached}"
                        )
                    return (
                        "[STOP] You already retrieved this data. "
                        "Use the values from your earlier successful tool response."
                    )
                result = tool.invoke(kwargs)
                # Cache the successful result for future STOP messages
                result_str = str(result)
                _DEDUP_CACHE[key] = result_str
                _TOOL_LAST[tool.name] = result_str
                # Post-process fundamentals output: format decimals as % so the
                # model doesn't misinterpret raw ratios (e.g. 1.14 → 114.29%)
                # Round raw EPS floats (4+ decimal places) to 2dp in earnings data
                # Use module-level _re throughout — avoid `import re` inside closure
                # (Python hoists the local binding and causes UnboundLocalError before it runs)
                if tool.name in ("get_earnings_calendar", "get_fundamentals") and isinstance(result, str):
                    def _eps_round(m: "Any") -> str:
                        return f"{m.group(1)}{float(m.group(2)):.2f}"
                    result = _re.sub(
                        r"((?:EPS|Earnings)[^:\n]*?:\s*)(-?\d+\.\d{3,})",
                        _eps_round, result, flags=_re.IGNORECASE,
                    )

                # Short interest: yfinance returns shortPercentOfFloat as a decimal (0.0119 = 1.19%)
                if tool.name == "get_short_interest" and isinstance(result, str):
                    def _short_pct(m: "Any") -> str:
                        return f"{m.group(1)}: {float(m.group(2)) * 100:.2f}%"
                    result = _re.sub(
                        r"(Short Percent of Float): ([\d.]+)",
                        _short_pct, result,
                    )

                if tool.name == "get_fundamentals" and isinstance(result, str):
                    def _pct(m: "Any") -> str:
                        return f"{m.group(1)}: {float(m.group(2)) * 100:.2f}%"
                    for field in ("Return on Equity", "Return on Assets",
                                  "Profit Margins", "Operating Margins",
                                  "Gross Margins", "Ebitda Margins"):
                        result = _re.sub(
                            rf"({_re.escape(field)}): (-?\d+\.\d+(?:[eE][+-]?\d+)?)",
                            _pct, result,
                        )
                    def _de_label(m: "Any") -> str:
                        v = float(m.group(2))
                        ratio = v / 100
                        return (
                            f"{m.group(1)}: {v:.3f}% yfinance snapshot "
                            f"(≈ {ratio:.4f} as a ratio; may differ from balance-sheet-derived "
                            f"Total Debt ÷ Common Equity due to timing/definition differences)"
                        )
                    result = _re.sub(
                        r"(Debt to Equity): (-?\d+\.\d+(?:[eE][+-]?\d+)?)",
                        _de_label, result,
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
        self._current_model: str = ""
        # per-agent: {agent_name: {prompt, completion, total, model}}
        self._agent_tokens: dict[str, dict] = {}

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
        # Extract model name — Gemini stores it nested under kwargs["invocation_params"]
        model_name = (
            serialized.get("name")
            or (serialized.get("kwargs") or {}).get("model")
            or (kwargs.get("invocation_params") or {}).get("model")
            or (kwargs.get("invocation_params") or {}).get("model_name")
            or ""
        )
        self._current_model = model_name
        self._log({
            "type": "llm_prompt",
            "model": model_name,
            "prompt": prompt_text[:8000],
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
            # Try per-generation response_metadata (Ollama and Gemini both use it)
            if not usage and hasattr(response, "generations"):
                for g_list in response.generations:
                    for g in g_list:
                        msg = getattr(g, "message", None)
                        if msg:
                            resp_meta = getattr(msg, "response_metadata", {}) or {}
                            # Ollama format
                            if resp_meta.get("prompt_eval_count"):
                                usage = {
                                    "prompt": resp_meta.get("prompt_eval_count", 0),
                                    "completion": resp_meta.get("eval_count", 0),
                                    "total": resp_meta.get("prompt_eval_count", 0) + resp_meta.get("eval_count", 0),
                                }
                            # Gemini format: usage_metadata nested dict
                            um = resp_meta.get("usage_metadata") or {}
                            if um:
                                usage = {
                                    "prompt": um.get("prompt_token_count", 0),
                                    "completion": um.get("candidates_token_count", 0),
                                    "total": um.get("total_token_count", 0),
                                }
                            # Also capture model name from Gemini metadata
                            if not self._log.__self__._current_agent:
                                pass  # model name captured below via serialized
        except Exception:
            pass

        prompt_t = int(usage.get("prompt_tokens") or usage.get("prompt") or 0)
        completion_t = int(usage.get("completion_tokens") or usage.get("completion") or 0)
        total_t = int(usage.get("total_tokens") or usage.get("total") or prompt_t + completion_t)

        self._tokens["prompt"] += prompt_t
        self._tokens["completion"] += completion_t
        self._tokens["total"] += total_t

        # Per-agent token accumulation
        agent_key = self._current_agent or "pipeline"
        if agent_key not in self._agent_tokens:
            self._agent_tokens[agent_key] = {
                "prompt": 0, "completion": 0, "total": 0,
                "model": self._current_model, "calls": 0,
            }
        self._agent_tokens[agent_key]["prompt"] += prompt_t
        self._agent_tokens[agent_key]["completion"] += completion_t
        self._agent_tokens[agent_key]["total"] += total_t
        self._agent_tokens[agent_key]["calls"] += 1
        if self._current_model:
            self._agent_tokens[agent_key]["model"] = self._current_model

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
        self._log({
            "type": "summary",
            "total_tokens": dict(self._tokens),
            "agent_tokens": self._agent_tokens,
        })

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
# Unfilled template placeholders the model echoes literally (e.g. "$X", "$Y", "[amount]")
_PLACEHOLDER_RE = _re.compile(
    r'\$[A-Z]\b'                  # $X, $Y, $Z
    r'|\[\s*(?:amount|value|number|price|ticker|date|name)\s*\]'  # [amount] etc.
    r'|\{[A-Z_]+\}',              # {PLACEHOLDER} style
    _re.IGNORECASE,
)

_SAME_DATE_RANGE_RE = _re.compile(
    r'between\s+'
    r'((?:January|February|March|April|May|June|July|August|September|'
    r'October|November|December)\s+\d{1,2}(?:,?\s*\d{4})?)'
    r'\s+and\s+\1',
    _re.IGNORECASE,
)


def _clean_llm_output(text: str) -> str:
    """Strip stray chat-template tokens, unfilled placeholders, and same-date ranges."""
    text = _TEMPLATE_TOKEN_RE.sub("", text)
    text = _PLACEHOLDER_RE.sub("", text)
    # "between June 4 and June 4, 2026" → "on June 4, 2026"
    text = _SAME_DATE_RANGE_RE.sub(r"on \1", text)
    return text.strip()


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

    # If signal_detail has TradingAgents defaults (parser missed the JSON block),
    # try harder to find and parse the JSON from final_trade_decision text.
    # The model sometimes omits the ```json label or writes JSON unfenced.
    if (signal_detail
            and "No parseable JSON block" in str(signal_detail.get("warning_message", ""))
            and isinstance(decision, str)):
        import json as _json
        parsed: dict | None = None
        try:
            # Strategy 1: fenced with ```json (original TradingAgents approach)
            from tradingagents.graph.signal_processing import _parse_json_block
            parsed = _parse_json_block(decision)
        except Exception:
            pass
        if not parsed:
            try:
                # Strategy 2: fenced with ``` but no json label
                m = _re.search(r'```\s*\n(\{.*?\})\s*\n\s*```', decision, _re.DOTALL)
                if m:
                    parsed = _json.loads(m.group(1))
            except Exception:
                pass
        if not parsed:
            try:
                # Strategy 3: last bare { ... } block containing "signal"
                start = decision.rfind('{')
                end = decision.rfind('}')
                if start >= 0 and end > start and '"signal"' in decision[start:end + 1]:
                    parsed = _json.loads(decision[start:end + 1])
            except Exception:
                pass
        if parsed:
            allowed = set(signal_detail.keys())
            parsed["signal"] = signal_str  # canonical signal always wins
            for k, v in parsed.items():
                if k in allowed:
                    signal_detail[k] = v
            signal_detail["warning_message"] = None  # clear stale default warning

    # Fundamentals: if empty string, try to surface a data-unavailable note
    fundamentals = to_json(_get(final_state, "fundamentals_report")) or None

    # Relabel the Trader's "FINAL TRANSACTION PROPOSAL" to distinguish it from the
    # PM's canonical signal. Both use the same label by design in TradingAgents, but
    # the Trader proposes BEFORE the risk debate — the PM decides AFTER. Showing both
    # with identical labels creates A-vs-B contradictions in the final report.
    trader_plan = to_json(_get(final_state, "trader_investment_plan"))
    if isinstance(trader_plan, str):
        trader_plan = trader_plan.replace(
            "FINAL TRANSACTION PROPOSAL", "TRADER'S PROPOSED SIGNAL (pre-risk-debate)"
        )
        # Detect if Trader's proposed signal disagrees with PM's final signal
        import re as _re2
        trader_match = _re2.search(
            r"TRADER'S PROPOSED SIGNAL.*?:\s*\*{0,2}\s*(BUY|SELL|HOLD)\b",
            trader_plan, _re2.IGNORECASE,
        )
        if trader_match and signal_str:
            trader_sig = trader_match.group(1).upper()
            pm_sig = signal_str.upper()
            if trader_sig != pm_sig:
                trader_plan += (
                    f"\n\n> ℹ️ **Pipeline note**: The Trader initially proposed **{trader_sig}** "
                    f"above. After the risk debate, the Portfolio Manager issued a final decision "
                    f"of **{pm_sig}**. The PM's signal is authoritative — see PM Decision section."
                )

    return {
        "signal": signal_str,
        "signal_detail": signal_detail,
        "market_report": to_json(_get(final_state, "market_report")),
        "fundamentals_report": fundamentals,
        "sentiment_report": to_json(_get(final_state, "sentiment_report")),
        "news_report": to_json(_get(final_state, "news_report")),
        "trader_investment_plan": trader_plan,
        "final_trade_decision": decision,
        "investment_debate": debate_to_text(_get(final_state, "investment_debate_state")),
        "risk_debate": debate_to_text(_get(final_state, "risk_debate_state")),
    }


# ── Price sanity check ────────────────────────────────────────────────────

# ── Entity sanity check ───────────────────────────────────────────────────

# Regex: multi-word capitalized strings followed by corporate suffixes
_ENTITY_RE = _re.compile(
    r'\b([A-Z][A-Za-z&]+(?:\s+[A-Z][A-Za-z&]+){1,4}'
    r'\s+(?:Inc\.?|LLC|Ltd\.?|LP|Capital|Partners|Management|Fund|Group|'
    r'Associates|Corp\.?|Corporation|Advisors?|Investments\b|Securities|Holdings?))\b'
    # Requires at least 2 capitalised words before the suffix so single-word
    # generic phrases like "Strategic Investments" or "Infrastructure Fund" are
    # not treated as company names. "Financial Avengers Inc" (2 words) still matches.
)


# Common English adjectives/participles that should NOT be the first word of a company name.
# Prevents "Driven Network Management", "Integrated Solutions Group" etc. from matching.
_ENTITY_NON_STARTERS = {
    "driven", "based", "integrated", "advanced", "enhanced", "focused",
    "led", "powered", "enabled", "supported", "related", "aligned",
    "dedicated", "unified", "connected", "automated", "optimized",
}


def _extract_entities_from_text(text: str) -> set[str]:
    # Skip markdown header lines — they contain descriptive phrases
    prose = "\n".join(
        line for line in text.splitlines()
        if not line.lstrip().startswith("#")
    )
    return {
        m.group(1).strip()
        for m in _ENTITY_RE.finditer(prose)
        if m.group(1).split()[0].lower() not in _ENTITY_NON_STARTERS
    }


def _extract_entities_from_tool_output(raw: str) -> set[str]:
    """Extract entity names from raw CSV/text tool output (holder/transaction data)."""
    entities: set[str] = set()
    entities.update(_extract_entities_from_text(raw))
    # Also grab any Holder column values from CSV rows
    for line in raw.splitlines():
        parts = line.split(",")
        if len(parts) >= 2:
            candidate = parts[1].strip().strip('"')
            if len(candidate) > 3 and candidate[0].isupper():
                entities.add(candidate)
    return {e for e in entities if len(e) > 4}


_DERIVED_PCT_RE = _re.compile(
    r'\b(?:of articles|of headlines|of the articles|approximately|estimated|roughly|'
    r'about |around |polarity|breakdown|ratio|proportion|tally|self.comput|'
    r'analyst.count|positive(?:\s+\w+){0,3}\s+articles?|negative(?:\s+\w+){0,3}\s+articles?)',
    _re.IGNORECASE,
)


def _sanity_check_percentages(result: dict) -> dict:
    """Remove sentences with percentage figures not found in ANY raw tool output."""
    # Widen source to all tool outputs available to news/sentiment nodes
    raw_sources = " ".join(filter(None, [
        _TOOL_LAST.get(k, "") for k in (
            "get_news", "get_global_news", "get_market_context",
            "get_earnings_calendar", "get_fundamentals", "get_analyst_ratings",
            "get_insider_transactions", "get_institutional_holders",
        )
    ]))
    if not raw_sources.strip():
        return result

    # Extract all percentage values from ALL tool outputs
    real_pcts = set()
    for m in _re.finditer(r'(\d+\.?\d*)\s*%', raw_sources):
        real_pcts.add(m.group(1))

    for field in ("news_report", "sentiment_report"):
        text = result.get(field)
        if not isinstance(text, str):
            continue

        lines = text.splitlines()
        clean_lines: list[str] = []
        removed_count = 0

        for line in lines:
            pcts_in_line = _re.findall(r'(\d+\.?\d*)\s*%', line)
            unverified = [p for p in pcts_in_line if p not in real_pcts]

            # Exempt self-computed/analyst-derived percentages
            if unverified and _DERIVED_PCT_RE.search(line):
                unverified = []

            if unverified and pcts_in_line:
                # Drop the line silently — no placeholder, to avoid orphaned headers
                removed_count += 1
            else:
                clean_lines.append(line)

        if removed_count:
            # Clean up orphaned section headers: a header is orphaned if
            # no non-empty, non-header line follows it before the next header.
            all_lines = "\n".join(clean_lines).splitlines()
            final_lines: list[str] = []
            i = 0
            while i < len(all_lines):
                line = all_lines[i]
                if _re.match(r'#{1,6}\s', line):
                    # Look ahead for content
                    j = i + 1
                    has_content = False
                    while j < len(all_lines):
                        ahead = all_lines[j].strip()
                        if _re.match(r'#{1,6}\s', all_lines[j]):
                            break  # hit next header without content
                        if ahead:
                            has_content = True
                            break
                        j += 1
                    if has_content:
                        final_lines.append(line)
                    # else: drop the orphaned header
                else:
                    final_lines.append(line)
                i += 1
            cleaned = "\n".join(final_lines)
            result[field] = cleaned.strip()
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "PERCENTAGE_SANITY: removed %d line(s) with unverified percentages from %s",
                removed_count, field,
            )

    return result


def _sanity_check_entities(result: dict, ticker: str = "") -> dict:
    """Flag institutional entity names in news_report not present in raw tool data."""
    news = result.get("news_report")
    if not isinstance(news, str) or not news:
        return result

    raw_holders = _TOOL_LAST.get("get_institutional_holders", "")
    raw_insiders = _TOOL_LAST.get("get_insider_transactions", "")
    raw_news = _TOOL_LAST.get("get_news", "")
    raw_global_news = _TOOL_LAST.get("get_global_news", "")
    if not raw_holders and not raw_insiders and not raw_news:
        return result

    real_entities = _extract_entities_from_tool_output(raw_holders)
    real_entities.update(_extract_entities_from_tool_output(raw_insiders))
    # News articles legitimately mention entity names — include them as real sources.
    # MarketBeat-style "XYZ purchased N shares of NVDA" headlines are from real 13F filings.
    real_entities.update(_extract_entities_from_text(raw_news))
    real_entities.update(_extract_entities_from_text(raw_global_news))

    # Scan full news report for entity names (sentence splitter would break on "Inc.")
    report_entities = _extract_entities_from_text(news)

    # Known-safe: entities from news articles (not from institutional-data tools)
    _KNOWN_SOURCES = {
        "Morningstar", "Appaloosa Management", "MarketBeat", "Motley Fool",
        "Seeking Alpha", "Wall Street", "Federal Reserve", "Goldman Sachs",
        "Morgan Stanley", "Bank of America", "Wells Fargo", "Citigroup",
    }
    # Extract subject company name from get_fundamentals output
    raw_fundamentals = _TOOL_LAST.get("get_fundamentals", "")
    company_name_match = _re.search(r"^Name:\s*(.+)$", raw_fundamentals, _re.MULTILINE)
    if company_name_match:
        _KNOWN_SOURCES.add(company_name_match.group(1).strip())
    if ticker:
        _KNOWN_SOURCES.add(ticker.upper())
        _KNOWN_SOURCES.add(ticker.lower())

    report_entities = {
        e for e in report_entities
        if not any(known.lower() in e.lower() or e.lower() in known.lower()
                   for known in _KNOWN_SOURCES)
    }

    fabricated = {
        e for e in report_entities
        if not any(e.lower() in real.lower() or real.lower() in e.lower()
                   for real in real_entities)
        # Only flag if it sounds like an institutional entity (has corporate suffix)
        and _re.search(
            r'\b(?:Inc\.?|LLC|Ltd\.?|LP|Capital|Partners|Management|Fund|Group|'
            r'Associates|Corp\.?|Corporation|Advisors?|Investments?|Securities|Holdings?)\b',
            e, _re.IGNORECASE
        )
    }

    if fabricated:
        # Redact fabricated entity names from body text so they can't be read as fact
        redacted_news = news
        for entity in fabricated:
            redacted_news = redacted_news.replace(
                entity,
                f"[REDACTED — '{entity}' not found in any tool output]"
            )
        banner = (
            "\n\n> ⚠️ **ENTITY SANITY CHECK FAILED**: The following institutional entity "
            f"name(s) appeared in this report but were NOT found in any raw tool output "
            f"(get_news, get_institutional_holders, get_insider_transactions). "
            f"Mentions have been redacted in the body text: "
            f"**{', '.join(sorted(fabricated))}**.\n\n"
        )
        result["news_report"] = banner + redacted_news
        import logging as _logging
        _logging.getLogger(__name__).warning(
            "ENTITY_SANITY_FAIL: fabricated institutional names detected and redacted: %s",
            fabricated
        )

    return result


_PRICE_DEVIATION_THRESHOLD = 0.50  # flag / auto-correct if >50% off real price

# ── Debate price hallucination check ──────────────────────────────────────

def _sanity_check_debate_prices(result: dict, ticker: str, trade_date: str) -> dict:
    """Scan debate text for price figures inconsistent with the real trading range."""
    real = _fetch_real_price(ticker, trade_date)
    if not real or real <= 0:
        return result

    # Fetch 52-week range from yfinance if available
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        wk52_high = float(info.get("fiftyTwoWeekHigh") or real * 1.5)
        wk52_low  = float(info.get("fiftyTwoWeekLow")  or real * 0.5)
    except Exception:
        wk52_high = real * 1.5
        wk52_low  = real * 0.5

    # Any mentioned price more than 30% above the real 52-week high is likely stale/pre-split.
    # Threshold: 1.3× real 52-week high (catches pre-split NVDA $378 vs real high $236).
    upper_bound = wk52_high * 1.3

    # Magnitude qualifiers that indicate the value is NOT a per-share price
    _MAGNITUDE_SUFFIXES = _re.compile(
        r'\s*(?:million|billion|thousand|mn|bn|[MBK]\b)', _re.IGNORECASE
    )
    # Non-price financial context words (e.g. "$30 million investment")
    # Note: avoid single-letter abbreviations (M/B/K) as they match mid-word with IGNORECASE
    _NON_PRICE_CONTEXT = _re.compile(
        r'(?:million|billion|thousand|mn|bn'
        r'|investment|deal|facility|fund|revenue|loan|contract|grant|award'
        r'|capex|spending|budget|commitment|raise|round|valuation)',
        _re.IGNORECASE
    )

    price_pattern = _re.compile(r'\$\s*([\d,]+(?:\.\d+)?)')
    flagged_fields: dict[str, list[str]] = {}

    for field in ("investment_debate", "risk_debate"):
        text = result.get(field) or ""
        if not isinstance(text, str):
            continue
        suspicious = []
        for m in price_pattern.finditer(text):
            try:
                val = float(m.group(1).replace(",", ""))
            except ValueError:
                continue
            if val <= upper_bound or val >= upper_bound * 20:
                continue
            # Skip if immediately followed by % — it's a return/rate, not a price
            after = text[m.end():m.end() + 20]
            if after.lstrip().startswith('%'):
                continue
            # Skip if followed by a magnitude qualifier (not a per-share price)
            if _MAGNITUDE_SUFFIXES.match(after):
                continue
            # Skip if non-price context word appears within 30 chars after
            context = text[max(0, m.start() - 5):m.end() + 30]
            if _NON_PRICE_CONTEXT.search(context):
                continue
            suspicious.append(f"${m.group(1)}")
        if suspicious:
            flagged_fields[field] = list(set(suspicious))

    if flagged_fields:
        # Use closing-price 52-week high (consistent with what the Technical Analyst reports)
        # yfinance fiftyTwoWeekHigh is intraday; the report body typically uses closing highs
        for field, prices in flagged_fields.items():
            banner = (
                f"\n\n> ⚠️ **PRICE GROUNDING WARNING**: The following per-share price figure(s) "
                f"in this section appear inconsistent with the real trading range "
                f"(52-week closing high ~${wk52_high:.2f}, current ~${real:.2f}). "
                f"Note: the 52-week intraday high from yfinance may differ slightly from "
                f"the 52-week closing high cited in the Technical Analysis Report — "
                f"both are valid but label them correctly. "
                f"Flagged values: **{', '.join(prices)}**. "
                f"These may be pre-split or memorized training-data prices.\n\n"
            )
            result[field] = banner + result[field]

    return result

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


def _rewrite_pm_json_in_text(text: str, corrected: dict) -> str:
    """Overwrite corrected fields in the last fenced JSON block inside final_trade_decision.

    This propagates signal_detail corrections to the string that the rendering
    layer (frontend section + PDF export) actually displays.
    """
    import json as _json_inner
    matches = list(_re.finditer(r'```(?:json)?\s*\n(\{.*?\})\s*\n?```', text, _re.DOTALL))
    if not matches:
        return text
    m = matches[-1]
    try:
        parsed = _json_inner.loads(m.group(1))
    except Exception:
        return text
    for k in ("currency", "entry_reference_price", "target_price", "stop_loss"):
        if k in corrected:
            parsed[k] = corrected[k]
    new_json = _json_inner.dumps(parsed, indent=2)
    return text[: m.start(1)] + new_json + text[m.end(1):]


def _sanity_check_price(result: dict, ticker: str, trade_date: str) -> dict:
    """Populate/correct entry_reference_price and flag size_fraction inconsistencies."""
    import re as _re

    real = _fetch_real_price(ticker, trade_date)

    # Also apply sanity checks to signal_detail (the structured TradeRecommendation)
    for key in ("final_trade_decision", "signal_detail"):
        decision = result.get(key)
        if not isinstance(decision, dict):
            continue

        # ── currency: always USD for trading prices (P1) ─────────────────────
        if real and real > 0:
            decision["currency"] = "USD"

        # ── entry_reference_price: populate if null, correct if wrong ────────
        model_price = decision.get("entry_reference_price")
        if real and real > 0:
            if not model_price:
                decision["entry_reference_price"] = real
            else:
                deviation = abs(model_price - real) / real
                if deviation > _PRICE_DEVIATION_THRESHOLD:
                    decision["entry_reference_price"] = real
                    # Cascade: null target and stop — they were anchored to a
                    # fabricated entry and are no longer meaningful (P2)
                    decision["target_price"] = None
                    decision["stop_loss"] = None
                    sanity_w = (
                        f"[PRICE SANITY] Model stated ${model_price:.2f}; "
                        f"yfinance close ${real:.2f} ({deviation*100:.0f}% deviation). "
                        "entry_reference_price auto-corrected; target_price and stop_loss "
                        "nulled (were anchored to fabricated price)."
                    )
                    # P3: keep PM's warning_message separate — don't concatenate (P3)
                    decision["warning_message"] = sanity_w
                    if key == "signal_detail" and result.get("market_report"):
                        banner = (
                            f"\n\n> ⚠️ **PRICE WARNING**: Model stated ~${model_price:.0f}; "
                            f"real close is ${real:.2f}. entry_reference_price corrected; "
                            "target/stop nulled.\n\n"
                        )
                        result["market_report"] = banner + result["market_report"]

        # ── size_fraction: warn if wildly inconsistent with narrative text ──
        sf = decision.get("size_fraction")
        if sf is not None and sf > 0:
            # Collect percentage mentions from all narrative fields
            narrative = " ".join(
                str(result.get(f, "") or "")
                for f in ("trader_investment_plan", "final_trade_decision",
                          "investment_debate", "risk_debate")
            )
            pct_mentions = [
                float(m) / 100
                for m in _re.findall(r'\b(\d{1,2})\s*%\s*(?:of\s+(?:the\s+)?portfolio|allocation)',
                                     narrative, _re.IGNORECASE)
                if 1 <= float(m) <= 50  # plausible position-size percentages
            ]
            if pct_mentions:
                avg_narrative = sum(pct_mentions) / len(pct_mentions)
                if sf > avg_narrative * 2.5:
                    w = (
                        f"[SIZE SANITY] structured size_fraction={sf:.0%} is {sf/avg_narrative:.1f}× "
                        f"the debate's average proposed allocation ({avg_narrative:.0%}). "
                        "size_fraction may not reflect the debate consensus."
                    )
                    decision["warning_message"] = (
                        (decision.get("warning_message") or "") + " " + w
                    ).strip()

    # Propagate signal_detail corrections into the markdown string that the
    # rendering layer (frontend section + PDF export) actually displays.
    # Without this, _sanity_check_price only fixes signal_detail (the hero card)
    # while final_trade_decision (the PM Decision section body) stays uncorrected.
    sd = result.get("signal_detail")
    ftd = result.get("final_trade_decision")
    if isinstance(sd, dict) and isinstance(ftd, str):
        result["final_trade_decision"] = _rewrite_pm_json_in_text(ftd, sd)

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
    # Maps analyst key → original creator function (populated if Gemini patch applied)
    _saved_creators: dict[str, Any] = {}

    try:
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        q = run_manager.get(run_id)["queue"]
        callback = SSECallbackHandler(q, loop)
        logger = LoggingCallbackHandler(run_id)

        # Reset per-run dedup counters and caches
        _DEDUP_SEEN.clear()
        _NAME_SEEN.clear()
        _DEDUP_CACHE.clear()
        _TOOL_LAST.clear()

        # ── Gemini analyst routing ─────────────────────────────────────────
        # These analyst nodes are routed to Gemini because local 7B models
        # consistently fabricate data for them despite receiving real tool output.
        # Must be applied before TradingAgentsGraph() calls _build_analyst_nodes().
        # Restored unconditionally in the finally block below.
        #
        # Map: analyst key in selected_analysts → setup.py attribute name
        _GEMINI_ANALYST_ATTRS: dict[str, str] = {
            "fundamentals": "create_fundamentals_analyst",
            "social":       "create_social_media_analyst",
            "news":         "create_news_analyst",
            "market":       "create_market_analyst",
        }
        _active_gemini = [k for k in _GEMINI_ANALYST_ATTRS if k in analysts]
        if _active_gemini:
            try:
                import tradingagents.graph.setup as _gs
                from tradingagents.llm import build_chat_model as _bcm
                _gemini_llm = _bcm(
                    "google_genai", "gemini-3.1-flash-lite",
                    reasoning_effort="high",   # → thinking_level="high" for Gemini
                    callbacks=[callback, logger],
                )
                for analyst_key in _active_gemini:
                    attr = _GEMINI_ANALYST_ATTRS[analyst_key]
                    orig = getattr(_gs, attr)
                    _saved_creators[attr] = orig
                    setattr(_gs, attr, lambda _, _orig=orig: _orig(_gemini_llm))
            except Exception:
                _saved_creators = {}  # patch failed — run without override

        # ── Risk Debate nodes → qwen3:8b ──────────────────────────────────
        _RISK_DEBATE_ATTRS = (
            "create_aggressive_debator",
            "create_neutral_debator",
            "create_conservative_debator",
        )
        try:
            import tradingagents.graph.setup as _gs
            from langchain_ollama import ChatOllama as _ChatOllama
            _qwen3_llm = _ChatOllama(
                model="qwen3:8b",
                temperature=0.5,   # experiment: was Ollama default (~0.8)
                repeat_penalty=1.1,
                num_ctx=8192,
                callbacks=[callback, logger],
            )
            for attr in _RISK_DEBATE_ATTRS:
                orig = getattr(_gs, attr)
                _saved_creators[attr] = orig
                setattr(_gs, attr, lambda _, _orig=orig: _orig(_qwen3_llm))
        except Exception:
            pass  # fall back to quick_thinking_llm

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
        result = _sanity_check_entities(result, ticker=ticker)
        result = _sanity_check_debate_prices(result, ticker, trade_date)
        result = _sanity_check_percentages(result)

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
        # Always restore all patched analyst creators regardless of outcome.
        if _saved_creators:
            try:
                import tradingagents.graph.setup as _gs
                for attr, orig in _saved_creators.items():
                    setattr(_gs, attr, orig)
            except Exception:
                pass
