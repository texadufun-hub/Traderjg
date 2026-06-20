# Traderjg

A full-stack AI trading journal that wraps the **[TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)** multi-agent LLM framework behind a React dashboard and a FastAPI backend, deployable to Google Cloud Run.

---

## What it does

Traderjg lets you run institutional-grade AI analysis on any ticker — the same pipeline a trading firm would use — then log your actual trades alongside the AI's recommendations.

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
  SIGNAL: BUY / OVERWEIGHT / HOLD / UNDERWEIGHT / SELL
```

Everything streams live to the browser as agents work.

---

## Features

| Feature | Detail |
|---|---|
| **Live streaming** | SSE feed shows every tool call, LLM invocation, and agent transition in real time |
| **Agent timeline** | Visual 12-step progress indicator, colour-coded by status |
| **All 4 analysts** | Technical (MACD/RSI), Sentiment (Reddit/StockTwits), News (macro/global), Fundamentals (financials) |
| **Bull/Bear debate** | Configurable rounds — researchers challenge each other's thesis |
| **Risk assessment** | Three-way debate between aggressive, neutral, and conservative risk analysts |
| **5-tier signals** | BUY · OVERWEIGHT · HOLD · UNDERWEIGHT · SELL with full PM rationale |
| **12 LLM providers** | OpenAI, Anthropic, Google, xAI, DeepSeek, Qwen, GLM, MiniMax, OpenRouter, Ollama, AWS Bedrock, Azure |
| **Deep/Quick split** | Use a powerful model for reasoning, a fast one for lightweight calls |
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
│  /memory       — TradingAgents reflection log             │
│  /trades       — trade CRUD                               │
│  /config       — API key management                       │
│                                                           │
│  agent_runner.py                                          │
│    ThreadPoolExecutor  ← runs TradingAgentsGraph          │
│    SSECallbackHandler  ← LangChain → asyncio.Queue        │
│    RunManager          ← per-run SSE queues               │
└────────────────────────┬─────────────────────────────────┘
                         │  Python SDK
┌────────────────────────▼─────────────────────────────────┐
│           TauricResearch/TradingAgents                    │
│   LangGraph · LangChain · yfinance · FRED · StockTwits   │
│   Reddit · Polymarket · Alpha Vantage · stockstats        │
└──────────────────────────────────────────────────────────┘
```

**Storage:**  SQLite (`/app/data/traderjg.db`) for trades + analyses. TradingAgents writes results and memory log to `/app/data/`.

---

## Quick start

### 1. Clone and configure

```bash
git clone <this-repo>
cd Traderjg
cp .env.example .env
```

Edit `.env` and add at least one LLM API key:

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
docker compose up
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

## Configuration

All options can be set via the **Settings** tab in the UI or via `.env`:

```env
# Default LLM (overridden per-run in the UI)
TRADINGAGENTS_LLM_PROVIDER=openai
TRADINGAGENTS_DEEP_THINK_LLM=gpt-4o
TRADINGAGENTS_QUICK_THINK_LLM=gpt-4o-mini

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
| Google (Gemini) | `google` |
| xAI (Grok) | `xai` |
| DeepSeek | `deepseek` |
| Alibaba Qwen (DashScope) | `dashscope` |
| Zhipu GLM | `zhipu` |
| MiniMax | `minimax` |
| OpenRouter | `openrouter` |
| Ollama (local) | `ollama` |
| AWS Bedrock | `bedrock` |
| Azure OpenAI | `azure` |

---

## Project structure

```
Traderjg/
├── backend/
│   ├── main.py            # FastAPI app — all endpoints
│   ├── agent_runner.py    # TradingAgents wrapper + SSE callback
│   ├── models.py          # SQLAlchemy models (Trade, Analysis)
│   ├── schemas.py         # Pydantic request/response schemas
│   ├── database.py        # SQLite setup
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx                     # Top-level tab navigation
│   │   ├── pages/
│   │   │   ├── AnalyzePage.tsx         # Run new analysis + live stream
│   │   │   ├── HistoryPage.tsx         # Browse past analyses
│   │   │   ├── TradePage.tsx           # Trade journal
│   │   │   ├── MemoryPage.tsx          # TradingAgents memory log
│   │   │   └── SettingsPage.tsx        # API keys + model config
│   │   ├── components/
│   │   │   ├── AgentTimeline.tsx       # 12-step live pipeline progress
│   │   │   ├── StreamLog.tsx           # Real-time SSE event log
│   │   │   ├── AnalysisResult.tsx      # Full structured result display
│   │   │   ├── SignalBadge.tsx         # Colour-coded signal chip
│   │   │   ├── Dashboard.tsx           # Portfolio stats + recent analyses
│   │   │   ├── TradeForm.tsx           # Add/edit trade (with analysis link)
│   │   │   ├── TradeList.tsx           # Trade history table
│   │   │   └── StatCard.tsx            # Metric card
│   │   ├── api/                        # Typed Axios API clients
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
| Backend | 2 GiB | 2 | LLM analysis can run 5–15 min; timeout set to 3600s |
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
| `GET` | `/runs` | List all past runs |
| `GET` | `/runs/{id}` | Get run detail + result |
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
- Persistent trade journal with P&L tracking
- Docker Compose and Google Cloud Run deployment

---

## Disclaimer

This application is for **research and educational purposes only**. It does not constitute financial advice. Trading performance depends on model choice, data quality, market conditions, and many other factors. Never trade with money you cannot afford to lose.
