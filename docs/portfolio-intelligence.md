# Portfolio Intelligence

The backend analysis engine produces advisory-only portfolio decisions. It never places trades.

## Endpoints

- `GET /api/v1/intelligence/analysis`: full portfolio metrics, buy/sell/hold-style recommendations, optimization, alerts and data-quality warnings.
- `POST /api/v1/intelligence/run`: same analysis, persisted to recommendation history.
- `GET /api/v1/intelligence/alerts`: alert-only response for dashboard badges and notification panels.
- `GET /api/v1/intelligence/reports/daily?session=morning|evening`: daily report sections for the UI.
- `GET /api/v1/intelligence/recommendations/history`: persisted recommendation trail.

## Market Data

Default enrichment uses consensus mode. Yahoo Finance remains the no-key fallback, and Alpha Vantage/Finnhub join the validation set when keys are configured.

```env
MARKET_DATA_PROVIDER=multi
MARKET_DATA_TIMEOUT_SECONDS=6
MARKET_DATA_MAX_CONCURRENCY=8
MARKET_DATA_CONSENSUS_PRICE_TOLERANCE_PCT=3
```

The service sanitizes OHLCV rows, rejects invalid prices, and withholds live price replacement when source prices disagree beyond the consensus tolerance. If a symbol is not covered or a provider is slow, analysis still completes with a warning and lower conviction.

Optional keys activate independent validation sources:

```env
ALPHA_VANTAGE_API_KEY=
FINNHUB_API_KEY=
```

Yahoo symbols map NSE to `.NS` and BSE to `.BO`; Alpha Vantage uses `.NSE`/`.BSE`; Finnhub uses `NSE:`/`BSE:` prefixes.

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
