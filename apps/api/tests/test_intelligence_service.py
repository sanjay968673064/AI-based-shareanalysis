from uuid import UUID

import pytest

from src.domain.auth import UserContext
from src.services.intelligence_providers import MarketSnapshot, ProviderState
from src.services.intelligence_service import IntelligenceService


class PortfolioRepo:
    async def list_holdings(self, context: UserContext) -> list[dict]:
        return [
            {
                "symbol": "SBIN",
                "exchange": "NSE",
                "company_name": "State Bank of India",
                "sector": "Banks",
                "asset_class": "equity",
                "quantity": 10,
                "average_price": 700,
                "last_price": 800,
                "day_pnl": 50,
                "total_pnl": 1000,
                "updated_at": None,
            },
            {
                "symbol": "INFY",
                "exchange": "NSE",
                "company_name": "Infosys",
                "sector": "IT",
                "asset_class": "equity",
                "quantity": 2,
                "average_price": 1500,
                "last_price": 1000,
                "day_pnl": -20,
                "total_pnl": -1000,
                "updated_at": None,
            },
        ]


class HistoryRepo:
    def __init__(self) -> None:
        self.saved = []

    async def latest_by_symbol(self, context: UserContext) -> dict:
        return {}

    async def save_many(self, context: UserContext, recommendations: list, price_by_symbol: dict) -> None:
        self.saved = recommendations

    async def list_history(self, context: UserContext) -> list:
        return []


class AuditRepo:
    async def record(self, context: UserContext, action: str, resource_type: str) -> None:
        return None


class Provider:
    async def state(self) -> ProviderState:
        return ProviderState(available=True, notes=["test market data enabled"])

    async def fetch_many(self, holdings: list[dict]) -> dict[str, MarketSnapshot]:
        return {
            holding["symbol"]: MarketSnapshot(
                symbol=holding["symbol"],
                provider_symbol=f"{holding['symbol']}.NS",
                last_price=float(holding["last_price"]),
                previous_close=float(holding["last_price"]) * 0.99,
                closes=[float(holding["last_price"]) + index for index in range(-60, 1)],
                highs=[float(holding["last_price"]) + index + 2 for index in range(-60, 1)],
                lows=[float(holding["last_price"]) + index - 2 for index in range(-60, 1)],
                volumes=[1000 + index for index in range(61)],
                source="test",
            )
            for holding in holdings
        }


@pytest.mark.asyncio
async def test_intelligence_service_recommends_every_holding() -> None:
    history = HistoryRepo()
    service = IntelligenceService(PortfolioRepo(), history, AuditRepo())
    service._provider = Provider()
    context = UserContext(
        tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
        user_id=UUID("00000000-0000-0000-0000-000000000101"),
        external_auth_id="demo-user",
    )

    result = await service.analyze(context, persist=True)

    assert len(result.recommendations) == 2
    assert len(history.saved) == 2
    assert result.data_quality.score >= 80
    assert isinstance(result.alerts, list)
    assert result.portfolio_metrics.health_score >= 0
