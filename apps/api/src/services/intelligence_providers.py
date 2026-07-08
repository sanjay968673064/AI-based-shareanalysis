import asyncio
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from statistics import median
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
        self._price_tolerance_pct = max(0.5, settings.market_data_consensus_price_tolerance_pct)

    async def state(self) -> ProviderState:
        sources = self._enabled_sources()
        if sources:
            keyed = [source for source in sources if source != "yahoo"]
            notes = [
                f"Market data consensus is enabled with {', '.join(sources)}.",
                "Live prices are sanitized and cross-checked before they replace broker prices.",
            ]
            if not keyed:
                notes.append("Add ALPHA_VANTAGE_API_KEY and/or FINNHUB_API_KEY to validate Yahoo against independent sources.")
            return ProviderState(available=True, notes=notes)
        provider = settings.market_data_provider.lower().strip()
        if provider in {"multi", "consensus"}:
            return ProviderState(
                available=False,
                notes=[
                    "No market data source is configured for consensus validation.",
                    "Yahoo is available without a key; Alpha Vantage and Finnhub need API keys.",
                ],
            )
        return ProviderState(
            available=False,
            notes=[
                f"Market data provider '{provider}' is not configured or lacks the required API key.",
                "Recommendations use Zerodha holdings, prices, P&L and conservative missing-data penalties.",
            ],
        )

    async def fetch_many(self, holdings: list[dict]) -> dict[str, MarketSnapshot]:
        sources = self._enabled_sources()
        provider = settings.market_data_provider.lower().strip()
        if not sources:
            return {
                holding["symbol"]: MarketSnapshot(
                    symbol=holding["symbol"],
                    provider_symbol=self._yahoo_symbol(holding),
                    warnings=[f"Market data provider '{provider}' is not available or configured in this build."],
                )
                for holding in holdings
            }

        semaphore = asyncio.Semaphore(self._max_concurrency)

        async with httpx.AsyncClient(timeout=self._timeout, headers={"User-Agent": "ai-portfolio-advisor/1.0"}) as client:
            tasks = [self._fetch_consensus_with_limit(client, semaphore, holding, sources) for holding in holdings]
            snapshots = await asyncio.gather(*tasks)
        return {snapshot.symbol: snapshot for snapshot in snapshots}

    async def _fetch_consensus_with_limit(
        self,
        client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        holding: dict,
        sources: list[str],
    ) -> MarketSnapshot:
        symbol = holding["symbol"]
        cache_key = f"{symbol}:{holding.get('exchange', 'NSE')}:{','.join(sources)}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        async with semaphore:
            fetches = []
            if "yahoo" in sources:
                fetches.append(self._fetch_yahoo(client, holding))
            if "alpha_vantage" in sources:
                fetches.append(self._fetch_alpha_vantage(client, holding))
            if "finnhub" in sources:
                fetches.append(self._fetch_finnhub(client, holding))
            source_snapshots = await asyncio.gather(*fetches)
            snapshot = self._merge_snapshots(holding, source_snapshots, sources)
            self._cache[cache_key] = snapshot
            return snapshot

    async def _fetch_yahoo(self, client: httpx.AsyncClient, holding: dict) -> MarketSnapshot:
        symbol = holding["symbol"]
        provider_symbol = self._yahoo_symbol(holding)
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

    async def _fetch_alpha_vantage(self, client: httpx.AsyncClient, holding: dict) -> MarketSnapshot:
        symbol = holding["symbol"]
        provider_symbol = self._alpha_vantage_symbol(holding)
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": provider_symbol,
            "outputsize": "compact",
            "apikey": settings.alpha_vantage_api_key,
        }
        try:
            response = await client.get("https://www.alphavantage.co/query", params=params)
            response.raise_for_status()
            return self._parse_alpha_vantage(symbol, provider_symbol, response.json())
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            return MarketSnapshot(
                symbol=symbol,
                provider_symbol=provider_symbol,
                source="alpha_vantage",
                warnings=[f"Could not fetch Alpha Vantage daily data for {provider_symbol}: {exc.__class__.__name__}."],
            )

    async def _fetch_finnhub(self, client: httpx.AsyncClient, holding: dict) -> MarketSnapshot:
        symbol = holding["symbol"]
        provider_symbol = self._finnhub_symbol(holding)
        to_ts = int(datetime.now(UTC).timestamp())
        from_ts = int((datetime.now(UTC) - timedelta(days=390)).timestamp())
        try:
            quote_response, candle_response = await asyncio.gather(
                client.get(
                    "https://finnhub.io/api/v1/quote",
                    params={"symbol": provider_symbol, "token": settings.finnhub_api_key},
                ),
                client.get(
                    "https://finnhub.io/api/v1/stock/candle",
                    params={
                        "symbol": provider_symbol,
                        "resolution": "D",
                        "from": from_ts,
                        "to": to_ts,
                        "token": settings.finnhub_api_key,
                    },
                ),
            )
            quote_response.raise_for_status()
            candle_response.raise_for_status()
            return self._parse_finnhub(symbol, provider_symbol, quote_response.json(), candle_response.json())
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            return MarketSnapshot(
                symbol=symbol,
                provider_symbol=provider_symbol,
                source="finnhub",
                warnings=[f"Could not fetch Finnhub quote/candle data for {provider_symbol}: {exc.__class__.__name__}."],
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
        closes, highs, lows, volumes = self._clean_ohlcv_rows(
            quote.get("close", []),
            quote.get("high", []),
            quote.get("low", []),
            quote.get("volume", []),
        )
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

    def _parse_alpha_vantage(self, symbol: str, provider_symbol: str, payload: dict[str, Any]) -> MarketSnapshot:
        warning = payload.get("Error Message") or payload.get("Note") or payload.get("Information")
        if warning:
            return MarketSnapshot(
                symbol=symbol,
                provider_symbol=provider_symbol,
                source="alpha_vantage",
                warnings=[f"Alpha Vantage did not return usable daily data for {provider_symbol}: {str(warning)[:140]}"],
            )
        rows = payload.get("Time Series (Daily)")
        if not isinstance(rows, dict):
            return MarketSnapshot(
                symbol=symbol,
                provider_symbol=provider_symbol,
                source="alpha_vantage",
                warnings=[f"Alpha Vantage daily data was missing for {provider_symbol}."],
            )
        ordered = [rows[key] for key in sorted(rows.keys())]
        closes, highs, lows, volumes = self._clean_ohlcv_rows(
            [row.get("4. close") for row in ordered],
            [row.get("2. high") for row in ordered],
            [row.get("3. low") for row in ordered],
            [row.get("5. volume") for row in ordered],
        )
        previous_close = closes[-2] if len(closes) >= 2 else None
        warnings = []
        if len(closes) < 30:
            warnings.append(f"Only {len(closes)} Alpha Vantage closes were available for {provider_symbol}.")
        return MarketSnapshot(
            symbol=symbol,
            provider_symbol=provider_symbol,
            last_price=closes[-1] if closes else None,
            previous_close=previous_close,
            closes=closes,
            highs=highs,
            lows=lows,
            volumes=volumes,
            source="alpha_vantage",
            warnings=warnings,
        )

    def _parse_finnhub(
        self,
        symbol: str,
        provider_symbol: str,
        quote_payload: dict[str, Any],
        candle_payload: dict[str, Any],
    ) -> MarketSnapshot:
        warnings = []
        if candle_payload.get("s") not in {"ok", "no_data"}:
            warnings.append(f"Finnhub candle data returned status {candle_payload.get('s')} for {provider_symbol}.")
        closes, highs, lows, volumes = self._clean_ohlcv_rows(
            candle_payload.get("c", []),
            candle_payload.get("h", []),
            candle_payload.get("l", []),
            candle_payload.get("v", []),
        )
        last_price = self._as_float(quote_payload.get("c")) or (closes[-1] if closes else None)
        previous_close = self._as_float(quote_payload.get("pc")) or (closes[-2] if len(closes) >= 2 else None)
        if len(closes) < 30:
            warnings.append(f"Only {len(closes)} Finnhub closes were available for {provider_symbol}.")
        return MarketSnapshot(
            symbol=symbol,
            provider_symbol=provider_symbol,
            last_price=last_price,
            previous_close=previous_close,
            closes=closes,
            highs=highs,
            lows=lows,
            volumes=volumes,
            source="finnhub",
            warnings=warnings,
        )

    def _merge_snapshots(
        self,
        holding: dict,
        source_snapshots: list[MarketSnapshot],
        requested_sources: list[str],
    ) -> MarketSnapshot:
        symbol = holding["symbol"]
        provider_symbol = self._yahoo_symbol(holding)
        usable = [snapshot for snapshot in source_snapshots if snapshot.last_price is not None or snapshot.closes]
        warnings = [
            warning
            for snapshot in source_snapshots
            for warning in snapshot.warnings
        ]
        source_names = [snapshot.source for snapshot in usable if snapshot.source != "unavailable"]
        if len(source_names) < 2 and len(requested_sources) > 1:
            warnings.append(
                f"Consensus for {symbol} used {', '.join(source_names) or 'no source'}; "
                f"{len(requested_sources) - len(source_names)} configured source(s) returned no usable data."
            )

        best_history = max(usable, key=lambda item: len(item.closes), default=None)
        last_price = self._consensus_price(
            symbol=symbol,
            label="last price",
            values=[(snapshot.source, snapshot.last_price) for snapshot in usable],
            warnings=warnings,
        )
        previous_close = self._consensus_price(
            symbol=symbol,
            label="previous close",
            values=[(snapshot.source, snapshot.previous_close) for snapshot in usable],
            warnings=warnings,
            required=False,
        )
        if best_history is None:
            return MarketSnapshot(
                symbol=symbol,
                provider_symbol=provider_symbol,
                source="consensus:none",
                warnings=warnings or [f"No configured market data source returned usable data for {symbol}."],
            )
        return MarketSnapshot(
            symbol=symbol,
            provider_symbol=provider_symbol,
            last_price=last_price,
            previous_close=previous_close,
            closes=best_history.closes,
            highs=best_history.highs,
            lows=best_history.lows,
            volumes=best_history.volumes,
            currency=best_history.currency,
            source=f"consensus:{'+'.join(source_names)}",
            warnings=warnings,
        )

    def _consensus_price(
        self,
        symbol: str,
        label: str,
        values: list[tuple[str, float | None]],
        warnings: list[str],
        required: bool = True,
    ) -> float | None:
        clean = [(source, value) for source, value in values if value is not None and self._valid_price(value)]
        if not clean:
            if required:
                warnings.append(f"No valid {label} survived sanitization for {symbol}.")
            return None
        if len(clean) == 1:
            return clean[0][1]
        center = median(value for _, value in clean)
        if center <= 0:
            warnings.append(f"Consensus {label} for {symbol} was invalid after sanitization.")
            return None
        outliers = [
            f"{source}={value:.2f}"
            for source, value in clean
            if abs(value - center) / center * 100 > self._price_tolerance_pct
        ]
        if outliers:
            warnings.append(
                f"Rejected consensus {label} for {symbol}: sources differ by more than "
                f"{self._price_tolerance_pct:.1f}% ({', '.join(outliers)})."
            )
            return None
        return float(center)

    def _enabled_sources(self) -> list[str]:
        provider = settings.market_data_provider.lower().strip()
        if provider in {"multi", "consensus"}:
            sources = ["yahoo"]
            if settings.alpha_vantage_api_key:
                sources.append("alpha_vantage")
            if settings.finnhub_api_key:
                sources.append("finnhub")
            return sources
        if provider == "yahoo":
            return ["yahoo"]
        if provider == "alpha_vantage" and settings.alpha_vantage_api_key:
            return ["alpha_vantage"]
        if provider == "finnhub" and settings.finnhub_api_key:
            return ["finnhub"]
        return []

    def _yahoo_symbol(self, holding: dict) -> str:
        symbol = str(holding["symbol"]).strip().upper()
        if "." in symbol or symbol.startswith("^"):
            return symbol
        exchange = str(holding.get("exchange") or "NSE").strip().upper()
        if exchange == "BSE":
            return f"{symbol}.BO"
        return f"{symbol}.NS"

    def _alpha_vantage_symbol(self, holding: dict) -> str:
        symbol = str(holding["symbol"]).strip().upper()
        if "." in symbol or ":" in symbol:
            return symbol
        exchange = str(holding.get("exchange") or "NSE").strip().upper()
        suffix = "BSE" if exchange == "BSE" else "NSE"
        return f"{symbol}.{suffix}"

    def _finnhub_symbol(self, holding: dict) -> str:
        symbol = str(holding["symbol"]).strip().upper()
        if ":" in symbol:
            return symbol
        exchange = str(holding.get("exchange") or "NSE").strip().upper()
        prefix = "BSE" if exchange == "BSE" else "NSE"
        return f"{prefix}:{symbol}"

    def _clean_ohlcv_rows(
        self,
        closes_raw: list[Any],
        highs_raw: list[Any],
        lows_raw: list[Any],
        volumes_raw: list[Any],
    ) -> tuple[list[float], list[float], list[float], list[float]]:
        closes: list[float] = []
        highs: list[float] = []
        lows: list[float] = []
        volumes: list[float] = []
        max_length = max(len(closes_raw), len(highs_raw), len(lows_raw), len(volumes_raw), 0)
        for index in range(max_length):
            close = self._as_float(closes_raw[index]) if index < len(closes_raw) else None
            high = self._as_float(highs_raw[index]) if index < len(highs_raw) else None
            low = self._as_float(lows_raw[index]) if index < len(lows_raw) else None
            volume = self._as_float(volumes_raw[index]) if index < len(volumes_raw) else 0.0
            if close is None or high is None or low is None:
                continue
            if not self._valid_price(close) or not self._valid_price(high) or not self._valid_price(low):
                continue
            if high < low or close > high * 1.1 or close < low * 0.9:
                continue
            closes.append(close)
            highs.append(high)
            lows.append(low)
            volumes.append(max(0.0, volume or 0.0))
        return closes, highs, lows, volumes

    def _as_float(self, value: Any) -> float | None:
        if value is None:
            return None
        try:
            output = float(value)
        except (TypeError, ValueError):
            return None
        return output if math.isfinite(output) else None

    def _valid_price(self, value: float) -> bool:
        return math.isfinite(value) and 0 < value < 1_000_000_000
