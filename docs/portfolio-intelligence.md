# Portfolio Intelligence

The backend analysis engine produces advisory-only portfolio decisions. It never places trades.

## Endpoints

- `GET /api/v1/intelligence/analysis`: full portfolio metrics, buy/sell/hold-style recommendations, optimization, alerts and data-quality warnings.
- `POST /api/v1/intelligence/run`: same analysis, persisted to recommendation history.
- `GET /api/v1/intelligence/alerts`: alert-only response for dashboard badges and notification panels.
- `GET /api/v1/intelligence/reports/daily?session=morning|evening`: daily report sections for the UI.
- `GET /api/v1/intelligence/recommendations/history`: persisted recommendation trail.

## Market Data

Default enrichment uses no-key Yahoo Finance chart data for live price and one-year daily OHLCV history.

```env
MARKET_DATA_PROVIDER=yahoo
MARKET_DATA_TIMEOUT_SECONDS=6
MARKET_DATA_MAX_CONCURRENCY=8
```

The service maps NSE symbols to `.NS` and BSE symbols to `.BO`. If a symbol is not covered or the provider is slow, analysis still completes with a warning and lower conviction.

Optional settings are reserved for production-grade adapters:

```env
ALPHA_VANTAGE_API_KEY=
FINNHUB_API_KEY=
```

## Decision Inputs

The recommendation engine combines:

- Zerodha or CSV holdings, allocation, average price, last price and P&L.
- Technical signals from live OHLCV when available: RSI 14, MACD, signal line, EMA 20/50/100/200, ATR, trend, momentum, support and resistance.
- Conservative penalties when fundamentals, trusted news or historical transaction data are missing.
- Prior recommendation history for `whatChanged` explanations.

## Alerts

Generated alerts include:

- high-risk reduce or exit candidates
- oversized positions
- intraday drawdown above 3%
- sector concentration above 35%
- missing sector classification
- incomplete market-data coverage

All outputs are explainable analytics and must be reviewed by the user before any trade decision.
