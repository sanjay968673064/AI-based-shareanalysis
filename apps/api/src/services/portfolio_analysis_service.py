from collections import defaultdict

from src.schemas.intelligence import PortfolioMetricsRead


class PortfolioAnalysisService:
    def analyze(self, holdings: list[dict]) -> tuple[PortfolioMetricsRead, dict[str, float], dict[str, float]]:
        portfolio_value = sum(float(row["quantity"]) * float(row["last_price"]) for row in holdings)
        invested = sum(float(row["quantity"]) * float(row["average_price"]) for row in holdings)
        total_pnl = sum(float(row["total_pnl"]) for row in holdings)
        day_pnl = sum(float(row["day_pnl"]) for row in holdings)
        weights = {
            row["symbol"]: (float(row["quantity"]) * float(row["last_price"]) / portfolio_value * 100)
            if portfolio_value
            else 0
            for row in holdings
        }
        sector_values: defaultdict[str, float] = defaultdict(float)
        for row in holdings:
            sector_values[row["sector"] or "Unclassified"] += float(row["quantity"]) * float(row["last_price"])

        diversification_score = self._diversification_score(weights, sector_values, portfolio_value)
        concentration_penalty = max(weights.values(), default=0) * 0.8
        missing_sector_penalty = (sector_values.get("Unclassified", 0) / portfolio_value * 20) if portfolio_value else 20
        pnl_bonus = 8 if total_pnl > 0 else -8
        health_score = int(max(0, min(100, diversification_score - concentration_penalty - missing_sector_penalty + pnl_bonus)))

        return (
            PortfolioMetricsRead(
                portfolio_value=portfolio_value,
                invested_value=invested,
                total_pnl=total_pnl,
                total_return_pct=(total_pnl / max(invested, 1)) * 100,
                day_pnl=day_pnl,
                xirr=None,
                cagr=None,
                volatility=None,
                beta=None,
                sharpe_ratio=None,
                maximum_drawdown=None,
                diversification_score=diversification_score,
                health_score=health_score,
            ),
            weights,
            dict(sector_values),
        )

    def _diversification_score(self, weights: dict[str, float], sector_values: dict[str, float], total: float) -> int:
        if not weights:
            return 0
        position_count_score = min(40, len(weights) * 2)
        max_weight_penalty = max(0, max(weights.values()) - 10) * 1.2
        sector_pct = max(sector_values.values(), default=0) / total * 100 if total else 100
        sector_penalty = max(0, sector_pct - 35) * 0.6
        return int(max(0, min(100, 70 + position_count_score - max_weight_penalty - sector_penalty)))
