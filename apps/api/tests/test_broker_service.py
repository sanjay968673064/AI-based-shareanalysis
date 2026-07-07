from datetime import UTC, datetime
from uuid import UUID

import pytest

from src.domain.auth import UserContext
from src.integrations.kite_mcp import _normalize_mcp_holding
from src.schemas.zerodha import ReadOnlyConnectRequest
from src.services.broker_service import BrokerService


class BrokerRepo:
    def __init__(self) -> None:
        self.connecting = False
        self.synced = False

    async def get_zerodha_status(self, context: UserContext) -> dict:
        return {
            "broker": "zerodha",
            "status": "connected",
            "last_synced_at": datetime(2026, 1, 1, tzinfo=UTC),
            "scopes": ["read:portfolio", "read:quotes"],
        }

    async def mark_zerodha_connecting(self, context: UserContext) -> None:
        self.connecting = True

    async def mark_zerodha_synced(self, context: UserContext) -> None:
        self.synced = True


class AuditRepo:
    async def record(self, context: UserContext, action: str, resource_type: str) -> None:
        return None


class PortfolioRepo:
    def __init__(self) -> None:
        self.holdings = []

    async def replace_holdings(self, context: UserContext, holdings: list[dict]) -> None:
        self.holdings = holdings


class KiteClient:
    async def create_read_only_authorization_url(self, user_reference: str, account_label: str) -> str:
        return f"https://kite.zerodha.com/connect/login?v=3&api_key=test&redirect_params={user_reference}"

    async def create_mcp_authorization_url(self, user_reference: str) -> str:
        return "https://kite.zerodha.com/connect/login?mcp=1"

    async def fetch_mcp_holdings(self, user_reference: str) -> list[dict]:
        return [
            {
                "symbol": "INFY",
                "exchange": "NSE",
                "company_name": "Infosys",
                "sector": None,
                "asset_class": "equity",
                "quantity": 2,
                "average_price": 1400,
                "last_price": 1500,
                "day_pnl": 10,
                "total_pnl": 200,
            }
        ]


@pytest.mark.asyncio
async def test_zerodha_status_is_read_only() -> None:
    service = BrokerService(BrokerRepo(), PortfolioRepo(), AuditRepo(), KiteClient())
    context = UserContext(
        tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
        user_id=UUID("00000000-0000-0000-0000-000000000101"),
        external_auth_id="demo-user",
    )

    status = await service.get_zerodha_status(context)

    assert status.read_only is True
    assert status.status == "connected"


@pytest.mark.asyncio
async def test_read_only_connection_returns_kite_login_url() -> None:
    service = BrokerService(BrokerRepo(), PortfolioRepo(), AuditRepo(), KiteClient())
    context = UserContext(
        tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
        user_id=UUID("00000000-0000-0000-0000-000000000101"),
        external_auth_id="demo-user",
    )

    response = await service.create_read_only_connection(
        context,
        ReadOnlyConnectRequest(zerodhaUserId="AB1234", accountLabel="Primary Zerodha"),
    )

    assert response.read_only is True
    assert "api_key=test" in response.authorization_url


@pytest.mark.asyncio
async def test_mcp_sync_replaces_holdings() -> None:
    broker_repo = BrokerRepo()
    portfolio_repo = PortfolioRepo()
    service = BrokerService(broker_repo, portfolio_repo, AuditRepo(), KiteClient())
    context = UserContext(
        tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
        user_id=UUID("00000000-0000-0000-0000-000000000101"),
        external_auth_id="demo-user",
    )

    response = await service.sync_mcp_holdings(context)

    assert response.imported_count == 1
    assert portfolio_repo.holdings[0]["symbol"] == "INFY"
    assert broker_repo.synced is True


def test_normalize_mcp_holding_from_kite_shape() -> None:
    holding = _normalize_mcp_holding(
        {
            "tradingsymbol": "SBIN",
            "exchange": "NSE",
            "quantity": 5,
            "average_price": 700,
            "last_price": 755,
            "pnl": 275,
            "day_change_percentage": 1.5,
        }
    )

    assert holding is not None
    assert holding["symbol"] == "SBIN"
    assert holding["day_pnl"] == 56.625
