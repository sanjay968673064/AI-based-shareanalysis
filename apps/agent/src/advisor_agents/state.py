from typing import Literal, TypedDict


RecommendationLabel = Literal["Strong Buy", "Buy More", "Hold", "Reduce", "Book Profit", "Exit"]


class AgentFinding(TypedDict):
    agent: str
    summary: str
    confidence_score: float
    risk_score: float


class Recommendation(TypedDict):
    symbol: str
    label: RecommendationLabel
    reason: str
    confidence_score: float
    risk_score: float
    expected_upside: float
    expected_downside: float
    target_price: float
    stop_loss: float
    horizon: str


class AdvisorState(TypedDict):
    tenant_id: str
    user_id: str
    portfolio_snapshot: dict
    findings: list[AgentFinding]
    recommendations: list[Recommendation]
