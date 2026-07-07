from src.domain.auth import UserContext
from src.integrations.kite_mcp import BrokerPortfolioClient
from src.repositories.audit import AuditLogRepository
from src.repositories.broker_connections import BrokerConnectionRepository
from src.repositories.portfolio import PortfolioRepository
from src.schemas.zerodha import (
    BrokerStatusRead,
    McpConnectResponse,
    McpSyncResponse,
    ReadOnlyConnectRequest,
    ReadOnlyConnectResponse,
)


class BrokerService:
    def __init__(
        self,
        broker_repo: BrokerConnectionRepository,
        portfolio_repo: PortfolioRepository,
        audit_repo: AuditLogRepository,
        kite_client: BrokerPortfolioClient,
    ) -> None:
        self._broker_repo = broker_repo
        self._portfolio_repo = portfolio_repo
        self._audit_repo = audit_repo
        self._kite_client = kite_client

    async def get_zerodha_status(self, context: UserContext) -> BrokerStatusRead:
        status = await self._broker_repo.get_zerodha_status(context)
        scopes = status["scopes"] if status else []
        return BrokerStatusRead(
            broker="zerodha",
            status=status["status"] if status else "disconnected",
            read_only="trade:execute" not in scopes,
            last_synced_at=status["last_synced_at"] if status else None,
        )

    async def create_read_only_connection(
        self, context: UserContext, request: ReadOnlyConnectRequest
    ) -> ReadOnlyConnectResponse:
        url = await self._kite_client.create_read_only_authorization_url(
            context.external_auth_id, request.account_label
        )
        await self._audit_repo.record(context, "zerodha.read_only_connect.started", "broker_connection")
        return ReadOnlyConnectResponse(
            authorization_url=url,
            message="Open this URL to connect Zerodha with read-only portfolio permissions.",
        )

    async def create_mcp_connection(self, context: UserContext) -> McpConnectResponse:
        url = await self._kite_client.create_mcp_authorization_url(context.external_auth_id)
        await self._broker_repo.mark_zerodha_connecting(context)
        await self._audit_repo.record(context, "zerodha.mcp_connect.started", "broker_connection")
        return McpConnectResponse(
            authorization_url=url,
            message="Open this URL, approve Kite MCP on Zerodha, then return to this app tab and sync holdings.",
        )

    async def sync_mcp_holdings(self, context: UserContext) -> McpSyncResponse:
        holdings = await self._kite_client.fetch_mcp_holdings(context.external_auth_id)
        await self._portfolio_repo.replace_holdings(context, holdings)
        await self._broker_repo.mark_zerodha_synced(context)
        await self._audit_repo.record(context, "zerodha.mcp_holdings.synced", "portfolio")
        return McpSyncResponse(
            imported_count=len(holdings),
            skipped_count=0,
            message="Zerodha holdings synced through Kite MCP.",
        )
