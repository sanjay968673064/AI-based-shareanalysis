from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

AiProvider = Literal["gemini", "openai"]


class OpenAiSettingsRead(BaseModel):
    configured: bool
    provider: AiProvider
    masked_key: str | None = Field(default=None, serialization_alias="maskedKey")
    model: str


class OpenAiSettingsUpdate(BaseModel):
    api_key: str = Field(min_length=20, alias="apiKey")
    provider: AiProvider = "gemini"
    model: str | None = None


class AiAnalyticsInsightRead(BaseModel):
    configured: bool
    provider: AiProvider | None = None
    generated_at: datetime | None = Field(default=None, serialization_alias="generatedAt")
    model: str | None = None
    summary: str
    buy_focus: list[str] = Field(default_factory=list, serialization_alias="buyFocus")
    hold_focus: list[str] = Field(default_factory=list, serialization_alias="holdFocus")
    sell_or_review_focus: list[str] = Field(default_factory=list, serialization_alias="sellOrReviewFocus")
    risk_controls: list[str] = Field(default_factory=list, serialization_alias="riskControls")
    data_warnings: list[str] = Field(default_factory=list, serialization_alias="dataWarnings")
