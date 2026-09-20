---
name: automated-trading-system
description: "Design and scaffold automated stock trading systems."
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [trading, automated-trading, krx, kis-api, quantitative, signal-generation, order-execution, risk-management, monitoring, fastapi]
---

# Automated Trading System Design

Use this skill when designing, planning, or scaffolding **automated stock trading systems**. Covers data source selection, signal generation, order execution, risk management, and monitoring architecture.

## When to apply

- "I want to build an automated trading system"
- "Compare data sources for stock signals"
- "Design the architecture for algorithmic trading in [market]"
- "How should I structure a quantitative trading pipeline?"

## Core Design Framework

Every automated trading system must resolve **5 sequential steps in a loop**:

```
[1. Data Fetch] → [2. Signal Analysis] → [3. Order Execution] → [4. Position/PnL] → [5. Daily Report] → Sleep → (repeat)
```

### Step 1: Data Fetch (Pre-condition / Risk table)
- Required: API token + rate limit config, data cleaning pipeline, Last-Fetched timestamping
- Risk: Rate limit exhaustion, stale data, network timeout, WebSocket disconnection

### Step 2: Signal Analysis (Pre-condition / Risk table)
- Required: TA library (pandas-ta), NLP/news pipeline, signal threshold config, state filter (skip already-held positions)
- Risk: Garbage-in/garbage-out, false signals, computation bottleneck as universe grows

### Step 3: Order Execution (Pre-condition / Risk table)
- Required: Broker API environment, idempotent order key, slippage check, order queue
- Risk: Partial fills, market conditions (no liquidity, halted stocks), API token expiry

### Step 4: Position & PnL (Pre-condition / Risk table)
- Required: periodic position polling, dynamic avg cost calc, day-open/closed detection, DB vs API consistency check
- Risk: Time-lag between price and position data, daily trade miss, FX rate error

### Step 5: Daily Report (Pre-condition / Risk table)
- Required: source trade log, report template, notification channel, daily rollover
- Risk: Market closing time confusion, report generation failure, next-day data corruption

## Architecture Principles

1. **State Machine** — must track: `Idle → Fetch → Analyze → Trade → Report → Sleep`. Unknown current state (market open/closed, API error waiting) is a bug source.
2. **Data Source of Truth** — separate price source (fetch step) from position/fill source (API source). Mixing origins causes PnL corruption.
3. **Non-Blocking** — spider-web fashion: N stocks × 1s each = N seconds. Use `asyncio` or `concurrent.futures`.
4. **Dead Letter Queue** — failed stocks must NOT block the loop. Queue them for retry or skip.

## Data Source Selection (Korean Markets - KOSPI/KOSDAQ)

### Quick comparison:

| Purpose | Recommended Source | Rate Limit Consideration |
|---------|-------------------|--------------------------|
| Real-time depth+trades | Broker KIS WebSocket | NOT counted as TR calls |
| REST 10-min OHLCV | Broker KIS REST API | ~60 TR/min recommended |
| Stock screening | KRX OPEN API + broker condition search | Free tier: 1 req/sec |
| News analysis | Naver/Dispatch crawl OR paid API | External dependency |
| Technical indicators | `pandas-ta` library | Local computation, no limit |

## Output Structure

When scaffolding a trading system project, produce:

```
trading_system/
├── config.py              # API keys, watchlist, thresholds
├── database.py            # DB init, schema design
├── engine.py              # Main loop (state machine)
├── datasource/            # Data source adapters
│   ├── broker_api.py      # REST + WebSocket client
│   └── external_api.py    # KRX, news, etc.
├── analyzer/              # Signal generation
│   ├── indicators.py      # Technical indicators
│   └── sentiment.py       # News NLP (optional)
├── executor/              # Order management
│   ├── order.py           # Place order, handle fills
│   └── position.py        # PnL calculation
├── reporter/              # Reporting
│   └── daily_report.py    # Daily summary & alert
├── main.py                # Entry point (FastAPI lifespan)
├── requirements.txt
└── .env.example
```

## Pitfalls
1. **Rate Limit TR Counting**: "1 TR = 1 HTTP request URL", not "1 API function". Multiple URLs = multiple TR counts.
2. **WebSocket vs REST**: REST price updates are lagged (seconds). Use WebSocket for real-time monitoring — WebSocket calls are NOT counted as TR.
3. **KRX OPEN API**: Free tier only 1 req/sec. Data is T+1 (not real-time). Use for daily screening, not intraday.
4. **Market hours**: KOSPI market 09:00-15:30 KST. Plan loop guard around open/close times.
