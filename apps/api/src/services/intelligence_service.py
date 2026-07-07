from datetime import UTC, datetime

from src.domain.auth import UserContext
from src.repositories.audit import AuditLogRepository
from src.repositories.portfolio import PortfolioRepository
from src.repositories.recommendation_history import RecommendationHistoryRepository
from src.schemas.intelligence import (
    DataQualityRead,
    IntelligenceReportRead,
    PortfolioAlertRead,
    PortfolioIntelligenceRead,
    PortfolioOptimizationRead,
    RecommendationHistoryRead,
)
from src.services.alerting_service import AlertingService
from src.services.fundamental_analysis_service import FundamentalAnalysisService
from src.services.intelligence_providers import MarketDataProvider
from src.services.market_analysis_service import MarketAnalysisService
from src.services.news_analysis_service import NewsAnalysisService
from src.services.portfolio_analysis_service import PortfolioAnalysisService
from src.services.recommendation_engine import RecommendationEngine
from src.services.technical_analysis_service import TechnicalAnalysisService


class IntelligenceService:
    def __init__(
        self,
        portfolio_repo: PortfolioRepository,
        history_repo: RecommendationHistoryRepository,
        audit_repo: AuditLogRepository,
    ) -> None:
        self._portfolio_repo = portfolio_repo
        self._history_repo = history_repo
        self._audit_repo = audit_repo
        self._portfolio_analysis = PortfolioAnalysisService()
        self._fundamental = FundamentalAnalysisService()
        self._technical = TechnicalAnalysisService()
        self._market = MarketAnalysisService()
        self._news = NewsAnalysisService()
        self._engine = RecommendationEngine()
        self._provider = MarketDataProvider()
        self._alerts = AlertingService()

    async def analyze(self, context: UserContext, persist: bool = False) -> PortfolioIntelligenceRead:
        holdings = await self._portfolio_repo.list_holdings(context)
        provider_state = await self._provider.state()
        snapshots = await self._provider.fetch_many(holdings)
        holdings = self._apply_live_snapshots(holdings, snapshots)
        metrics, weights, sector_values = self._portfolio_analysis.analyze(holdings)
        market = self._market.analyze()
        previous = await self._history_repo.latest_by_symbol(context)

        recommendations = []
        for holding in holdings:
            fundamental = self._fundamental.analyze(holding)
            technical = self._technical.analyze(holding, snapshots.get(holding["symbol"]))
            news = self._news.analyze(holding["symbol"])
            recommendations.append(
                self._engine.recommend(
                    holding=holding,
                    allocation_pct=weights.get(holding["symbol"], 0),
                    fundamental=fundamental,
                    technical=technical,
                    news=news,
                    previous=previous.get(holding["symbol"]),
                )
            )

        if persist:
            price_by_symbol = {row["symbol"]: float(row["last_price"]) for row in holdings}
            await self._history_repo.save_many(context, recommendations, price_by_symbol)
            await self._audit_repo.record(context, "intelligence.recommendations.generated", "portfolio")

        snapshot_warnings = {symbol: snapshot.warnings for symbol, snapshot in snapshots.items() if snapshot.warnings}
        alerts = self._alerts.generate(
            holdings=holdings,
            recommendations=recommendations,
            weights=weights,
            sector_values=sector_values,
            portfolio_value=metrics.portfolio_value,
            snapshot_warnings=snapshot_warnings,
        )

        return PortfolioIntelligenceRead(
            generated_at=datetime.now(UTC),
            portfolio_metrics=metrics,
            market_analysis=market,
            recommendations=recommendations,
            optimization=self._optimization(recommendations, weights, sector_values, metrics.portfolio_value),
            alerts=alerts,
            data_quality=DataQualityRead(
                score=self._data_quality_score(provider_state.available, holdings, snapshots),
                warnings=self._data_quality_warnings(provider_state.notes, snapshot_warnings)
                + [
                    "XIRR, CAGR, beta, Sharpe and drawdown require historical transaction/price series.",
                    "Recommendations are explainable analytics, not trade execution instructions.",
                ],
            ),
        )

    async def generate_report(self, context: UserContext, report_type: str, persist: bool = True) -> IntelligenceReportRead:
        intelligence = await self.analyze(context, persist=persist)
        grouped = self._group_recommendations(intelligence.recommendations)
        summary = (
            f"{report_type.title()} report: portfolio health is "
            f"{intelligence.portfolio_metrics.health_score}/100 with "
            f"{len(intelligence.recommendations)} holdings analyzed."
        )
        return IntelligenceReportRead(
            report_type=report_type,
            generated_at=datetime.now(UTC),
            summary=summary,
            sections={
                "portfolioSummary": intelligence.portfolio_metrics.model_dump(mode="json", by_alias=True),
                "marketOverview": intelligence.market_analysis.model_dump(mode="json", by_alias=True),
                "stocksToWatch": grouped["Reduce"] + grouped["Book Partial Profit"] + grouped["Exit"],
                "buyMoreCandidates": grouped["Strong Buy"] + grouped["Buy More"] + grouped["Accumulate"],
                "holdCandidates": grouped["Hold"],
                "reduceCandidates": grouped["Reduce"],
                "bookProfitCandidates": grouped["Book Partial Profit"],
                "alerts": [item.model_dump(mode="json", by_alias=True) for item in intelligence.alerts],
                "riskAlerts": intelligence.optimization.high_risk_stocks,
                "dataQuality": intelligence.data_quality.model_dump(mode="json", by_alias=True),
            },
        )

    async def alerts(self, context: UserContext) -> list[PortfolioAlertRead]:
        intelligence = await self.analyze(context, persist=False)
        return intelligence.alerts

    async def history(self, context: UserContext) -> list[RecommendationHistoryRead]:
        return await self._history_repo.list_history(context)

    def _optimization(
        self,
        recommendations,
        weights: dict[str, float],
        sector_values: dict[str, float],
        portfolio_value: float,
    ) -> PortfolioOptimizationRead:
        overweight = [symbol for symbol, weight in weights.items() if weight > 15]
        underweight = [symbol for symbol, weight in weights.items() if weight < 1]
        weak = [item.symbol for item in recommendations if item.recommendation in {"Reduce", "Exit"}]
        high_risk = [item.symbol for item in recommendations if item.risk_score >= 75]
        duplicate = [
            sector
            for sector, value in sector_values.items()
            if portfolio_value and (value / portfolio_value * 100) > 35
        ]
        return PortfolioOptimizationRead(
            overweight_positions=overweight,
            underweight_positions=underweight,
            weak_holdings=weak,
            high_risk_stocks=high_risk,
            duplicate_sector_exposure=duplicate,
            cash_allocation_suggestion=(
                "Maintain cash buffer until external market regime and risk data providers are configured."
            ),
        )

    def _group_recommendations(self, recommendations) -> dict[str, list[str]]:
        groups = {
            "Strong Buy": [],
            "Buy More": [],
            "Accumulate": [],
            "Hold": [],
            "Reduce": [],
            "Book Partial Profit": [],
            "Exit": [],
        }
        for item in recommendations:
            groups[item.recommendation].append(item.symbol)
        return groups

    def _data_quality_score(self, provider_available: bool, holdings: list[dict], snapshots: dict) -> int:
        if not holdings:
            return 30
        technical_coverage = sum(1 for snapshot in snapshots.values() if len(snapshot.closes) >= 30) / len(holdings)
        score = 45
        if provider_available:
            score += 20
        score += int(technical_coverage * 25)
        return max(0, min(90, score))

    def _data_quality_warnings(self, provider_notes: list[str], snapshot_warnings: dict[str, list[str]]) -> list[str]:
        warnings = list(provider_notes)
        warning_count = sum(len(items) for items in snapshot_warnings.values())
        if warning_count:
            warnings.append(f"Live market enrichment returned warnings for {len(snapshot_warnings)} holdings.")
        return warnings

    def _apply_live_snapshots(self, holdings: list[dict], snapshots: dict) -> list[dict]:
        enriched = []
        for holding in holdings:
            snapshot = snapshots.get(holding["symbol"])
            if snapshot is None or snapshot.last_price is None:
                enriched.append(holding)
                continue

            quantity = float(holding["quantity"])
            average_price = float(holding["average_price"])
            last_price = float(snapshot.last_price)
            previous_close = float(snapshot.previous_close) if snapshot.previous_close else None
            enriched_holding = {
                **holding,
                "last_price": last_price,
                "total_pnl": (last_price - average_price) * quantity,
            }
            if previous_close and previous_close > 0:
                enriched_holding["day_pnl"] = (last_price - previous_close) * quantity
            enriched.append(enriched_holding)
        return enriched
