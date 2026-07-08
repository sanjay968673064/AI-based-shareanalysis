from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DiscoveryCandidateRead(BaseModel):
    symbol: str
    company_name: str = Field(serialization_alias="companyName")
    sector: str | None = None
    industry: str | None = None
    last_price: float | None = Field(default=None, serialization_alias="lastPrice")
    discovery_score: int = Field(serialization_alias="discoveryScore")
    conviction: Literal["High", "Medium", "Low"]
    risk_level: Literal["Low", "Medium", "High"] = Field(serialization_alias="riskLevel")
    recommendation: str
    why_buy: list[str] = Field(serialization_alias="whyBuy")
    company_potential: list[str] = Field(serialization_alias="companyPotential")
    risks: list[str]
    entry_discipline: str = Field(serialization_alias="entryDiscipline")
    verification_triggers: list[str] = Field(serialization_alias="verificationTriggers")
    research_view: str = Field(serialization_alias="researchView")
    data_quality_score: int = Field(serialization_alias="dataQualityScore")
    source_notes: list[str] = Field(serialization_alias="sourceNotes")


class StockDiscoveryRead(BaseModel):
    generated_at: datetime = Field(serialization_alias="generatedAt")
    universe: str
    methodology: str
    candidates: list[DiscoveryCandidateRead]
    excluded_symbols: list[str] = Field(serialization_alias="excludedSymbols")
    warnings: list[str]
