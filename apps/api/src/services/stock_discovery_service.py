import asyncio
from datetime import UTC, datetime

import httpx

from src.core.config import settings
from src.domain.auth import UserContext
from src.repositories.portfolio import PortfolioRepository
from src.schemas.discovery import DiscoveryCandidateRead, StockDiscoveryRead
from src.services.company_analytics_service import CompanyAnalyticsService


DISCOVERY_UNIVERSE = [
    {"symbol": "TCS", "company_name": "Tata Consultancy Services Ltd", "sector": "Information Technology"},
    {"symbol": "ICICIBANK", "company_name": "ICICI Bank Ltd", "sector": "Financial Services"},
    {"symbol": "LT", "company_name": "Larsen & Toubro Ltd", "sector": "Industrials"},
    {"symbol": "BHARTIARTL", "company_name": "Bharti Airtel Ltd", "sector": "Communication Services"},
    {"symbol": "SUNPHARMA", "company_name": "Sun Pharmaceutical Industries Ltd", "sector": "Healthcare"},
    {"symbol": "MARUTI", "company_name": "Maruti Suzuki India Ltd", "sector": "Consumer Cyclical"},
    {"symbol": "TITAN", "company_name": "Titan Company Ltd", "sector": "Consumer Cyclical"},
    {"symbol": "ULTRACEMCO", "company_name": "UltraTech Cement Ltd", "sector": "Materials"},
    {"symbol": "ASIANPAINT", "company_name": "Asian Paints Ltd", "sector": "Consumer Defensive"},
    {"symbol": "NESTLEIND", "company_name": "Nestle India Ltd", "sector": "Consumer Defensive"},
    {"symbol": "BAJFINANCE", "company_name": "Bajaj Finance Ltd", "sector": "Financial Services"},
    {"symbol": "POWERGRID", "company_name": "Power Grid Corporation of India Ltd", "sector": "Utilities"},
]


class StockDiscoveryService:
    def __init__(self, portfolio_repo: PortfolioRepository) -> None:
        self._portfolio_repo = portfolio_repo
        self._company_analytics = CompanyAnalyticsService(portfolio_repo)
        self._timeout = max(6.0, settings.market_data_timeout_seconds)
        self._max_concurrency = max(1, settings.market_data_max_concurrency)

    async def discover(self, context: UserContext) -> StockDiscoveryRead:
        holdings = await self._portfolio_repo.list_holdings(context)
        held_symbols = {str(holding["symbol"]).upper() for holding in holdings}
        universe = [item for item in DISCOVERY_UNIVERSE if item["symbol"] not in held_symbols]
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
                    for item in universe
                ]
            )

        candidates = [self._candidate_from_company(company) for company in companies]
        candidates = sorted(candidates, key=lambda item: item.discovery_score, reverse=True)[:8]
        warnings = [
            note
            for candidate in candidates
            for note in candidate.source_notes
            if note.lower().startswith(("could not", "missing", "limited", "fundamental"))
        ][:8]
        warnings.append(
            "Discovery is an advisory shortlist only. Verify fundamentals, valuation, liquidity, news and your risk profile before buying."
        )

        return StockDiscoveryRead(
            generated_at=datetime.now(UTC),
            universe="Curated NSE large-cap watch universe",
            methodology=(
                "Ranks stocks not already in your holdings using provider fundamentals, price position, "
                "growth, cash-flow quality, valuation discipline, news coverage and conservative data-quality penalties."
            ),
            candidates=candidates,
            excluded_symbols=sorted(held_symbols),
            warnings=warnings,
        )

    def _candidate_from_company(self, company) -> DiscoveryCandidateRead:
        missing_metrics = sum(1 for metric in company.financials if metric.value == "N/A")
        data_quality = max(20, min(95, 92 - missing_metrics * 7 - (0 if company.last_price else 12)))
        score = int(
            max(
                0,
                min(
                    100,
                    company.overall_score * 0.46
                    + company.balance_sheet_score * 0.16
                    + company.growth_score * 0.14
                    + company.cash_flow_score * 0.16
                    + company.valuation_score * 0.08
                    - max(0, missing_metrics - 3) * 3,
                ),
            )
        )
        risk = self._risk_level(company, data_quality)
        conviction = "High" if score >= 76 and data_quality >= 70 else "Medium" if score >= 58 else "Low"
        recommendation = (
            "Research Buy Candidate"
            if conviction == "High" and risk != "High"
            else "Watchlist / Staged Entry"
            if conviction == "Medium"
            else "Avoid Fresh Buy Until Verified"
        )

        why_buy = [
            *company.strengths[:3],
            f"Overall research score is {company.overall_score}/100 with discovery score {score}/100.",
        ][:4]
        potential = [
            f"{company.symbol} may improve portfolio opportunity breadth because it is outside current holdings.",
            f"Business quality score mix: balance {company.balance_sheet_score}, growth {company.growth_score}, cash flow {company.cash_flow_score}.",
            "Potential is strongest only if earnings visibility, cash generation and trend remain aligned.",
        ]
        risks = [
            *company.concerns[:3],
            "New-share ideas need independent verification because provider data may be incomplete or delayed.",
        ][:4]

        return DiscoveryCandidateRead(
            symbol=company.symbol,
            company_name=company.company_name,
            sector=company.sector,
            industry=company.industry,
            last_price=company.last_price,
            discovery_score=score,
            conviction=conviction,
            risk_level=risk,
            recommendation=recommendation,
            why_buy=why_buy,
            company_potential=potential,
            risks=risks,
            entry_discipline=self._entry_discipline(company, conviction, risk),
            verification_triggers=[
                "Check latest quarterly result and management commentary.",
                "Confirm valuation is not stretched against sector peers.",
                "Verify price trend, support zone and position size before entry.",
                "Avoid buying if fresh news changes the thesis.",
            ],
            research_view=(
                f"Research model view: {company.symbol} is a {recommendation.lower()} because quality, "
                f"growth, cash-flow and valuation scores combine to {score}/100. Treat it as a candidate, not an order."
            ),
            data_quality_score=data_quality,
            source_notes=company.source_notes,
        )

    def _risk_level(self, company, data_quality: int) -> str:
        if data_quality < 55 or company.balance_sheet_score < 45 or company.cash_flow_score < 45:
            return "High"
        if company.valuation_score < 48 or company.growth_score < 50:
            return "Medium"
        return "Low"

    def _entry_discipline(self, company, conviction: str, risk: str) -> str:
        if conviction == "High" and risk == "Low":
            return "Build in small tranches only after price and valuation verification; do not exceed target allocation on day one."
        if conviction == "Medium":
            return "Keep on watchlist; enter only after pullback, result confirmation or clear trend continuation."
        return "Do not buy now; first resolve data gaps, weak financial scores or valuation concerns."
