import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from src.core.config import settings
from src.domain.auth import UserContext
from src.repositories.app_settings import AppSettingsRepository
from src.repositories.portfolio import PortfolioRepository
from src.schemas.discovery import DiscoveryCandidateRead, StockDiscoveryRead
from src.services.company_analytics_service import CompanyAnalyticsService
from src.services.openai_settings_service import OpenAiSettingsService


DISCOVERY_UNIVERSE = [
    # Large cap
    {"symbol": "TCS", "company_name": "Tata Consultancy Services Ltd", "sector": "Information Technology", "cap": "Large Cap"},
    {"symbol": "INFY", "company_name": "Infosys Ltd", "sector": "Information Technology", "cap": "Large Cap"},
    {"symbol": "HDFCBANK", "company_name": "HDFC Bank Ltd", "sector": "Financial Services", "cap": "Large Cap"},
    {"symbol": "ICICIBANK", "company_name": "ICICI Bank Ltd", "sector": "Financial Services", "cap": "Large Cap"},
    {"symbol": "SBIN", "company_name": "State Bank of India", "sector": "Financial Services", "cap": "Large Cap"},
    {"symbol": "LT", "company_name": "Larsen & Toubro Ltd", "sector": "Industrials", "cap": "Large Cap"},
    {"symbol": "BHARTIARTL", "company_name": "Bharti Airtel Ltd", "sector": "Communication Services", "cap": "Large Cap"},
    {"symbol": "SUNPHARMA", "company_name": "Sun Pharmaceutical Industries Ltd", "sector": "Healthcare", "cap": "Large Cap"},
    {"symbol": "MARUTI", "company_name": "Maruti Suzuki India Ltd", "sector": "Consumer Cyclical", "cap": "Large Cap"},
    {"symbol": "TITAN", "company_name": "Titan Company Ltd", "sector": "Consumer Cyclical", "cap": "Large Cap"},
    {"symbol": "ULTRACEMCO", "company_name": "UltraTech Cement Ltd", "sector": "Materials", "cap": "Large Cap"},
    {"symbol": "ASIANPAINT", "company_name": "Asian Paints Ltd", "sector": "Consumer Defensive", "cap": "Large Cap"},
    {"symbol": "NESTLEIND", "company_name": "Nestle India Ltd", "sector": "Consumer Defensive", "cap": "Large Cap"},
    {"symbol": "BAJFINANCE", "company_name": "Bajaj Finance Ltd", "sector": "Financial Services", "cap": "Large Cap"},
    {"symbol": "POWERGRID", "company_name": "Power Grid Corporation of India Ltd", "sector": "Utilities", "cap": "Large Cap"},
    {"symbol": "HCLTECH", "company_name": "HCL Technologies Ltd", "sector": "Information Technology", "cap": "Large Cap"},
    {"symbol": "AXISBANK", "company_name": "Axis Bank Ltd", "sector": "Financial Services", "cap": "Large Cap"},
    {"symbol": "KOTAKBANK", "company_name": "Kotak Mahindra Bank Ltd", "sector": "Financial Services", "cap": "Large Cap"},
    # Mid cap
    {"symbol": "PERSISTENT", "company_name": "Persistent Systems Ltd", "sector": "Information Technology", "cap": "Mid Cap"},
    {"symbol": "COFORGE", "company_name": "Coforge Ltd", "sector": "Information Technology", "cap": "Mid Cap"},
    {"symbol": "MPHASIS", "company_name": "Mphasis Ltd", "sector": "Information Technology", "cap": "Mid Cap"},
    {"symbol": "POLYCAB", "company_name": "Polycab India Ltd", "sector": "Industrials", "cap": "Mid Cap"},
    {"symbol": "DIXON", "company_name": "Dixon Technologies India Ltd", "sector": "Technology Hardware", "cap": "Mid Cap"},
    {"symbol": "CUMMINSIND", "company_name": "Cummins India Ltd", "sector": "Industrials", "cap": "Mid Cap"},
    {"symbol": "AUBANK", "company_name": "AU Small Finance Bank Ltd", "sector": "Financial Services", "cap": "Mid Cap"},
    {"symbol": "FEDERALBNK", "company_name": "The Federal Bank Ltd", "sector": "Financial Services", "cap": "Mid Cap"},
    {"symbol": "INDHOTEL", "company_name": "The Indian Hotels Company Ltd", "sector": "Consumer Cyclical", "cap": "Mid Cap"},
    {"symbol": "MAXHEALTH", "company_name": "Max Healthcare Institute Ltd", "sector": "Healthcare", "cap": "Mid Cap"},
    {"symbol": "FORTIS", "company_name": "Fortis Healthcare Ltd", "sector": "Healthcare", "cap": "Mid Cap"},
    {"symbol": "ASHOKLEY", "company_name": "Ashok Leyland Ltd", "sector": "Industrials", "cap": "Mid Cap"},
    {"symbol": "BALKRISIND", "company_name": "Balkrishna Industries Ltd", "sector": "Consumer Cyclical", "cap": "Mid Cap"},
    {"symbol": "ASTRAL", "company_name": "Astral Ltd", "sector": "Industrials", "cap": "Mid Cap"},
    {"symbol": "PAGEIND", "company_name": "Page Industries Ltd", "sector": "Consumer Cyclical", "cap": "Mid Cap"},
    # Small cap
    {"symbol": "KAYNES", "company_name": "Kaynes Technology India Ltd", "sector": "Technology Hardware", "cap": "Small Cap"},
    {"symbol": "KPITTECH", "company_name": "KPIT Technologies Ltd", "sector": "Information Technology", "cap": "Small Cap"},
    {"symbol": "TANLA", "company_name": "Tanla Platforms Ltd", "sector": "Communication Services", "cap": "Small Cap"},
    {"symbol": "CAMS", "company_name": "Computer Age Management Services Ltd", "sector": "Financial Services", "cap": "Small Cap"},
    {"symbol": "CDSL", "company_name": "Central Depository Services India Ltd", "sector": "Financial Services", "cap": "Small Cap"},
    {"symbol": "ANGELONE", "company_name": "Angel One Ltd", "sector": "Financial Services", "cap": "Small Cap"},
    {"symbol": "IEX", "company_name": "Indian Energy Exchange Ltd", "sector": "Financial Services", "cap": "Small Cap"},
    {"symbol": "RITES", "company_name": "RITES Ltd", "sector": "Industrials", "cap": "Small Cap"},
    {"symbol": "MAZDOCK", "company_name": "Mazagon Dock Shipbuilders Ltd", "sector": "Industrials", "cap": "Small Cap"},
    {"symbol": "GRSE", "company_name": "Garden Reach Shipbuilders & Engineers Ltd", "sector": "Industrials", "cap": "Small Cap"},
    {"symbol": "JYOTHYLAB", "company_name": "Jyothy Labs Ltd", "sector": "Consumer Defensive", "cap": "Small Cap"},
    {"symbol": "FINEORG", "company_name": "Fine Organic Industries Ltd", "sector": "Materials", "cap": "Small Cap"},
    {"symbol": "NEULANDLAB", "company_name": "Neuland Laboratories Ltd", "sector": "Healthcare", "cap": "Small Cap"},
    {"symbol": "SYRMA", "company_name": "Syrma SGS Technology Ltd", "sector": "Technology Hardware", "cap": "Small Cap"},
    {"symbol": "MTARTECH", "company_name": "MTAR Technologies Ltd", "sector": "Industrials", "cap": "Small Cap"},
]


class StockDiscoveryService:
    def __init__(
        self,
        portfolio_repo: PortfolioRepository,
        settings_repo: AppSettingsRepository | None = None,
    ) -> None:
        self._portfolio_repo = portfolio_repo
        self._company_analytics = CompanyAnalyticsService(portfolio_repo)
        self._ai_settings = OpenAiSettingsService(settings_repo) if settings_repo else None
        self._timeout = max(6.0, settings.market_data_timeout_seconds)
        self._max_concurrency = max(1, settings.market_data_max_concurrency)

    async def discover(self, context: UserContext) -> StockDiscoveryRead:
        now = datetime.now(UTC)
        valid_until = now + timedelta(days=2)
        holdings = await self._portfolio_repo.list_holdings(context)
        held_symbols = {str(holding["symbol"]).upper() for holding in holdings}
        universe = [item for item in DISCOVERY_UNIVERSE if item["symbol"] not in held_symbols]
        rotated_universe = self._rotate_universe(universe, now)
        semaphore = asyncio.Semaphore(self._max_concurrency)
        headers = {"User-Agent": "Mozilla/5.0 ai-portfolio-advisor/1.0"}

        async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
            companies = await asyncio.gather(
                *[
                    self._company_analytics._analyze_company(
                        client,
                        semaphore,
                        {
                            "symbol": item["symbol"],
                            "exchange": "NSE",
                            "company_name": item["company_name"],
                            "sector": item["sector"],
                        },
                    )
                    for item in rotated_universe
                ]
            )

        cap_by_symbol = {item["symbol"]: item["cap"] for item in rotated_universe}
        candidates = [
            self._candidate_from_company(company, str(cap_by_symbol.get(company.symbol, "Large Cap")), now)
            for company in companies
        ]
        candidates = self._balanced_shortlist(candidates)
        ai_notes, ai_warning = await self._ai_company_views(context, candidates)
        if ai_notes:
            candidates = [
                candidate.model_copy(update={"ai_view": ai_notes.get(candidate.symbol) or candidate.ai_view})
                for candidate in candidates
            ]
        warnings = [
            note
            for candidate in candidates
            for note in candidate.source_notes
            if note.lower().startswith(("could not", "missing", "limited", "fundamental", "withheld", "rejected"))
        ][:8]
        if ai_warning:
            warnings.append(ai_warning)
        warnings.append(
            "Discovery ideas expire after 2 days. Refresh after expiry because price, valuation, news and earnings context can change."
        )
        warnings.append(
            "Discovery is advisory only. Verify fundamentals, valuation, liquidity, news and your risk profile before buying."
        )

        return StockDiscoveryRead(
            generated_at=now,
            valid_until=valid_until,
            universe="Curated NSE large, mid and small-cap opportunity universe",
            methodology=(
                "Ranks non-held stocks across large, mid and small-cap buckets using fundamentals, quality, cash flow, "
                "valuation discipline, price/technical context, data-quality penalties and optional AI company analysis. "
                "Recommendations are valid for 2 days only, then a fresh scan is required."
            ),
            candidates=candidates,
            excluded_symbols=sorted(held_symbols),
            warnings=warnings,
        )

    def _candidate_from_company(self, company, market_cap_category: str, generated_at: datetime) -> DiscoveryCandidateRead:
        missing_metrics = sum(1 for metric in company.financials if metric.value == "N/A")
        data_quality = max(20, min(96, 94 - missing_metrics * 6 - (0 if company.last_price else 14) - (0 if company.news else 6)))
        fundamental_score = int(round(company.balance_sheet_score * 0.34 + company.growth_score * 0.28 + company.cash_flow_score * 0.38))
        technical_score = self._technical_proxy(company)
        quality_score = int(round(fundamental_score * 0.58 + data_quality * 0.24 + min(100, len(company.news) * 20) * 0.18))
        cap_risk_penalty = {"Large Cap": 0, "Mid Cap": 4, "Small Cap": 9}.get(market_cap_category, 0)
        score = int(
            max(
                0,
                min(
                    100,
                    fundamental_score * 0.42
                    + quality_score * 0.22
                    + company.valuation_score * 0.16
                    + technical_score * 0.12
                    + data_quality * 0.08
                    - max(0, missing_metrics - 3) * 2
                    - cap_risk_penalty,
                ),
            )
        )
        risk = self._risk_level(company, data_quality, market_cap_category)
        conviction = "High" if score >= 78 and data_quality >= 72 and risk != "High" else "Medium" if score >= 60 else "Low"
        recommendation = (
            "Professional Research Buy Candidate"
            if conviction == "High"
            else "Advisory Watchlist / Staged Entry"
            if conviction == "Medium"
            else "Avoid Fresh Buy Until Verified"
        )
        opportunity_rank = self._opportunity_rank(company.symbol, generated_at)

        why_buy = [
            *company.strengths[:3],
            f"Advanced score mix: fundamental {fundamental_score}, quality {quality_score}, technical {technical_score}, valuation {company.valuation_score}.",
        ][:4]
        potential = [
            f"{company.symbol} adds {market_cap_category.lower()} exposure outside current holdings.",
            f"Business quality score mix: balance {company.balance_sheet_score}, growth {company.growth_score}, cash flow {company.cash_flow_score}.",
            "Potential is strongest only if earnings visibility, cash generation, valuation and trend remain aligned.",
        ]
        risks = [
            *company.concerns[:3],
            f"{market_cap_category} ideas need position-size discipline; smaller companies can move sharply on liquidity and news.",
            "Provider data can be incomplete or delayed; verify annual report, latest quarter and exchange filings.",
        ][:5]

        return DiscoveryCandidateRead(
            symbol=company.symbol,
            company_name=company.company_name,
            sector=company.sector,
            industry=company.industry,
            market_cap_category=market_cap_category,  # type: ignore[arg-type]
            last_price=company.last_price,
            discovery_score=score,
            fundamental_score=fundamental_score,
            technical_score=technical_score,
            valuation_score=company.valuation_score,
            quality_score=quality_score,
            opportunity_rank=opportunity_rank,
            conviction=conviction,
            risk_level=risk,  # type: ignore[arg-type]
            recommendation=recommendation,
            why_buy=why_buy,
            company_potential=potential,
            risks=risks,
            entry_discipline=self._entry_discipline(company, conviction, risk, market_cap_category),
            verification_triggers=[
                "Check latest quarterly result, annual report and management commentary.",
                "Confirm valuation against sector peers and historical range.",
                "Verify price trend, support zone, liquidity and delivery volume before entry.",
                "Avoid buying if fresh exchange filing, result, pledge or governance news changes the thesis.",
            ],
            research_view=(
                f"Research model view: {company.symbol} is a {recommendation.lower()} because fundamentals, "
                f"quality, valuation and technical context combine to {score}/100. This is an advisory candidate, not an order."
            ),
            ai_view=None,
            data_quality_score=data_quality,
            source_notes=company.source_notes,
        )

    def _balanced_shortlist(self, candidates: list[DiscoveryCandidateRead]) -> list[DiscoveryCandidateRead]:
        ranked = sorted(candidates, key=lambda item: (item.discovery_score + item.opportunity_rank * 0.08), reverse=True)
        output: list[DiscoveryCandidateRead] = []
        bucket_targets = {"Large Cap": 4, "Mid Cap": 4, "Small Cap": 4}
        for bucket, target in bucket_targets.items():
            output.extend([item for item in ranked if item.market_cap_category == bucket][:target])
        if len(output) < 12:
            selected = {item.symbol for item in output}
            output.extend([item for item in ranked if item.symbol not in selected][: 12 - len(output)])
        return sorted(output[:12], key=lambda item: (item.discovery_score, item.opportunity_rank), reverse=True)

    async def _ai_company_views(
        self,
        context: UserContext,
        candidates: list[DiscoveryCandidateRead],
    ) -> tuple[dict[str, str], str | None]:
        if not self._ai_settings or not candidates:
            return {}, "AI company analysis was skipped because app settings are not available."
        provider = await self._ai_settings.get_provider(context)
        api_key = await self._ai_settings.get_api_key(context, provider)
        model = await self._ai_settings.get_model(context, provider)
        if not api_key:
            return {}, "AI company analysis is available after configuring Gemini or OpenAI in AI Config."
        payload = {
            "instruction": "Return concise advisory company-analysis notes. Do not invent prices, targets or guarantees.",
            "validForDays": 2,
            "candidates": [
                {
                    "symbol": item.symbol,
                    "companyName": item.company_name,
                    "marketCapCategory": item.market_cap_category,
                    "sector": item.sector,
                    "discoveryScore": item.discovery_score,
                    "fundamentalScore": item.fundamental_score,
                    "technicalScore": item.technical_score,
                    "valuationScore": item.valuation_score,
                    "qualityScore": item.quality_score,
                    "riskLevel": item.risk_level,
                    "risks": item.risks[:3],
                    "whyBuy": item.why_buy[:3],
                }
                for item in candidates[:8]
            ],
        }
        try:
            if provider == "openai":
                return await self._call_openai_ai(api_key, model, payload), None
            return await self._call_gemini_ai(api_key, model, payload), None
        except (httpx.HTTPError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            return {}, f"AI company analysis failed: {exc.__class__.__name__}. Deterministic discovery scores are still available."

    async def _call_openai_ai(self, api_key: str, model: str, payload: dict[str, Any]) -> dict[str, str]:
        async with httpx.AsyncClient(timeout=max(10.0, settings.openai_timeout_seconds)) as client:
            response = await client.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "instructions": self._ai_instructions(),
                    "input": json.dumps(payload, ensure_ascii=True),
                    "text": {"format": {"type": "json_object"}},
                },
            )
            response.raise_for_status()
            data = response.json()
        text = data.get("output_text") or data.get("text") or ""
        return self._extract_ai_notes(text)

    async def _call_gemini_ai(self, api_key: str, model: str, payload: dict[str, Any]) -> dict[str, str]:
        async with httpx.AsyncClient(timeout=max(10.0, settings.openai_timeout_seconds)) as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                params={"key": api_key},
                headers={"Content-Type": "application/json"},
                json={
                    "systemInstruction": {"parts": [{"text": self._ai_instructions()}]},
                    "contents": [{"role": "user", "parts": [{"text": json.dumps(payload, ensure_ascii=True)}]}],
                    "generationConfig": {"temperature": 0.15, "responseMimeType": "application/json"},
                },
            )
            response.raise_for_status()
            data = response.json()
        parts = data["candidates"][0]["content"]["parts"]
        text = "".join(str(part.get("text") or "") for part in parts)
        return self._extract_ai_notes(text)

    def _extract_ai_notes(self, text: str) -> dict[str, str]:
        payload = json.loads(text)
        notes = payload.get("companyNotes") if isinstance(payload, dict) else None
        if not isinstance(notes, list):
            return {}
        output = {}
        for item in notes:
            if isinstance(item, dict) and item.get("symbol") and item.get("analysis"):
                output[str(item["symbol"]).upper()] = str(item["analysis"])[:700]
        return output

    def _ai_instructions(self) -> str:
        return (
            "You are an equity research assistant. Return JSON only: "
            "{\"companyNotes\":[{\"symbol\":\"SYMBOL\",\"analysis\":\"2-3 sentence advisory note\"}]}. "
            "Use only supplied scores and risks. No price targets, no guaranteed returns, no invented data."
        )

    def _risk_level(self, company, data_quality: int, market_cap_category: str) -> str:
        if data_quality < 55 or company.balance_sheet_score < 45 or company.cash_flow_score < 45:
            return "High"
        if market_cap_category == "Small Cap" and (company.valuation_score < 58 or company.growth_score < 55):
            return "High"
        if company.valuation_score < 48 or company.growth_score < 50 or market_cap_category == "Small Cap":
            return "Medium"
        return "Low"

    def _entry_discipline(self, company, conviction: str, risk: str, market_cap_category: str) -> str:
        cap_limit = {"Large Cap": "4-6%", "Mid Cap": "2-4%", "Small Cap": "1-2%"}.get(market_cap_category, "2-4%")
        if conviction == "High" and risk == "Low":
            return f"Build in small tranches only after price and valuation verification; keep initial allocation below {cap_limit}."
        if conviction == "Medium":
            return f"Keep on watchlist; enter only after pullback, result confirmation or clear trend continuation. Initial allocation below {cap_limit}."
        return "Do not buy now; first resolve data gaps, weak financial scores, valuation concerns or liquidity risk."

    def _technical_proxy(self, company) -> int:
        price_position = self._metric_percent(company, "Price in 52W range")
        one_year_trend = self._metric_percent(company, "1Y price trend")
        volatility = self._metric_percent(company, "Realized volatility")
        score = 56
        if price_position is not None:
            score += 14 if 0.25 <= price_position <= 0.78 else -10 if price_position > 0.9 else 4
        if one_year_trend is not None:
            score += 14 if 0.05 <= one_year_trend <= 0.55 else -10 if one_year_trend < -0.12 else -6 if one_year_trend > 0.8 else 0
        if volatility is not None:
            score += 8 if volatility < 0.35 else -10 if volatility > 0.55 else 0
        return int(max(0, min(100, score)))

    def _metric_percent(self, company, label: str) -> float | None:
        metric = next((item for item in company.financials if item.label == label), None)
        if metric is None or metric.value == "N/A":
            return None
        try:
            return float(metric.value.replace("%", "")) / 100
        except ValueError:
            return None

    def _rotate_universe(self, universe: list[dict], generated_at: datetime) -> list[dict]:
        window = generated_at.toordinal() // 2
        return sorted(universe, key=lambda item: self._stable_bucket(f"{window}:{item['symbol']}"))

    def _opportunity_rank(self, symbol: str, generated_at: datetime) -> int:
        window = generated_at.toordinal() // 2
        return 100 - self._stable_bucket(f"rank:{window}:{symbol}") % 100

    def _stable_bucket(self, value: str) -> int:
        return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:8], 16)
