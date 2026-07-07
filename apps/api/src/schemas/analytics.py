from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


Tone = Literal["good", "watch", "bad", "neutral"]
SanityStatus = Literal["pass", "watch", "fail"]


class AnalyticsMetricRead(BaseModel):
    label: str
    value: str
    detail: str | None = None
    tone: Tone = "neutral"


class CompanyNewsRead(BaseModel):
    title: str
    publisher: str | None = None
    link: str | None = None
    published_at: datetime | None = Field(default=None, serialization_alias="publishedAt")


class CompanyAnalyticsRead(BaseModel):
    symbol: str
    company_name: str = Field(serialization_alias="companyName")
    sector: str | None = None
    industry: str | None = None
    currency: str | None = None
    last_price: float | None = Field(default=None, serialization_alias="lastPrice")
    day_change_pct: float | None = Field(default=None, serialization_alias="dayChangePct")
    fifty_two_week_low: float | None = Field(default=None, serialization_alias="fiftyTwoWeekLow")
    fifty_two_week_high: float | None = Field(default=None, serialization_alias="fiftyTwoWeekHigh")
    business_summary: str = Field(serialization_alias="businessSummary")
    overall_score: int = Field(serialization_alias="overallScore")
    balance_sheet_score: int = Field(serialization_alias="balanceSheetScore")
    growth_score: int = Field(serialization_alias="growthScore")
    cash_flow_score: int = Field(serialization_alias="cashFlowScore")
    valuation_score: int = Field(serialization_alias="valuationScore")
    recommendation: str
    planning: str
    strengths: list[str]
    concerns: list[str]
    financials: list[AnalyticsMetricRead]
    news: list[CompanyNewsRead]
    source_notes: list[str] = Field(serialization_alias="sourceNotes")


class DecisionSignalRead(BaseModel):
    symbol: str
    action: str
    confidence: int
    conviction_score: int = Field(serialization_alias="convictionScore")
    risk_flags: list[str] = Field(serialization_alias="riskFlags")
    entry_discipline: str = Field(serialization_alias="entryDiscipline")
    exit_guard: str = Field(serialization_alias="exitGuard")
    reasoning: str


class AnalyticsSanityCheckRead(BaseModel):
    label: str
    status: SanityStatus
    detail: str


class PortfolioAnalyticsRead(BaseModel):
    generated_at: datetime = Field(serialization_alias="generatedAt")
    cached_for_date: date = Field(serialization_alias="cachedForDate")
    next_refresh_at: datetime = Field(serialization_alias="nextRefreshAt")
    model_version: str = Field(serialization_alias="modelVersion")
    data_quality_score: int = Field(serialization_alias="dataQualityScore")
    summary: str
    companies: list[CompanyAnalyticsRead]
    decision_signals: list[DecisionSignalRead] = Field(serialization_alias="decisionSignals")
    sanity_checks: list[AnalyticsSanityCheckRead] = Field(serialization_alias="sanityChecks")
    warnings: list[str]
