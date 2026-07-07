from datetime import datetime

from pydantic import BaseModel, Field


class HoldingRead(BaseModel):
    symbol: str
    company_name: str = Field(serialization_alias="companyName")
    exchange: str
    sector: str | None
    asset_class: str = Field(serialization_alias="assetClass")
    quantity: float
    average_price: float = Field(serialization_alias="averagePrice")
    last_price: float = Field(serialization_alias="lastPrice")
    market_value: float = Field(serialization_alias="marketValue")
    day_pnl: float = Field(serialization_alias="dayPnl")
    total_pnl: float = Field(serialization_alias="totalPnl")
    allocation_pct: float = Field(serialization_alias="allocationPct")


class AllocationRead(BaseModel):
    label: str
    value: float
    percentage: float


class PortfolioSummaryRead(BaseModel):
    portfolio_value: float = Field(serialization_alias="portfolioValue")
    day_pnl: float = Field(serialization_alias="dayPnl")
    day_pnl_pct: float = Field(serialization_alias="dayPnlPct")
    total_pnl: float = Field(serialization_alias="totalPnl")
    total_pnl_pct: float = Field(serialization_alias="totalPnlPct")
    health_score: int = Field(serialization_alias="healthScore")
    cash_balance: float = Field(serialization_alias="cashBalance")
    dividend_summary: float = Field(serialization_alias="dividendSummary")
    ai_summary: str = Field(serialization_alias="aiSummary")
    holdings: list[HoldingRead]
    sector_allocation: list[AllocationRead] = Field(serialization_alias="sectorAllocation")
    asset_allocation: list[AllocationRead] = Field(serialization_alias="assetAllocation")
    recent_transactions: list[str] = Field(serialization_alias="recentTransactions")
    upcoming_events: list[str] = Field(serialization_alias="upcomingEvents")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class ManualPortfolioImportResponse(BaseModel):
    imported_count: int = Field(serialization_alias="importedCount")
    skipped_count: int = Field(serialization_alias="skippedCount")
    message: str
