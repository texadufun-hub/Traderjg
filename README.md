# Traderjg

A full-stack AI trading journal that wraps the **[TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)** multi-agent LLM framework behind a React dashboard and a FastAPI backend, deployable to Google Cloud Run.

---

## What it does

Traderjg lets you run institutional-grade AI analysis on any ticker — the same pipeline a trading firm would use — then log your actual trades alongside the AI's recommendations. Runs on cloud LLMs (Gemini, GPT, Claude) or fully **offline on a local Ollama instance** with no API costs.

### The analysis pipeline

Each run sends a ticker through a **12-agent LangGraph workflow**:

```
Technical Analyst ──┐
Sentiment Analyst ──┤ (parallel analysts)
News Analyst ────── ┤
Fundamentals Analyst┘
        │
   Bull Researcher ←──→ Bear Researcher  (debate rounds)
        │
   Research Manager
        │
      Trader
        │
   Aggressive ←──→ Neutral ←──→ Conservative  (risk debate rounds)
        │
  Portfolio Manager
        │
  SIGNAL: BUY / HOLD / SELL
```

Everything streams live to the browser as agents work.

---

## Features

| Feature | Detail |
|---|---|
| **Live streaming** | SSE feed shows every tool call, LLM invocation, and agent transition in real time |
| **Agent timeline** | Visual 12-step progress indicator, colour-coded by status |
| **All 4 analysts** | Technical (MACD/RSI/SMA), Sentiment (news-based), News (macro/global), Fundamentals (financials) |
| **Bull/Bear debate** | Configurable rounds — researchers challenge each other's thesis |
| **Risk assessment** | Three-way debate between aggressive, neutral, and conservative risk analysts |
| **3-tier signals** | BUY · HOLD · SELL with full PM rationale and size/confidence from risk judge |
| **Local LLM support** | Full Ollama integration — run with zero API cost on your own hardware |
| **Deep/Quick split** | Use a powerful model for reasoning (PM, risk judge), a fast one for the other 10 agents |
| **PDF export** | Export any analysis to a formatted PDF; multi-select to bundle several runs into one document |
| **Run logs** | Per-run JSONL logs with full prompts, model responses, and per-call token counts |
| **Model badge** | History list and detail view show which provider/model ran each analysis |
| **12 LLM providers** | OpenAI, Anthropic, Google, xAI, DeepSeek, Qwen, GLM, MiniMax, OpenRouter, Ollama, HuggingFace, LiteLLM |
| **Multi-language** | Reports in English, Chinese, Japanese, Korean, French, Spanish, German |
| **Global markets** | Any Yahoo Finance ticker: US, HK (`.HK`), Tokyo (`.T`), Shanghai (`.SS`), crypto (`BTC-USD`) |
| **Checkpoint resume** | LangGraph SQLite checkpointing — interrupted runs pick up where they left off |
| **Memory & reflection** | Past decisions and post-trade lessons fed back to future analysts |
| **Trade journal** | Log real trades, link them to an analysis run, track P&L |
| **Portfolio stats** | Total P&L, win rate, average trade, best/worst trade |

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                     React Frontend                        │
│  Dashboard │ Analyze │ History │ Journal │ Memory │ Settings │
│                  (Vite + TypeScript)                      │
└────────────────────────┬─────────────────────────────────┘
                         │  REST + SSE  (/api/*)
┌────────────────────────▼─────────────────────────────────┐
│                    FastAPI Backend                         │
│  /runs         — start analysis, stream events            │
│  /runs/{id}/log — full per-run prompt/response/token log  │
│  /memory       — TradingAgents reflection log             │
│  /trades       — trade CRUD                               │
│  /config       — API key management                       │
│                                                           │
│  agent_runner.py                                          │
│    ThreadPoolExecutor  ← runs TradingAgentsGraph          │
│    SSECallbackHandler  ← LangChain → asyncio.Queue        │
│    LoggingCallbackHandler ← full JSONL run log            │
│    RunManager          ← per-run SSE queues               │
│    Tool dedup patch    ← prevents small-model loops       │
│    Prompt patches      ← overlays for local LLM behaviour │
└────────────────────────┬─────────────────────────────────┘
                         │  Python SDK
┌────────────────────────▼─────────────────────────────────┐
│           TauricResearch/TradingAgents                    │
│   LangGraph · LangChain · yfinance · FRED · StockTwits   │
│   Reddit · Polymarket · Alpha Vantage · stockstats        │
└──────────────────────────────────────────────────────────┘
```

**Storage:** SQLite (`/app/data/traderjg.db`) for trades + analyses. TradingAgents writes results and memory log to `/app/data/`. Per-run JSONL logs written to `/app/data/logs/`.

---

## Quick start

### 1. Clone and configure

```bash
git clone <this-repo>
cd Traderjg
cp .env.example .env
```

Edit `.env` and add at least one LLM API key (or configure Ollama below):

```env
OPENAI_API_KEY=sk-...          # or
ANTHROPIC_API_KEY=sk-ant-...   # or
GOOGLE_API_KEY=AIza...
```

For macro data (FRED indicators in the News analyst):
```env
FRED_API_KEY=...   # free at fred.stlouisfed.org
```

### 2. Run with Docker Compose

```bash
docker-compose up
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8080 |
| API docs | http://localhost:8080/docs |

### 3. Run your first analysis

1. Open http://localhost:3000
2. Click **Settings** → enter your API keys → Save
3. Click **Analyze** → enter a ticker (e.g. `NVDA`) and date
4. Select analysts, choose your LLM provider and models
5. Click **Run Analysis →** and watch the agents work live

---

## Local LLM with Ollama

Traderjg runs fully offline using a local [Ollama](https://ollama.com) instance — no API costs, no token limits.

### Setup

1. Install Ollama and pull a model with tool-calling support:

```bash
ollama pull gemma4:e2b-it-qat   # current default — runs on 6 GB VRAM
ollama pull qwen2.5:7b           # alternative with stronger tool-use reliability
ollama pull qwen2.5:14b          # best quality, needs ~9 GB VRAM
```

2. In the **Analyze** form, select **Ollama (local)** as the provider and enter your Ollama host:

```
http://localhost:11434      # local
http://192.168.1.x:11434   # remote machine on LAN
```

3. Set the model name (must match what Ollama has pulled).

### Recommended model split

The pipeline has two model tiers. You can use different models for each:

| Tier | Agents | Current default |
|---|---|---|
| **Deep think** | Research Manager, Risk Judge (final decisions) | `gemma4:e2b-it-qat` |
| **Quick think** | 4 analysts + Bull/Bear + Trader + 3 risk debaters | `gemma4:e2b-it-qat` |

### VRAM requirements

| Model | VRAM | Notes |
|---|---|---|
| `gemma4:e2b-it-qat` | ~2 GB | Current default — 2B params, fits any 6 GB card |
| `qwen2.5:7b` | ~5 GB | Better tool-use reliability; fits in 6 GB |
| `qwen2.5:14b` | ~9 GB | Significant quality jump; needs 10 GB+ VRAM |

### Multi-GPU

Ollama automatically distributes model layers across all available GPUs. To restrict to a specific GPU (e.g. when mixing old and new cards):

```bash
CUDA_VISIBLE_DEVICES=<index> ollama serve
```

### Small-model reliability

Several patches are applied automatically to improve reliability with smaller local models:

- **Context window**: Ollama's default `num_ctx=2048` is too small for the debate context. All models are patched to `num_ctx=8192`.
- **Tool deduplication**: Models that loop on repeated tool calls are stopped after 2 identical calls (`get_stock_data`) or 4 total calls (`get_indicators`), with an explicit stop signal.
- **Prompt patches**: Analyst prompts are overlaid with instructions that small models need: "call a tool first", "use exact numbers from tool output", "no placeholder tables".
- **Output sanity checks**: Stop-loss/target-price field swaps are auto-corrected; ROE/ROA/margins are formatted as percentages before being passed to the model.

---

## Configuration

All options can be set via the **Settings** tab in the UI or via `.env`:

```env
# Default LLM (overridden per-run in the UI)
TRADINGAGENTS_LLM_PROVIDER=openai
TRADINGAGENTS_DEEP_THINK_LLM=gpt-4o
TRADINGAGENTS_QUICK_THINK_LLM=gpt-4o-mini

# Ollama (if using local LLM)
OLLAMA_HOST=http://localhost:11434

# Research depth
TRADINGAGENTS_MAX_DEBATE_ROUNDS=1
TRADINGAGENTS_MAX_RISK_ROUNDS=1

# Output
TRADINGAGENTS_OUTPUT_LANGUAGE=English
TRADINGAGENTS_TEMPERATURE=

# Checkpointing
TRADINGAGENTS_CHECKPOINT_ENABLED=false
```

### Supported tickers

| Market | Format | Example |
|---|---|---|
| US equities | `SYMBOL` | `AAPL`, `NVDA`, `SPY` |
| Crypto | `COIN-USD` | `BTC-USD`, `ETH-USD` |
| Hong Kong | `NNNN.HK` | `0700.HK` (Tencent) |
| Tokyo | `NNNN.T` | `7203.T` (Toyota) |
| Shanghai | `NNNNNN.SS` | `600519.SS` (Kweichow Moutai) |
| London | `SYMBOL.L` | `HSBA.L` |
| Any Yahoo Finance ticker | — | — |

### Supported LLM providers

| Provider | `llm_provider` value |
|---|---|
| OpenAI | `openai` |
| Anthropic (Claude) | `anthropic` |
| Google (Gemini) | `google_genai` |
| xAI (Grok) | `xai` |
| OpenRouter | `openrouter` |
| Ollama (local) | `ollama` |
| HuggingFace | `huggingface` |
| LiteLLM | `litellm` |

---

## PDF Export

Click **Export PDF** on any completed analysis to open a print-formatted page in a new tab. The browser's print dialog saves it as a PDF.

From the **History** page:
- Check any number of completed runs and click **Export N PDFs** to bundle them into a single multi-page PDF.
- Each analysis gets its own section with a page break between runs.

---

## Run Logs

Every analysis writes a detailed JSONL log to `/app/data/logs/<run_id>.jsonl` containing:

- Every agent start/end event
- Full prompt sent to the model (expandable)
- Full model response
- Per-call token counts (prompt ↑ / completion ↓ / total)
- Cumulative token count across the run
- Final summary with run totals

View logs in the app: open any run in History and scroll to the **Run Log** panel at the bottom. Use the filter buttons to focus on prompts, responses, tool calls, or errors.

Fetch logs via API: `GET /runs/{id}/log`

---

## Project structure

```
Traderjg/
├── backend/
│   ├── main.py               # FastAPI app — all endpoints
│   ├── agent_runner.py       # TradingAgents wrapper + SSE + logging callbacks
│   │                         # Also: tool dedup patch, num_ctx patch, output sanity checks
│   ├── models.py             # SQLAlchemy models (Trade, Analysis)
│   ├── schemas.py            # Pydantic request/response schemas
│   ├── database.py           # SQLite setup
│   ├── prompt_patches/       # Prompt overlays copied over installed TradingAgents prompts
│   │   ├── market_analyst.md
│   │   ├── news_analyst.md
│   │   ├── news_sentiment_analyst.md
│   │   ├── fundamentals_analyst.md
│   │   ├── conservative_debator.md
│   │   ├── neutral_debator.md
│   │   └── risk_manager.md
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx                     # Top-level tab navigation
│   │   ├── pages/
│   │   │   ├── AnalyzePage.tsx         # Run new analysis + live stream
│   │   │   ├── HistoryPage.tsx         # Browse past analyses + multi-select export
│   │   │   ├── TradePage.tsx           # Trade journal
│   │   │   ├── MemoryPage.tsx          # TradingAgents memory log
│   │   │   └── SettingsPage.tsx        # API keys + model config
│   │   ├── components/
│   │   │   ├── AgentTimeline.tsx       # 12-step live pipeline progress
│   │   │   ├── StreamLog.tsx           # Real-time SSE event log
│   │   │   ├── AnalysisResult.tsx      # Full structured result display
│   │   │   ├── SignalBadge.tsx         # Colour-coded signal chip
│   │   │   ├── ModelBadge.tsx          # Provider/model indicator badge
│   │   │   ├── RunLog.tsx              # Per-run log viewer with token counts
│   │   │   ├── Dashboard.tsx           # Portfolio stats + recent analyses
│   │   │   ├── TradeForm.tsx           # Add/edit trade (with analysis link)
│   │   │   ├── TradeList.tsx           # Trade history table
│   │   │   └── StatCard.tsx            # Metric card
│   │   ├── api/                        # Typed Axios API clients
│   │   ├── utils/
│   │   │   └── exportPdf.ts            # Browser-native PDF export utility
│   │   └── types/index.ts              # TypeScript types
│   ├── nginx.conf.template
│   └── Dockerfile
│
├── docker-compose.yml
├── cloudbuild.yaml         # Google Cloud Build + Cloud Run deploy
└── .env.example
```

---

## Deploy to Google Cloud Run

### Prerequisites

- Google Cloud project with Cloud Build, Cloud Run, and Container Registry APIs enabled
- Secret Manager secrets for your API keys (recommended)

### Deploy

```bash
# Replace with your project ID
gcloud builds submit \
  --config cloudbuild.yaml \
  --project YOUR_PROJECT_ID
```

After deploy, update the frontend Cloud Run service with the backend URL:

```bash
gcloud run services update traderjg-frontend \
  --set-env-vars BACKEND_URL=https://traderjg-backend-XXXX-uc.a.run.app \
  --region us-central1
```

### Cloud Run sizing

| Service | Memory | CPU | Notes |
|---|---|---|---|
| Backend | 2 GiB | 2 | LLM analysis can run 5–30 min; timeout set to 3600s |
| Frontend | 256 MiB | 1 | Static nginx, lightweight |

---

## API reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/config` | Current config (keys masked) |
| `PUT` | `/config` | Update API keys / defaults |
| `GET` | `/agents/order` | Ordered list of pipeline agents |
| `POST` | `/runs` | Start a new analysis run |
| `GET` | `/runs` | List all past runs (includes `llm_provider`, `deep_think_llm`) |
| `GET` | `/runs/{id}` | Get run detail + result |
| `GET` | `/runs/{id}/log` | Full per-run JSONL log (prompts, responses, token counts) |
| `DELETE` | `/runs/{id}` | Delete a run |
| `GET` | `/runs/{id}/stream` | SSE stream of live agent events |
| `GET` | `/memory` | TradingAgents memory/reflection log |
| `GET` | `/trades` | List trades |
| `POST` | `/trades` | Create trade |
| `PUT` | `/trades/{id}` | Update trade |
| `DELETE` | `/trades/{id}` | Delete trade |
| `GET` | `/stats` | Portfolio statistics |

Interactive API docs available at `/docs` when the backend is running.

---

## SSE event types

The `/runs/{id}/stream` endpoint emits JSON events:

| `type` | Meaning |
|---|---|
| `analysis_started` | Graph invocation began |
| `agent_start` | A named agent node started |
| `agent_end` | A named agent node finished |
| `tool_call` | An analyst called a data tool |
| `tool_result` | Tool returned data |
| `llm_start` | LLM call initiated |
| `complete` | Full result payload (all reports + signal) |
| `error` | Analysis failed with message |
| `heartbeat` | Keep-alive (every 300 s of inactivity) |

---

## Attribution

This project is built on top of **[TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)** (Apache-2.0), a multi-agent LLM trading framework developed by the Tauric Research team. The research behind it is published at [arXiv:2412.20138](https://arxiv.org/abs/2412.20138).

Traderjg adds:
- A FastAPI REST + SSE layer wrapping the Python SDK
- A React/TypeScript dashboard with live streaming
- Full Ollama integration for local/offline LLM inference
- PDF export (single run or multi-run bundle)
- Per-run JSONL logs with full token accounting
- Model badge showing provider/model per analysis
- Reliability patches for small local models (tool dedup, context window, prompt overlays, output sanity checks)
- Persistent trade journal with P&L tracking
- Docker Compose and Google Cloud Run deployment

---

## Disclaimer

This application is for **research and educational purposes only**. It does not constitute financial advice. Trading performance depends on model choice, data quality, market conditions, and many other factors. Never trade with money you cannot afford to lose.
