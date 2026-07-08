from collections import defaultdict
from datetime import UTC, datetime

from src.domain.auth import UserContext
from src.repositories.audit import AuditLogRepository
from src.repositories.portfolio import PortfolioRepository
from src.schemas.portfolio import AllocationRead, HoldingRead, ManualPortfolioImportResponse, PortfolioSummaryRead
from src.services.csv_portfolio_parser import parse_portfolio_csv


class PortfolioService:
    def __init__(self, portfolio_repo: PortfolioRepository, audit_repo: AuditLogRepository) -> None:
        self._portfolio_repo = portfolio_repo
        self._audit_repo = audit_repo

    async def get_summary(self, context: UserContext) -> PortfolioSummaryRead:
        rows = await self._portfolio_repo.list_holdings(context)
        portfolio_value = sum(float(row["quantity"]) * float(row["last_price"]) for row in rows)
        invested = sum(float(row["quantity"]) * float(row["average_price"]) for row in rows)
        day_pnl = sum(float(row["day_pnl"]) for row in rows)
        total_pnl = sum(float(row["total_pnl"]) for row in rows)

        holdings = []
        sector_values: defaultdict[str, float] = defaultdict(float)
        asset_values: defaultdict[str, float] = defaultdict(float)
        for row in rows:
            market_value = float(row["quantity"]) * float(row["last_price"])
            allocation_pct = (market_value / portfolio_value * 100) if portfolio_value else 0
            sector = row["sector"] or "Unclassified"
            asset = row["asset_class"]
            sector_values[sector] += market_value
            asset_values[asset] += market_value
            holdings.append(
                HoldingRead(
                    symbol=row["symbol"],
                    exchange=row["exchange"],
                    company_name=row["company_name"],
                    sector=row["sector"],
                    asset_class=asset,
                    quantity=float(row["quantity"]),
                    average_price=float(row["average_price"]),
                    last_price=float(row["last_price"]),
                    market_value=market_value,
                    day_pnl=float(row["day_pnl"]),
                    total_pnl=float(row["total_pnl"]),
                    allocation_pct=allocation_pct,
                )
            )

        max_sector = max(sector_values.values(), default=0)
        concentration_penalty = int((max_sector / portfolio_value) * 20) if portfolio_value else 0
        health_score = max(0, min(100, 84 - concentration_penalty + (4 if total_pnl > 0 else -6)))
        await self._audit_repo.record(context, "portfolio.summary.read", "portfolio")

        ai_summary = self._build_ai_summary(
            holdings=holdings,
            portfolio_value=portfolio_value,
            day_pnl=day_pnl,
            total_pnl=total_pnl,
            total_pnl_pct=(total_pnl / max(invested, 1)) * 100,
            health_score=health_score,
            sector_values=sector_values,
        )

        return PortfolioSummaryRead(
            portfolio_value=portfolio_value,
            day_pnl=day_pnl,
            day_pnl_pct=(day_pnl / max(portfolio_value - day_pnl, 1)) * 100,
            total_pnl=total_pnl,
            total_pnl_pct=(total_pnl / max(invested, 1)) * 100,
            health_score=health_score,
            cash_balance=0.0,
            dividend_summary=0.0,
            ai_summary=ai_summary,
            holdings=holdings,
            sector_allocation=self._to_allocations(sector_values, portfolio_value),
            asset_allocation=self._to_allocations(asset_values, portfolio_value),
            recent_transactions=[],
            upcoming_events=[],
            updated_at=datetime.now(UTC),
        )

    async def import_manual_csv(self, context: UserContext, content: bytes) -> ManualPortfolioImportResponse:
        holdings, skipped_count = parse_portfolio_csv(content)
        await self._portfolio_repo.replace_holdings(context, holdings)
        await self._audit_repo.record(context, "portfolio.manual_csv.imported", "portfolio")
        return ManualPortfolioImportResponse(
            imported_count=len(holdings),
            skipped_count=skipped_count,
            message="Manual portfolio CSV imported successfully.",
        )

    def _to_allocations(self, values: dict[str, float], total: float) -> list[AllocationRead]:
        return [
            AllocationRead(label=label, value=value, percentage=(value / total * 100) if total else 0)
            for label, value in sorted(values.items(), key=lambda item: item[1], reverse=True)
        ]

    def _build_ai_summary(
        self,
        holdings: list[HoldingRead],
        portfolio_value: float,
        day_pnl: float,
        total_pnl: float,
        total_pnl_pct: float,
        health_score: int,
        sector_values: dict[str, float],
    ) -> str:
        if not holdings or portfolio_value <= 0:
            return "No holdings are available yet. Connect Zerodha through MCP or upload a CSV to generate portfolio insights."

        top_holding = max(holdings, key=lambda item: item.market_value)
        top_winner = max(holdings, key=lambda item: item.total_pnl)
        top_loser = min(holdings, key=lambda item: item.total_pnl)
        day_tone = "positive" if day_pnl >= 0 else "negative"
        total_tone = "profit" if total_pnl >= 0 else "loss"

        largest_sector_label = "Unclassified"
        largest_sector_value = 0.0
        if sector_values:
            largest_sector_label, largest_sector_value = max(sector_values.items(), key=lambda item: item[1])
        largest_sector_pct = (largest_sector_value / portfolio_value * 100) if portfolio_value else 0

        concentration_note = (
            f"{top_holding.symbol} is the largest holding at {top_holding.allocation_pct:.1f}%."
            if top_holding.allocation_pct < 20
            else f"{top_holding.symbol} is a concentrated position at {top_holding.allocation_pct:.1f}%."
        )
        sector_note = (
            f"Largest sector exposure is {largest_sector_label} at {largest_sector_pct:.1f}%."
            if largest_sector_label != "Unclassified"
            else f"{largest_sector_pct:.1f}% of the portfolio is missing sector classification."
        )
        risk_note = (
            "Risk looks controlled."
            if health_score >= 75
            else "Risk needs attention due to concentration or weak P&L profile."
        )

        return (
            f"Portfolio has {len(holdings)} holdings worth Rs {portfolio_value:,.0f}. "
            f"Today's P&L is {day_tone} at Rs {day_pnl:,.0f}, while overall P&L is a {total_tone} "
            f"of Rs {total_pnl:,.0f} ({total_pnl_pct:+.2f}%). "
            f"{concentration_note} {sector_note} "
            f"Top contributor is {top_winner.symbol}; weakest contributor is {top_loser.symbol}. "
            f"Health score is {health_score}/100. {risk_note}"
        )
