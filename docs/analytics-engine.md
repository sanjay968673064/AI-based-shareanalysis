# Analytics Engine

The Analytics tab is a holdings-only business-intelligence engine. It does not scan unrelated market stocks and it does not execute trades.

## Daily Refresh

- The API starts a background refresh worker when the app starts.
- Once per UTC day, the worker refreshes company analytics and persists portfolio intelligence for every local user with holdings.
- Manual refresh is also available through `POST /api/v1/analytics/daily-refresh`.
- The company analytics response includes `nextRefreshAt`, `cachedForDate`, and `modelVersion`.

## Data Inputs

- Current holdings from the local portfolio database.
- Consensus market snapshots for live price and OHLCV enrichment. `MARKET_DATA_PROVIDER=multi` uses Yahoo Finance plus configured Alpha Vantage and Finnhub keys.
- Market data sanitization removes invalid prices, malformed OHLCV rows, impossible high/low relationships, and non-finite values before analytics sees the data.
- Consensus validation compares source prices and withholds live price replacement when configured sources disagree beyond `MARKET_DATA_CONSENSUS_PRICE_TOLERANCE_PCT`.
- Yahoo Finance chart data remains available as the no-key fallback for one-year price trend, volatility, and 52-week position.
- Yahoo Finance annual fundamentals time series for revenue, net income, debt, equity, cash, assets, liabilities, operating cash flow, free cash flow, and EPS.
- Yahoo Finance search/news for company profile and recent news signals.
- Fundamental and news data are still provider-limited and are scored conservatively when missing. They are not treated as multi-source verified yet.

## Scoring

Each holding receives:

- Balance sheet score
- Growth score
- Cash-flow score
- Valuation score
- Overall BI score
- Backend decision signal with action, confidence, conviction, risk flags, entry discipline, and exit guard

## Sanity Checks

The model reports portfolio-level checks for:

- Fundamental coverage
- Live price coverage
- News coverage
- Score bounds
- Provider warning load

Warnings reduce the data-quality score. Missing or incomplete data is treated conservatively.

## AI Analytics

- Gemini or OpenAI is optional and is configured from the app's `AI Config` button.
- Gemini is the default provider because it has a practical free tier for light usage.
- The API key is stored server-side in `app_settings`; the browser only receives provider/configured/masked status.
- AI is used as an explanation layer over the calculated Analytics output.
- The prompt sends holdings-only analytics data: scores, decision signals, sanity checks, financial metrics and provider warnings.
- The AI provider must not invent holdings, prices, ratios or news; it returns structured buy-focus, hold-focus, review-focus and risk-control lists.
- Gemini is the default AI provider. The recommended free-tier model for portfolio analysis is `gemini-3.5-flash`; `gemini-3.1-flash-lite` is available in AI Config as a faster/lightweight free-tier option.
- AI analysis uses a 75-second provider timeout. If the selected Gemini model fails or times out, the backend retries known free-tier fallback models before returning a safe warning.

## Important Limit

The system provides explainable analytics and decision support. It is not a SEBI-registered advisory engine, a guarantee of returns, or an automated trading system.
