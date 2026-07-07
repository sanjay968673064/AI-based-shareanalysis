import asyncio
from dataclasses import dataclass, field
from typing import Any

import httpx

from src.core.config import settings


@dataclass(frozen=True)
class ProviderState:
    available: bool
    notes: list[str]


@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    provider_symbol: str
    last_price: float | None = None
    previous_close: float | None = None
    closes: list[float] = field(default_factory=list)
    highs: list[float] = field(default_factory=list)
    lows: list[float] = field(default_factory=list)
    volumes: list[float] = field(default_factory=list)
    currency: str | None = None
    source: str = "unavailable"
    warnings: list[str] = field(default_factory=list)


class MarketDataProvider:
    def __init__(self) -> None:
        self._timeout = settings.market_data_timeout_seconds
        self._max_concurrency = max(1, settings.market_data_max_concurrency)
        self._cache: dict[str, MarketSnapshot] = {}

    async def state(self) -> ProviderState:
        provider = settings.market_data_provider.lower()
        if provider == "yahoo":
            return ProviderState(
                available=True,
                notes=[
                    "Yahoo Finance chart data is enabled for no-key live price and OHLCV enrichment.",
                    "Fundamental statements and trusted news providers are still optional and reduce conviction when absent.",
                ],
            )
        if provider == "alpha_vantage" and settings.alpha_vantage_api_key:
            return ProviderState(
                available=False,
                notes=["Alpha Vantage configuration is present, but the provider adapter is not enabled yet."],
            )
        if provider == "finnhub" and settings.finnhub_api_key:
            return ProviderState(
                available=False,
                notes=["Finnhub configuration is present, but the provider adapter is not enabled yet."],
            )
        return ProviderState(
            available=False,
            notes=[
                "External market data provider is not configured.",
                "Recommendations use Zerodha holdings, prices, P&L and conservative missing-data penalties.",
            ],
        )

    async def fetch_many(self, holdings: list[dict]) -> dict[str, MarketSnapshot]:
        provider = settings.market_data_provider.lower()
        if provider != "yahoo":
            return {
                holding["symbol"]: MarketSnapshot(
                    symbol=holding["symbol"],
                    provider_symbol=self._provider_symbol(holding),
                    warnings=[f"Market data provider '{provider}' is not available in this build."],
                )
                for holding in holdings
            }

        semaphore = asyncio.Semaphore(self._max_concurrency)

        async with httpx.AsyncClient(timeout=self._timeout, headers={"User-Agent": "ai-portfolio-advisor/1.0"}) as client:
            tasks = [self._fetch_yahoo_with_limit(client, semaphore, holding) for holding in holdings]
            snapshots = await asyncio.gather(*tasks)
        return {snapshot.symbol: snapshot for snapshot in snapshots}

    async def _fetch_yahoo_with_limit(
        self,
        client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        holding: dict,
    ) -> MarketSnapshot:
        symbol = holding["symbol"]
        provider_symbol = self._provider_symbol(holding)
        if provider_symbol in self._cache:
            return self._cache[provider_symbol]
        async with semaphore:
            snapshot = await self._fetch_yahoo(client, symbol, provider_symbol)
            self._cache[provider_symbol] = snapshot
            return snapshot

    async def _fetch_yahoo(self, client: httpx.AsyncClient, symbol: str, provider_symbol: str) -> MarketSnapshot:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{provider_symbol}"
        params = {"range": "1y", "interval": "1d"}
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
            return self._parse_yahoo(symbol, provider_symbol, payload)
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
            return MarketSnapshot(
                symbol=symbol,
                provider_symbol=provider_symbol,
                warnings=[f"Could not fetch live market data for {provider_symbol}: {exc.__class__.__name__}."],
            )

    def _parse_yahoo(self, symbol: str, provider_symbol: str, payload: dict[str, Any]) -> MarketSnapshot:
        chart = payload["chart"]
        errors = chart.get("error")
        if errors:
            return MarketSnapshot(
                symbol=symbol,
                provider_symbol=provider_symbol,
                warnings=[f"Yahoo Finance returned an error for {provider_symbol}."],
            )
        result = chart["result"][0]
        meta = result.get("meta", {})
        quote = result["indicators"]["quote"][0]
        closes = self._clean_series(quote.get("close", []))
        highs = self._clean_series(quote.get("high", []))
        lows = self._clean_series(quote.get("low", []))
        volumes = self._clean_series(quote.get("volume", []))
        last_price = self._as_float(meta.get("regularMarketPrice")) or (closes[-1] if closes else None)
        previous_close = self._as_float(meta.get("previousClose")) or self._as_float(meta.get("chartPreviousClose"))
        warnings = []
        if len(closes) < 30:
            warnings.append(f"Only {len(closes)} historical closes were available for {provider_symbol}.")
        return MarketSnapshot(
            symbol=symbol,
            provider_symbol=provider_symbol,
            last_price=last_price,
            previous_close=previous_close,
            closes=closes,
            highs=highs,
            lows=lows,
            volumes=volumes,
            currency=meta.get("currency"),
            source="yahoo",
            warnings=warnings,
        )

    def _provider_symbol(self, holding: dict) -> str:
        symbol = str(holding["symbol"]).strip().upper()
        if "." in symbol or symbol.startswith("^"):
            return symbol
        exchange = str(holding.get("exchange") or "NSE").strip().upper()
        if exchange == "BSE":
            return f"{symbol}.BO"
        return f"{symbol}.NS"

    def _clean_series(self, values: list[Any]) -> list[float]:
        return [float(value) for value in values if value is not None]

    def _as_float(self, value: Any) -> float | None:
        if value is None:
            return None
        return float(value)
