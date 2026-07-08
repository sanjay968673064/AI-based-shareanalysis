import asyncio
import math
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from src.core.config import settings
from src.core.security import token_cipher
from src.domain.auth import UserContext
from src.repositories.app_settings import AppSettingsRepository
from src.repositories.portfolio import PortfolioRepository
from src.schemas.analytics import (
    AnalyticsMetricRead,
    AnalyticsSanityCheckRead,
    CompanyAnalyticsRead,
    CompanyNewsRead,
    DecisionSignalRead,
    PortfolioAnalyticsRead,
)
from src.services.intelligence_providers import MarketDataProvider, MarketSnapshot


_CACHE: dict[str, PortfolioAnalyticsRead] = {}
MODEL_VERSION = "fundamental-signal-engine-2026.07"
MARKET_TZ = ZoneInfo("Asia/Kolkata")
SCORING_WEIGHTS = {
    "fundamental": 0.40,
    "technical": 0.20,
    "valuation": 0.10,
    "risk": 0.10,
    "governance": 0.05,
    "sector": 0.05,
    "news": 0.05,
    "sentiment": 0.05,
}


class CompanyAnalyticsService:
    def __init__(
        self,
        portfolio_repo: PortfolioRepository,
        settings_repo: AppSettingsRepository | None = None,
    ) -> None:
        self._portfolio_repo = portfolio_repo
        self._settings_repo = settings_repo
        self._timeout = max(6.0, settings.market_data_timeout_seconds)
        self._max_concurrency = max(1, settings.market_data_max_concurrency)
        self._market_data = MarketDataProvider()

    async def analyze(self, context: UserContext, force_refresh: bool = False) -> PortfolioAnalyticsRead:
        analysis_date = self._analysis_date()
        holdings = await self._portfolio_repo.list_holdings(context)
        holdings_signature = self._holdings_signature(holdings)
        cache_key = f"{context.tenant_id}:{context.user_id}:{analysis_date.isoformat()}:{holdings_signature}"
        if not force_refresh and cache_key in _CACHE:
            return _CACHE[cache_key]

        semaphore = asyncio.Semaphore(self._max_concurrency)
        headers = {"User-Agent": "Mozilla/5.0 ai-portfolio-advisor/1.0"}
        async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
            companies = await asyncio.gather(
                *[self._analyze_company(client, semaphore, holding) for holding in holdings]
            )
        market_snapshots = await self._market_data.fetch_many(holdings)
        companies = [
            self._apply_verified_market_snapshot(company, market_snapshots.get(company.symbol))
            for company in companies
        ]

        warnings = [
            note
            for company in companies
            for note in company.source_notes
            if note.lower().startswith(("could not", "missing", "limited", "fundamental", "consensus", "rejected", "withheld"))
        ]
        sanity_checks = self._sanity_checks(companies, warnings)
        quality = self._quality_score(companies, sanity_checks)
        result = PortfolioAnalyticsRead(
            generated_at=datetime.now(UTC),
            cached_for_date=analysis_date,
            next_refresh_at=self._next_refresh_at(),
            model_version=MODEL_VERSION,
            data_quality_score=quality,
            summary=self._portfolio_summary(companies, quality),
            companies=sorted(companies, key=lambda item: item.overall_score, reverse=True),
            decision_signals=self._decision_signals(companies),
            sanity_checks=sanity_checks,
            warnings=warnings[:8],
        )
        _CACHE[cache_key] = result
        await self._store_latest(context, result)
        return result

    async def _store_latest(self, context: UserContext, result: PortfolioAnalyticsRead) -> None:
        if self._settings_repo is None:
            return
        await self._settings_repo.upsert(
            context,
            "latest_portfolio_analytics_snapshot",
            token_cipher.encrypt(result.model_dump_json(by_alias=True)),
        )

    async def _analyze_company(
        self,
        client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        holding: dict,
    ) -> CompanyAnalyticsRead:
        async with semaphore:
            provider_symbol = self._provider_symbol(holding)
            search, chart, fundamentals = await asyncio.gather(
                self._fetch_search(client, provider_symbol),
                self._fetch_chart(client, provider_symbol),
                self._fetch_fundamentals(client, provider_symbol),
            )
        return self._build_company(holding, provider_symbol, search, chart, fundamentals)

    async def _fetch_search(self, client: httpx.AsyncClient, provider_symbol: str) -> dict:
        try:
            response = await client.get(
                "https://query1.finance.yahoo.com/v1/finance/search",
                params={"q": provider_symbol, "quotesCount": 1, "newsCount": 6},
            )
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError):
            return {"quotes": [], "news": [], "warning": f"Could not fetch company profile/news for {provider_symbol}."}

    async def _fetch_chart(self, client: httpx.AsyncClient, provider_symbol: str) -> dict:
        try:
            response = await client.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{provider_symbol}",
                params={"range": "1y", "interval": "1d"},
            )
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError):
            return {"warning": f"Could not fetch live chart data for {provider_symbol}."}

    async def _fetch_fundamentals(self, client: httpx.AsyncClient, provider_symbol: str) -> dict:
        metric_types = ",".join(
            [
                "annualTotalAssets",
                "annualTotalLiabilitiesNetMinorityInterest",
                "annualTotalDebt",
                "annualStockholdersEquity",
                "annualCashAndCashEquivalents",
                "annualTotalRevenue",
                "annualNetIncome",
                "annualOperatingCashFlow",
                "annualFreeCashFlow",
                "annualBasicEPS",
            ]
        )
        try:
            response = await client.get(
                f"https://query1.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/{provider_symbol}",
                params={"type": metric_types, "period1": 1483228800, "period2": 1893456000},
            )
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError):
            return {"warning": f"Could not fetch balance-sheet time-series for {provider_symbol}."}

    def _build_company(
        self,
        holding: dict,
        provider_symbol: str,
        search: dict,
        chart: dict,
        fundamentals: dict,
    ) -> CompanyAnalyticsRead:
        quote = (search.get("quotes") or [{}])[0] if isinstance(search.get("quotes"), list) else {}
        meta = self._chart_meta(chart)
        series = self._series_map(fundamentals)
        latest = {key: values[-1] for key, values in series.items() if values}
        previous = {key: values[-2] for key, values in series.items() if len(values) >= 2}

        revenue_growth = self._growth(previous.get("annualTotalRevenue"), latest.get("annualTotalRevenue"))
        net_income_growth = self._growth(previous.get("annualNetIncome"), latest.get("annualNetIncome"))
        debt_to_equity = self._ratio(latest.get("annualTotalDebt"), latest.get("annualStockholdersEquity"))
        cash_to_debt = self._ratio(latest.get("annualCashAndCashEquivalents"), latest.get("annualTotalDebt"))
        fcf_margin = self._ratio(latest.get("annualFreeCashFlow"), latest.get("annualTotalRevenue"))
        operating_cashflow_to_debt = self._ratio(
            latest.get("annualOperatingCashFlow"), latest.get("annualTotalDebt")
        )
        roe = self._ratio(latest.get("annualNetIncome"), latest.get("annualStockholdersEquity"))
        liabilities_to_assets = self._ratio(
            latest.get("annualTotalLiabilitiesNetMinorityInterest"), latest.get("annualTotalAssets")
        )
        eps_growth = self._growth(previous.get("annualBasicEPS"), latest.get("annualBasicEPS"))
        price_position = self._price_position(meta)
        one_year_price_return = self._one_year_price_return(chart)
        realized_volatility = self._realized_volatility(chart)

        balance_score = self._score_balance_sheet(debt_to_equity, cash_to_debt, liabilities_to_assets)
        growth_score = self._score_growth(revenue_growth, net_income_growth, eps_growth)
        cash_flow_score = self._score_cash_flow(
            fcf_margin, latest.get("annualFreeCashFlow"), operating_cashflow_to_debt
        )
        valuation_score = self._score_valuation(price_position, one_year_price_return)
        fundamental_score = self._score_fundamental(balance_score, growth_score, cash_flow_score, roe)
        technical_score = self._score_technical(price_position, one_year_price_return, realized_volatility)
        risk_score = self._score_risk(realized_volatility, debt_to_equity, liabilities_to_assets)
        governance_score = self._score_governance(quote)
        sector_score = self._score_sector(quote.get("sector") or holding.get("sector"), one_year_price_return)
        news_items = self._news(search)
        news_score = self._score_news(news_items)
        sentiment_score = self._score_sentiment(news_items)
        overall = self._weighted_final_score(
            fundamental=fundamental_score,
            technical=technical_score,
            valuation=valuation_score,
            risk=risk_score,
            governance=governance_score,
            sector=sector_score,
            news=news_score,
            sentiment=sentiment_score,
        )
        recommendation = self._recommendation(overall, risk_score)
        last_price = self._as_float(meta.get("regularMarketPrice"))
        valuation_profile = self._valuation_profile(last_price, price_position, valuation_score, overall)

        strengths, concerns = self._strengths_and_concerns(
            revenue_growth=revenue_growth,
            net_income_growth=net_income_growth,
            debt_to_equity=debt_to_equity,
            cash_to_debt=cash_to_debt,
            fcf_margin=fcf_margin,
            price_position=price_position,
        )
        source_notes = [
            f"Profile/news source: Yahoo Finance search for {provider_symbol}.",
            f"Price source: Yahoo Finance chart for {provider_symbol}.",
            f"Fundamentals source: Yahoo Finance annual fundamentals time-series for {provider_symbol}.",
            f"Analytics model: {MODEL_VERSION}.",
        ]
        for payload in (search, chart, fundamentals):
            warning = payload.get("warning") if isinstance(payload, dict) else None
            if warning:
                source_notes.append(warning)
        if not series:
            source_notes.append("Fundamental time-series was missing or empty; scores use conservative defaults.")

        return CompanyAnalyticsRead(
            symbol=holding["symbol"],
            company_name=meta.get("longName") or quote.get("longname") or holding["company_name"],
            sector=quote.get("sector") or holding.get("sector"),
            industry=quote.get("industry"),
            currency=meta.get("currency"),
            last_price=last_price,
            day_change_pct=self._day_change_pct(meta),
            fifty_two_week_low=self._as_float(meta.get("fiftyTwoWeekLow")),
            fifty_two_week_high=self._as_float(meta.get("fiftyTwoWeekHigh")),
            business_summary=self._business_summary(quote, meta),
            overall_score=int(overall),
            balance_sheet_score=balance_score,
            growth_score=growth_score,
            cash_flow_score=cash_flow_score,
            valuation_score=valuation_score,
            fundamental_score=fundamental_score,
            technical_score=technical_score,
            governance_score=governance_score,
            risk_score=risk_score,
            sector_score=sector_score,
            news_score=news_score,
            sentiment_score=sentiment_score,
            final_score=int(overall),
            confidence=self._confidence(overall, risk_score, news_score, sentiment_score, series),
            investment_horizon=self._investment_horizon(recommendation, technical_score, risk_score),
            intrinsic_value=valuation_profile["intrinsic_value"],
            fair_value=valuation_profile["fair_value"],
            expected_upside=valuation_profile["expected_upside"],
            stop_loss=valuation_profile["stop_loss"],
            target1=valuation_profile["target1"],
            target2=valuation_profile["target2"],
            target3=valuation_profile["target3"],
            recommendation=recommendation,
            planning=self._planning(recommendation, holding["symbol"], strengths, concerns),
            strengths=strengths,
            concerns=concerns,
            weaknesses=concerns,
            risks=self._risk_factors(risk_score, valuation_score, realized_volatility, concerns),
            catalysts=self._catalysts(news_items, strengths),
            explanation=self._explanation(
                symbol=holding["symbol"],
                final_score=overall,
                recommendation=recommendation,
                fundamental_score=fundamental_score,
                technical_score=technical_score,
                valuation_score=valuation_score,
                risk_score=risk_score,
                governance_score=governance_score,
                sector_score=sector_score,
                news_score=news_score,
                sentiment_score=sentiment_score,
            ),
            scoring_weights=SCORING_WEIGHTS,
            financials=[
                self._metric("Revenue growth", revenue_growth, percent=True),
                self._metric("Net income growth", net_income_growth, percent=True),
                self._metric("Debt / equity", debt_to_equity),
                self._metric("Cash / debt", cash_to_debt),
                self._metric("FCF margin", fcf_margin, percent=True),
                self._metric("ROE", roe, percent=True),
                self._metric("Liabilities / assets", liabilities_to_assets),
                self._metric("Operating cash flow / debt", operating_cashflow_to_debt),
                self._metric("Price in 52W range", price_position, percent=True),
                self._metric("1Y price trend", one_year_price_return, percent=True),
                self._metric("Realized volatility", realized_volatility, percent=True),
            ],
            news=news_items,
            source_notes=source_notes,
        )

    def _apply_verified_market_snapshot(
        self,
        company: CompanyAnalyticsRead,
        snapshot: MarketSnapshot | None,
    ) -> CompanyAnalyticsRead:
        if snapshot is None:
            return company.model_copy(
                update={
                    "last_price": None,
                    "day_change_pct": None,
                    "source_notes": [
                        *company.source_notes,
                        "Withheld live price: no consensus market snapshot was available.",
                    ],
                }
            )
        source_notes = [
            *company.source_notes,
            f"Validated market snapshot source: {snapshot.source}.",
            *snapshot.warnings,
        ]
        if snapshot.last_price is None:
            return company.model_copy(
                update={
                    "last_price": None,
                    "day_change_pct": None,
                    "source_notes": [
                        *source_notes,
                        "Withheld live price: market data sources did not pass consensus validation.",
                    ],
                }
            )
        day_change_pct = None
        if snapshot.previous_close and snapshot.previous_close > 0:
            day_change_pct = (snapshot.last_price - snapshot.previous_close) / snapshot.previous_close * 100
        return company.model_copy(
            update={
                "last_price": snapshot.last_price,
                "day_change_pct": day_change_pct,
                "source_notes": source_notes,
            }
        )

    def _provider_symbol(self, holding: dict) -> str:
        symbol = str(holding["symbol"]).strip().upper()
        if "." in symbol or symbol.startswith("^"):
            return symbol
        exchange = str(holding.get("exchange") or "NSE").strip().upper()
        return f"{symbol}.BO" if exchange == "BSE" else f"{symbol}.NS"

    def _chart_meta(self, chart: dict) -> dict:
        try:
            return chart["chart"]["result"][0].get("meta", {})
        except (KeyError, IndexError, TypeError):
            return {}

    def _series_map(self, fundamentals: dict) -> dict[str, list[float]]:
        items = fundamentals.get("timeseries", {}).get("result", []) if isinstance(fundamentals, dict) else []
        output: dict[str, list[float]] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            metric_type = (item.get("meta", {}).get("type") or [None])[0]
            if not metric_type:
                continue
            values = []
            rows = item.get(metric_type, [])
            ordered_rows = sorted(rows, key=lambda row: row.get("asOfDate") or "")
            for row in ordered_rows:
                raw = row.get("reportedValue", {}).get("raw") if isinstance(row, dict) else None
                value = self._clean_statement_value(metric_type, raw)
                if value is not None:
                    values.append(value)
            output[metric_type] = values
        return output

    def _news(self, search: dict) -> list[CompanyNewsRead]:
        output = []
        for item in (search.get("news") or [])[:5]:
            provider_publish_time = item.get("providerPublishTime")
            output.append(
                CompanyNewsRead(
                    title=item.get("title") or "Untitled market update",
                    publisher=item.get("publisher"),
                    link=item.get("link"),
                    published_at=datetime.fromtimestamp(provider_publish_time, UTC)
                    if provider_publish_time
                    else None,
                )
            )
        return output

    def _metric(self, label: str, value: float | None, percent: bool = False) -> AnalyticsMetricRead:
        if value is None:
            return AnalyticsMetricRead(label=label, value="N/A", detail="Not available from provider", tone="neutral")
        display = f"{value * 100:.1f}%" if percent else f"{value:.2f}"
        tone = "neutral"
        if label in {"Revenue growth", "Net income growth", "FCF margin", "Cash / debt"}:
            tone = "good" if value > 0.08 else "watch" if value >= 0 else "bad"
        if label in {"ROE", "Operating cash flow / debt"}:
            tone = "good" if value > 0.12 else "watch" if value >= 0.04 else "bad"
        if label == "Debt / equity":
            tone = "good" if value < 0.5 else "watch" if value < 1.2 else "bad"
        if label == "Liabilities / assets":
            tone = "good" if value < 0.45 else "watch" if value < 0.7 else "bad"
        if label == "Price in 52W range":
            tone = "good" if value < 0.7 else "watch" if value < 0.88 else "bad"
        if label == "1Y price trend":
            tone = "good" if value > 0.08 else "watch" if value >= -0.08 else "bad"
        if label == "Realized volatility":
            tone = "good" if value < 0.28 else "watch" if value < 0.45 else "bad"
        return AnalyticsMetricRead(label=label, value=display, tone=tone)

    def _portfolio_summary(self, companies: list[CompanyAnalyticsRead], quality: int) -> str:
        if not companies:
            return "No holdings are available for company analytics."
        strong = sum(1 for company in companies if company.overall_score >= 72)
        weak = sum(1 for company in companies if company.overall_score < 50)
        return (
            f"Daily business-intelligence scan completed for {len(companies)} companies. "
            f"{strong} look fundamentally strong, {weak} need closer review. Data quality is {quality}/100."
        )

    def _quality_score(
        self,
        companies: list[CompanyAnalyticsRead],
        sanity_checks: list[AnalyticsSanityCheckRead],
    ) -> int:
        if not companies:
            return 25
        coverage = (
            sum(
                1
                for company in companies
                if sum(1 for metric in company.financials if metric.value != "N/A") >= 7
            )
            / len(companies)
        )
        news = sum(1 for company in companies if company.news) / len(companies)
        live_price = sum(1 for company in companies if company.last_price is not None) / len(companies)
        failures = sum(1 for check in sanity_checks if check.status == "fail")
        watches = sum(1 for check in sanity_checks if check.status == "watch")
        return int(max(15, min(95, 25 + coverage * 40 + live_price * 18 + news * 12 - failures * 12 - watches * 4)))

    def _business_summary(self, quote: dict, meta: dict) -> str:
        sector = quote.get("sectorDisp") or quote.get("sector")
        industry = quote.get("industryDisp") or quote.get("industry")
        name = meta.get("longName") or quote.get("longname") or quote.get("shortname") or "The company"
        if sector or industry:
            return f"{name} operates in {sector or 'an unclassified sector'} with industry exposure to {industry or 'not available'}."
        return f"{name} profile details are limited from the current provider response."

    def _strengths_and_concerns(
        self,
        revenue_growth: float | None,
        net_income_growth: float | None,
        debt_to_equity: float | None,
        cash_to_debt: float | None,
        fcf_margin: float | None,
        price_position: float | None,
    ) -> tuple[list[str], list[str]]:
        strengths: list[str] = []
        concerns: list[str] = []
        self._push_signal(strengths, concerns, revenue_growth, 0.08, "Revenue is growing year over year.", "Revenue growth is weak or negative.")
        self._push_signal(strengths, concerns, net_income_growth, 0.08, "Profit growth supports earnings quality.", "Net income growth is weak or negative.")
        if debt_to_equity is not None:
            (strengths if debt_to_equity < 0.5 else concerns).append(
                "Debt load is conservative versus equity." if debt_to_equity < 0.5 else "Debt load needs balance-sheet review."
            )
        if cash_to_debt is not None and cash_to_debt > 0.5:
            strengths.append("Cash balance provides debt coverage flexibility.")
        if fcf_margin is not None:
            (strengths if fcf_margin > 0.08 else concerns).append(
                "Free cash flow conversion is healthy." if fcf_margin > 0.08 else "Free cash flow conversion is thin."
            )
        if price_position is not None and price_position > 0.88:
            concerns.append("Price is near the upper end of its 52-week range; entry discipline matters.")
        return strengths[:5] or ["No strong fundamental strength detected."], concerns[:5] or ["No major provider-derived concern detected."]

    def _push_signal(
        self,
        strengths: list[str],
        concerns: list[str],
        value: float | None,
        threshold: float,
        positive: str,
        negative: str,
    ) -> None:
        if value is None:
            concerns.append("Growth data is missing from the provider response.")
        elif value >= threshold:
            strengths.append(positive)
        else:
            concerns.append(negative)

    def _planning(self, recommendation: str, symbol: str, strengths: list[str], concerns: list[str]) -> str:
        if recommendation in {"Strong Conviction Buy", "Strong Buy", "Buy", "Accumulate"}:
            return f"For {symbol}, plan staged accumulation only on valuation comfort and stable market trend; keep position sizing below the portfolio risk band."
        if recommendation == "Hold":
            return f"For {symbol}, maintain exposure and review after the next earnings/news trigger; add only if strengths remain intact."
        if recommendation == "Reduce":
            return f"For {symbol}, avoid fresh buying and consider reducing oversized exposure if concerns persist."
        return f"For {symbol}, avoid fresh buying until concerns improve; prepare a trim or thesis-review plan if weakness persists."

    def _score_fundamental(
        self,
        balance_score: int,
        growth_score: int,
        cash_flow_score: int,
        roe: float | None,
    ) -> int:
        score = round(balance_score * 0.30 + growth_score * 0.30 + cash_flow_score * 0.30 + 50 * 0.10)
        if roe is not None:
            score += 8 if roe >= 0.18 else 3 if roe >= 0.10 else -8 if roe < 0 else 0
        return int(max(0, min(100, score)))

    def _score_technical(
        self,
        price_position: float | None,
        one_year_price_return: float | None,
        realized_volatility: float | None,
    ) -> int:
        score = 50
        if one_year_price_return is None:
            score -= 8
        elif one_year_price_return > 0.25:
            score += 24
        elif one_year_price_return > 0.08:
            score += 12
        elif one_year_price_return < -0.18:
            score -= 18
        if price_position is not None:
            score += 10 if 0.35 <= price_position <= 0.82 else -8 if price_position > 0.92 else 2
        if realized_volatility is not None and realized_volatility > 0.55:
            score -= 12
        return int(max(0, min(100, score)))

    def _score_risk(
        self,
        realized_volatility: float | None,
        debt_to_equity: float | None,
        liabilities_to_assets: float | None,
    ) -> int:
        score = 68
        if realized_volatility is None:
            score -= 8
        elif realized_volatility > 0.65:
            score -= 25
        elif realized_volatility > 0.42:
            score -= 10
        elif realized_volatility < 0.24:
            score += 8
        if debt_to_equity is not None:
            score += 8 if debt_to_equity < 0.4 else -16 if debt_to_equity > 1.2 else 0
        if liabilities_to_assets is not None and liabilities_to_assets > 0.75:
            score -= 12
        return int(max(0, min(100, score)))

    def _score_governance(self, quote: dict) -> int:
        if quote.get("quoteType") == "EQUITY":
            return 58
        return 50

    def _score_sector(self, sector: str | None, one_year_price_return: float | None) -> int:
        score = 54 if sector else 46
        if one_year_price_return is not None:
            score += 8 if one_year_price_return > 0.12 else -6 if one_year_price_return < -0.12 else 0
        return int(max(0, min(100, score)))

    def _score_news(self, news_items: list[CompanyNewsRead]) -> int:
        return int(max(0, min(100, 48 + min(len(news_items), 6) * 6)))

    def _score_sentiment(self, news_items: list[CompanyNewsRead]) -> int:
        positive_words = ("beats", "growth", "profit", "wins", "upgrade", "record", "expands", "surges")
        negative_words = ("loss", "falls", "probe", "downgrade", "fraud", "default", "decline", "misses")
        score = 50
        for item in news_items[:6]:
            title = item.title.lower()
            if any(word in title for word in positive_words):
                score += 7
            if any(word in title for word in negative_words):
                score -= 9
        return int(max(0, min(100, score)))

    def _weighted_final_score(
        self,
        *,
        fundamental: int,
        technical: int,
        valuation: int,
        risk: int,
        governance: int,
        sector: int,
        news: int,
        sentiment: int,
    ) -> int:
        return round(
            fundamental * SCORING_WEIGHTS["fundamental"]
            + technical * SCORING_WEIGHTS["technical"]
            + valuation * SCORING_WEIGHTS["valuation"]
            + risk * SCORING_WEIGHTS["risk"]
            + governance * SCORING_WEIGHTS["governance"]
            + sector * SCORING_WEIGHTS["sector"]
            + news * SCORING_WEIGHTS["news"]
            + sentiment * SCORING_WEIGHTS["sentiment"]
        )

    def _valuation_profile(
        self,
        last_price: float | None,
        price_position: float | None,
        valuation_score: int,
        final_score: int,
    ) -> dict[str, float | None]:
        if last_price is None or last_price <= 0:
            return {
                "intrinsic_value": None,
                "fair_value": None,
                "expected_upside": None,
                "stop_loss": None,
                "target1": None,
                "target2": None,
                "target3": None,
            }
        valuation_discount = (valuation_score - 50) / 250
        quality_premium = (final_score - 60) / 300
        if price_position is not None and price_position > 0.88:
            valuation_discount -= 0.06
        fair_value = round(last_price * (1 + valuation_discount), 2)
        intrinsic_value = round(last_price * (1 + valuation_discount + quality_premium), 2)
        upside = round((intrinsic_value - last_price) / last_price * 100, 2)
        stop_loss = round(last_price * 0.92, 2)
        return {
            "intrinsic_value": intrinsic_value,
            "fair_value": fair_value,
            "expected_upside": upside,
            "stop_loss": stop_loss,
            "target1": round(last_price * 1.08, 2),
            "target2": round(last_price * 1.16, 2),
            "target3": round(max(intrinsic_value, last_price * 1.24), 2),
        }

    def _confidence(
        self,
        final_score: int,
        risk_score: int,
        news_score: int,
        sentiment_score: int,
        series: dict[str, list[float]],
    ) -> int:
        data_bonus = min(18, len(series) * 2)
        score = final_score * 0.55 + risk_score * 0.18 + news_score * 0.12 + sentiment_score * 0.10 + data_bonus
        return int(max(20, min(96, round(score))))

    def _investment_horizon(self, recommendation: str, technical_score: int, risk_score: int) -> str:
        if recommendation in {"Strong Conviction Buy", "Strong Buy", "Buy"} and technical_score >= 65 and risk_score >= 55:
            return "6-18 months with quarterly thesis review"
        if recommendation in {"Accumulate", "Hold"}:
            return "3-12 months; review after earnings, valuation change, or trend break"
        return "Near-term risk review; avoid adding until score improves"

    def _risk_factors(
        self,
        risk_score: int,
        valuation_score: int,
        realized_volatility: float | None,
        concerns: list[str],
    ) -> list[str]:
        risks = list(concerns[:3])
        if risk_score < 45:
            risks.append("Composite market/business risk score is weak.")
        if valuation_score < 45:
            risks.append("Valuation or price-position score is stretched.")
        if realized_volatility is not None and realized_volatility > 0.55:
            risks.append("Realized volatility is elevated versus a stable portfolio holding.")
        return risks[:5] or ["No major model-derived risk factor detected."]

    def _catalysts(self, news_items: list[CompanyNewsRead], strengths: list[str]) -> list[str]:
        catalysts = strengths[:2]
        catalysts.extend(item.title for item in news_items[:2])
        return catalysts[:4] or ["Next earnings, corporate announcement, or sector momentum update."]

    def _explanation(
        self,
        *,
        symbol: str,
        final_score: int,
        recommendation: str,
        fundamental_score: int,
        technical_score: int,
        valuation_score: int,
        risk_score: int,
        governance_score: int,
        sector_score: int,
        news_score: int,
        sentiment_score: int,
    ) -> str:
        return (
            f"{symbol} recommendation is {recommendation} from a weighted multi-factor score of {final_score}/100. "
            f"Drivers: fundamental {fundamental_score} at 40%, technical {technical_score} at 20%, "
            f"valuation {valuation_score} at 10%, risk {risk_score} at 10%, governance {governance_score} at 5%, "
            f"sector {sector_score} at 5%, news {news_score} at 5%, sentiment {sentiment_score} at 5%. "
            "No recommendation is produced from a single indicator."
        )

    def _recommendation(
        self,
        overall: int,
        risk: int,
    ) -> str:
        if risk < 35:
            return "Reduce" if overall >= 40 else "Sell"
        if overall >= 95:
            return "Strong Conviction Buy"
        if overall >= 90:
            return "Strong Buy"
        if overall >= 80:
            return "Buy"
        if overall >= 70:
            return "Accumulate"
        if overall >= 60:
            return "Hold"
        if overall >= 40:
            return "Reduce"
        if overall >= 20:
            return "Sell"
        return "Strong Sell"

    def _score_balance_sheet(
        self,
        debt_to_equity: float | None,
        cash_to_debt: float | None,
        liabilities_to_assets: float | None,
    ) -> int:
        score = 55
        if debt_to_equity is None:
            score -= 15
        elif debt_to_equity < 0.4:
            score += 25
        elif debt_to_equity < 1.0:
            score += 8
        else:
            score -= 18
        if cash_to_debt is not None and cash_to_debt > 0.6:
            score += 10
        if liabilities_to_assets is not None:
            score += 10 if liabilities_to_assets < 0.45 else -10 if liabilities_to_assets > 0.75 else 0
        return int(max(0, min(100, score)))

    def _score_growth(
        self,
        revenue_growth: float | None,
        net_income_growth: float | None,
        eps_growth: float | None,
    ) -> int:
        score = 50
        for value in (revenue_growth, net_income_growth, eps_growth):
            if value is None:
                score -= 10
            elif value > 0.15:
                score += 18
            elif value > 0.05:
                score += 8
            elif value < 0:
                score -= 15
        return int(max(0, min(100, score)))

    def _score_cash_flow(
        self,
        fcf_margin: float | None,
        free_cash_flow: float | None,
        operating_cashflow_to_debt: float | None,
    ) -> int:
        if fcf_margin is None:
            return 42
        score = 50 + fcf_margin * 220
        if free_cash_flow is not None and free_cash_flow > 0:
            score += 12
        if operating_cashflow_to_debt is not None:
            score += 10 if operating_cashflow_to_debt > 0.25 else -8 if operating_cashflow_to_debt < 0.05 else 0
        return int(max(0, min(100, score)))

    def _score_valuation(self, price_position: float | None, one_year_price_return: float | None) -> int:
        if price_position is None:
            return 50
        if price_position < 0.35:
            score = 76
        elif price_position < 0.7:
            score = 64
        elif price_position < 0.88:
            score = 52
        else:
            score = 38
        if one_year_price_return is not None and one_year_price_return > 0.45:
            score -= 8
        if one_year_price_return is not None and one_year_price_return < -0.25:
            score += 5
        return int(max(0, min(100, score)))

    def _growth(self, old: float | None, new: float | None) -> float | None:
        if old is None or new is None or old == 0:
            return None
        return (new - old) / abs(old)

    def _ratio(self, numerator: float | None, denominator: float | None) -> float | None:
        if numerator is None or denominator is None or denominator == 0:
            return None
        return numerator / denominator

    def _price_position(self, meta: dict) -> float | None:
        last = self._as_float(meta.get("regularMarketPrice"))
        low = self._as_float(meta.get("fiftyTwoWeekLow"))
        high = self._as_float(meta.get("fiftyTwoWeekHigh"))
        if last is None or low is None or high is None or high <= low:
            return None
        return (last - low) / (high - low)

    def _one_year_price_return(self, chart: dict) -> float | None:
        closes = self._chart_closes(chart)
        if len(closes) < 30 or closes[0] == 0:
            return None
        return (closes[-1] - closes[0]) / closes[0]

    def _realized_volatility(self, chart: dict) -> float | None:
        closes = self._chart_closes(chart)
        if len(closes) < 30:
            return None
        returns = [(current - previous) / previous for previous, current in zip(closes, closes[1:]) if previous]
        if len(returns) < 20:
            return None
        mean = sum(returns) / len(returns)
        variance = sum((item - mean) ** 2 for item in returns) / len(returns)
        return math.sqrt(variance) * math.sqrt(252)

    def _chart_closes(self, chart: dict) -> list[float]:
        try:
            values = chart["chart"]["result"][0]["indicators"]["quote"][0].get("close", [])
        except (KeyError, IndexError, TypeError):
            return []
        return [float(value) for value in values if value is not None and self._is_finite(value) and float(value) > 0]

    def _day_change_pct(self, meta: dict) -> float | None:
        last = self._as_float(meta.get("regularMarketPrice"))
        previous = self._as_float(meta.get("previousClose")) or self._as_float(meta.get("chartPreviousClose"))
        if last is None or previous is None or previous == 0:
            return None
        return (last - previous) / previous * 100

    def _as_float(self, value: Any) -> float | None:
        if value is None:
            return None
        try:
            output = float(value)
        except (TypeError, ValueError):
            return None
        return output if math.isfinite(output) else None

    def _clean_statement_value(self, metric_type: str, value: Any) -> float | None:
        number = self._as_float(value)
        if number is None or abs(number) > 1e18:
            return None
        positive_only = {
            "annualTotalAssets",
            "annualTotalLiabilitiesNetMinorityInterest",
            "annualTotalDebt",
            "annualStockholdersEquity",
            "annualCashAndCashEquivalents",
            "annualTotalRevenue",
        }
        if metric_type in positive_only and number < 0:
            return None
        return number

    def _is_finite(self, value: Any) -> bool:
        try:
            return math.isfinite(float(value))
        except (TypeError, ValueError):
            return False

    def _decision_signals(self, companies: list[CompanyAnalyticsRead]) -> list[DecisionSignalRead]:
        return sorted(
            [self._decision_signal(company) for company in companies],
            key=lambda item: item.conviction_score,
            reverse=True,
        )

    def _decision_signal(self, company: CompanyAnalyticsRead) -> DecisionSignalRead:
        weak_core = company.balance_sheet_score < 45 or company.cash_flow_score < 45
        stretched = company.valuation_score < 45
        low_quality = sum(1 for metric in company.financials if metric.value != "N/A") < 7
        risk_flags = []
        if weak_core:
            risk_flags.append("Weak balance-sheet or cash-flow core.")
        if stretched:
            risk_flags.append("Valuation/price position is stretched.")
        if low_quality:
            risk_flags.append("Provider data coverage is limited.")
        risk_flags.extend(company.concerns[:2])
        confidence = int(
            max(
                20,
                min(
                    94,
                    company.overall_score * 0.5
                    + company.balance_sheet_score * 0.16
                    + company.cash_flow_score * 0.16
                    + company.valuation_score * 0.1
                    + (8 if company.news else -6)
                    - (10 if low_quality else 0),
                ),
            )
        )
        conviction = int(
            max(
                0,
                min(
                    100,
                    company.overall_score * 0.42
                    + company.balance_sheet_score * 0.18
                    + company.growth_score * 0.14
                    + company.cash_flow_score * 0.18
                    + company.valuation_score * 0.08
                    - len(risk_flags) * 3,
                ),
            )
        )

        if low_quality:
            action = "Hold / Verify Data"
        elif company.overall_score >= 76 and not weak_core and not stretched:
            action = "Add Candidate"
        elif company.overall_score >= 62 and not weak_core:
            action = "Hold / Accumulate Slowly"
        elif weak_core or company.overall_score < 50:
            action = "Risk Review"
        else:
            action = "Hold"

        return DecisionSignalRead(
            symbol=company.symbol,
            action=action,
            confidence=confidence,
            conviction_score=conviction,
            risk_flags=risk_flags[:4] or ["No critical model risk flag detected."],
            entry_discipline=self._entry_discipline(company, action),
            exit_guard=self._exit_guard(company, action),
            reasoning=(
                f"{company.symbol} has BI {company.overall_score}/100, balance {company.balance_sheet_score}, "
                f"growth {company.growth_score}, cash flow {company.cash_flow_score}, valuation {company.valuation_score}."
            ),
        )

    def _entry_discipline(self, company: CompanyAnalyticsRead, action: str) -> str:
        if action == "Add Candidate":
            return "Use staged buying only; prefer pullbacks or stable trend confirmation."
        if "Accumulate" in action:
            return "Add slowly only if the next earnings/news cycle confirms the thesis."
        if "Verify" in action:
            return "Do not add until missing fundamentals or price data are verified."
        return "No fresh buying unless the weak signal improves."

    def _exit_guard(self, company: CompanyAnalyticsRead, action: str) -> str:
        if action == "Risk Review":
            return "Prepare trim/rebalance if weak cash flow, balance sheet or price trend persists."
        if company.valuation_score < 45:
            return "Protect gains if price stays stretched and fundamentals do not catch up."
        return "Review after earnings, major news, or a material trend break."

    def _sanity_checks(
        self,
        companies: list[CompanyAnalyticsRead],
        warnings: list[str],
    ) -> list[AnalyticsSanityCheckRead]:
        if not companies:
            return [
                AnalyticsSanityCheckRead(
                    label="Portfolio coverage",
                    status="fail",
                    detail="No holdings are available for analytics.",
                )
            ]
        checks = []
        fundamentals_coverage = sum(
            1 for company in companies if sum(1 for metric in company.financials if metric.value != "N/A") >= 7
        ) / len(companies)
        price_coverage = sum(1 for company in companies if company.last_price is not None) / len(companies)
        news_coverage = sum(1 for company in companies if company.news) / len(companies)
        impossible_scores = [
            company.symbol
            for company in companies
            if not all(
                0 <= value <= 100
                for value in [
                    company.overall_score,
                    company.balance_sheet_score,
                    company.growth_score,
                    company.cash_flow_score,
                    company.valuation_score,
                ]
            )
        ]
        checks.append(
            AnalyticsSanityCheckRead(
                label="Fundamental coverage",
                status="pass" if fundamentals_coverage >= 0.75 else "watch" if fundamentals_coverage >= 0.45 else "fail",
                detail=f"{fundamentals_coverage * 100:.0f}% of holdings have enough statement metrics.",
            )
        )
        checks.append(
            AnalyticsSanityCheckRead(
                label="Live price coverage",
                status="pass" if price_coverage >= 0.9 else "watch" if price_coverage >= 0.6 else "fail",
                detail=f"{price_coverage * 100:.0f}% of holdings returned latest provider price data.",
            )
        )
        checks.append(
            AnalyticsSanityCheckRead(
                label="News coverage",
                status="pass" if news_coverage >= 0.7 else "watch" if news_coverage >= 0.35 else "fail",
                detail=f"{news_coverage * 100:.0f}% of holdings returned related market news.",
            )
        )
        checks.append(
            AnalyticsSanityCheckRead(
                label="Score bounds",
                status="fail" if impossible_scores else "pass",
                detail=(
                    f"Out-of-range scores detected for {', '.join(impossible_scores)}."
                    if impossible_scores
                    else "All model scores are within the expected 0-100 range."
                ),
            )
        )
        checks.append(
            AnalyticsSanityCheckRead(
                label="Provider warning load",
                status="pass" if len(warnings) <= 1 else "watch" if len(warnings) <= 5 else "fail",
                detail=f"{len(warnings)} provider warning(s) were produced in this run.",
            )
        )
        return checks

    def _analysis_date(self) -> date:
        return datetime.now(MARKET_TZ).date()

    def _next_refresh_at(self) -> datetime:
        now = datetime.now(MARKET_TZ)
        refresh_time = datetime.combine(now.date(), time(hour=9, minute=30), tzinfo=MARKET_TZ)
        if now >= refresh_time:
            refresh_time += timedelta(days=1)
        return refresh_time.astimezone(UTC)

    def _holdings_signature(self, holdings: list[dict]) -> str:
        if not holdings:
            return "empty"
        parts = []
        for holding in sorted(holdings, key=lambda item: str(item.get("symbol", ""))):
            parts.append(
                ":".join(
                    [
                        str(holding.get("symbol", "")),
                        str(holding.get("quantity", "")),
                        str(holding.get("average_price", "")),
                        str(holding.get("last_price", "")),
                        str(holding.get("updated_at", "")),
                    ]
                )
            )
        return "|".join(parts)
