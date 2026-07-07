from src.schemas.portfolio import HoldingRead
from src.services.portfolio_service import PortfolioService


def test_ai_summary_uses_actual_portfolio_data() -> None:
    service = PortfolioService(portfolio_repo=None, audit_repo=None)
    holdings = [
        HoldingRead(
            symbol="SBIN",
            company_name="State Bank of India",
            exchange="NSE",
            sector="Banks",
            asset_class="equity",
            quantity=10,
            average_price=700,
            last_price=800,
            market_value=8000,
            day_pnl=120,
            total_pnl=1000,
            allocation_pct=80,
        ),
        HoldingRead(
            symbol="INFY",
            company_name="Infosys",
            exchange="NSE",
            sector="IT",
            asset_class="equity",
            quantity=2,
            average_price=1500,
            last_price=1000,
            market_value=2000,
            day_pnl=-40,
            total_pnl=-1000,
            allocation_pct=20,
        ),
    ]

    summary = service._build_ai_summary(
        holdings=holdings,
        portfolio_value=10000,
        day_pnl=80,
        total_pnl=0,
        total_pnl_pct=0,
        health_score=70,
        sector_values={"Banks": 8000, "IT": 2000},
    )

    assert "SBIN" in summary
    assert "INFY" in summary
    assert "Portfolio has 2 holdings" in summary
    assert "Financials and auto exposure" not in summary
