from src.schemas.intelligence import FundamentalAnalysisRead, NewsAnalysisRead, TechnicalAnalysisRead
from src.services.recommendation_engine import RecommendationEngine


def test_recommendation_engine_outputs_explainable_label() -> None:
    engine = RecommendationEngine()
    recommendation = engine.recommend(
        holding={
            "symbol": "SBIN",
            "company_name": "State Bank of India",
            "average_price": 700,
            "last_price": 800,
            "quantity": 10,
        },
        allocation_pct=22,
        fundamental=FundamentalAnalysisRead(score=60, notes=["fundamentals missing"]),
        technical=TechnicalAnalysisRead(
            support_levels=[760],
            resistance_levels=[860],
            trend_direction="uptrend",
            momentum_score=65,
            notes=["history missing"],
        ),
        news=NewsAnalysisRead(sentiment_score=0, trusted_items=[], notes=["news missing"]),
        previous=None,
    )

    assert recommendation.recommendation == "Book Partial Profit"
    assert recommendation.confidence_score < 70
    assert "missing-data penalties" in recommendation.reasoning
