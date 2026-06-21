FROM python:3.12-slim

WORKDIR /app

# System deps for some tradingagents transitive deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Override analyst prompts to enforce tool-first behavior for local LLMs
RUN cp /app/prompt_patches/*.md \
    /usr/local/lib/python3.12/site-packages/tradingagents/agents/prompts/

RUN mkdir -p /app/data/results /app/data/cache

ENV PORT=8080

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
