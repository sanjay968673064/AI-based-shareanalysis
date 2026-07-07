from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


RecommendationLabel = Literal[
    "Strong Buy",
    "Buy More",
    "Accumulate",
    "Hold",
    "Reduce",
    "Book Partial Profit",
    "Exit",
]


class DataQualityRead(BaseModel):
    score: int
    warnings: list[str]


class PortfolioMetricsRead(BaseModel):
    portfolio_value: float = Field(serialization_alias="portfolioValue")
    invested_value: float = Field(serialization_alias="investedValue")
    total_pnl: float = Field(serialization_alias="totalPnl")
    total_return_pct: float = Field(serialization_alias="totalReturnPct")
    day_pnl: float = Field(serialization_alias="dayPnl")
    xirr: float | None = None
    cagr: float | None = None
    volatility: float | None = None
    beta: float | None = None
    sharpe_ratio: float | None = Field(default=None, serialization_alias="sharpeRatio")
    maximum_drawdown: float | None = Field(default=None, serialization_alias="maximumDrawdown")
    diversification_score: int = Field(serialization_alias="diversificationScore")
    health_score: int = Field(serialization_alias="healthScore")


class FundamentalAnalysisRead(BaseModel):
    pe: float | None = None
    forward_pe: float | None = Field(default=None, serialization_alias="forwardPe")
    pb: float | None = None
    peg: float | None = None
    eps: float | None = None
    book_value: float | None = Field(default=None, serialization_alias="bookValue")
    revenue_growth: float | None = Field(default=None, serialization_alias="revenueGrowth")
    profit_growth: float | None = Field(default=None, serialization_alias="profitGrowth")
    operating_margin: float | None = Field(default=None, serialization_alias="operatingMargin")
    net_margin: float | None = Field(default=None, serialization_alias="netMargin")
    roe: float | None = None
    roce: float | None = None
    debt_to_equity: float | None = Field(default=None, serialization_alias="debtToEquity")
    dividend_yield: float | None = Field(default=None, serialization_alias="dividendYield")
    intrinsic_value: float | None = Field(default=None, serialization_alias="intrinsicValue")
    margin_of_safety: float | None = Field(default=None, serialization_alias="marginOfSafety")
    score: int
    notes: list[str]


class TechnicalAnalysisRead(BaseModel):
    rsi_14: float | None = Field(default=None, serialization_alias="rsi14")
    macd: float | None = None
    signal_line: float | None = Field(default=None, serialization_alias="signalLine")
    ema_20: float | None = Field(default=None, serialization_alias="ema20")
    ema_50: float | None = Field(default=None, serialization_alias="ema50")
    ema_100: float | None = Field(default=None, serialization_alias="ema100")
    ema_200: float | None = Field(default=None, serialization_alias="ema200")
    atr: float | None = None
    adx: float | None = None
    support_levels: list[float] = Field(serialization_alias="supportLevels")
    resistance_levels: list[float] = Field(serialization_alias="resistanceLevels")
    trend_direction: str = Field(serialization_alias="trendDirection")
    momentum_score: int = Field(serialization_alias="momentumScore")
    notes: list[str]


class NewsAnalysisRead(BaseModel):
    sentiment_score: int = Field(serialization_alias="sentimentScore")
    trusted_items: list[str] = Field(serialization_alias="trustedItems")
    notes: list[str]


class StockRecommendationRead(BaseModel):
    symbol: str
    company_name: str = Field(serialization_alias="companyName")
    recommendation: RecommendationLabel
    confidence_score: int = Field(serialization_alias="confidenceScore")
    risk_score: int = Field(serialization_alias="riskScore")
    expected_upside: float = Field(serialization_alias="expectedUpside")
    expected_downside: float = Field(serialization_alias="expectedDownside")
    suggested_holding_period: str = Field(serialization_alias="suggestedHoldingPeriod")
    target_allocation: float = Field(serialization_alias="targetAllocation")
    reasoning: str
    bullish_factors: list[str] = Field(serialization_alias="bullishFactors")
    bearish_factors: list[str] = Field(serialization_alias="bearishFactors")
    key_risks: list[str] = Field(serialization_alias="keyRisks")
    what_changed: str = Field(serialization_alias="whatChanged")
    fundamental: FundamentalAnalysisRead
    technical: TechnicalAnalysisRead
    news: NewsAnalysisRead


class PortfolioOptimizationRead(BaseModel):
    overweight_positions: list[str] = Field(serialization_alias="overweightPositions")
    underweight_positions: list[str] = Field(serialization_alias="underweightPositions")
    weak_holdings: list[str] = Field(serialization_alias="weakHoldings")
    high_risk_stocks: list[str] = Field(serialization_alias="highRiskStocks")
    duplicate_sector_exposure: list[str] = Field(serialization_alias="duplicateSectorExposure")
    cash_allocation_suggestion: str = Field(serialization_alias="cashAllocationSuggestion")


class PortfolioAlertRead(BaseModel):
    severity: Literal["low", "medium", "high"]
    alert_type: str = Field(serialization_alias="alertType")
    symbol: str | None = None
    message: str
    action: str


class MarketAnalysisRead(BaseModel):
    nifty_trend: str = Field(serialization_alias="niftyTrend")
    bank_nifty_trend: str = Field(serialization_alias="bankNiftyTrend")
    india_vix: float | None = Field(default=None, serialization_alias="indiaVix")
    notes: list[str]


class PortfolioIntelligenceRead(BaseModel):
    generated_at: datetime = Field(serialization_alias="generatedAt")
    portfolio_metrics: PortfolioMetricsRead = Field(serialization_alias="portfolioMetrics")
    market_analysis: MarketAnalysisRead = Field(serialization_alias="marketAnalysis")
    recommendations: list[StockRecommendationRead]
    optimization: PortfolioOptimizationRead
    alerts: list[PortfolioAlertRead]
    data_quality: DataQualityRead = Field(serialization_alias="dataQuality")


class IntelligenceReportRead(BaseModel):
    report_type: str = Field(serialization_alias="reportType")
    generated_at: datetime = Field(serialization_alias="generatedAt")
    summary: str
    sections: dict


class RecommendationHistoryRead(BaseModel):
    symbol: str
    recommendation: str
    confidence_score: float = Field(serialization_alias="confidenceScore")
    risk_score: float = Field(serialization_alias="riskScore")
    price_at_recommendation: float = Field(serialization_alias="priceAtRecommendation")
    current_outcome: str = Field(serialization_alias="currentOutcome")
    created_at: datetime = Field(serialization_alias="createdAt")
