from src.schemas.intelligence import (
    FundamentalAnalysisRead,
    NewsAnalysisRead,
    StockRecommendationRead,
    TechnicalAnalysisRead,
)
from src.services.alerting_service import AlertingService


def test_alerting_service_flags_high_risk_and_concentration() -> None:
    service = AlertingService()
    recommendation = StockRecommendationRead(
        symbol="SBIN",
        company_name="State Bank of India",
        recommendation="Reduce",
        confidence_score=45,
        risk_score=80,
        expected_upside=4,
        expected_downside=-20,
        suggested_holding_period="3-12 months",
        target_allocation=10,
        reasoning="test",
        bullish_factors=[],
        bearish_factors=[],
        key_risks=[],
        what_changed="test",
        fundamental=FundamentalAnalysisRead(score=50, notes=[]),
        technical=TechnicalAnalysisRead(
            support_levels=[750],
            resistance_levels=[850],
            trend_direction="downtrend",
            momentum_score=35,
            notes=[],
        ),
        news=NewsAnalysisRead(sentiment_score=0, trusted_items=[], notes=[]),
    )

    alerts = service.generate(
        holdings=[
            {
                "symbol": "SBIN",
                "quantity": 10,
                "last_price": 800,
                "day_pnl": -400,
            }
        ],
        recommendations=[recommendation],
        weights={"SBIN": 30},
        sector_values={"Banks": 8000},
        portfolio_value=8000,
        snapshot_warnings={},
    )

    alert_types = {alert.alert_type for alert in alerts}
    assert "risk_reduction" in alert_types
    assert "position_concentration" in alert_types
    assert "sector_concentration" in alert_types
    assert alerts[0].severity == "high"
