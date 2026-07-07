from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.auth import UserContext


class BrokerConnectionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_zerodha_status(self, context: UserContext) -> dict | None:
        result = await self._session.execute(
            text(
                """
                SELECT broker, status, last_synced_at, scopes
                FROM broker_connections
                WHERE tenant_id = :tenant_id
                  AND user_id = :user_id
                  AND broker = 'zerodha'
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"tenant_id": context.tenant_id, "user_id": context.user_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def mark_zerodha_connecting(self, context: UserContext) -> None:
        await self._upsert_zerodha_status(context, "connecting", update_last_synced=False)

    async def mark_zerodha_synced(self, context: UserContext) -> None:
        await self._upsert_zerodha_status(context, "connected", update_last_synced=True)

    async def _upsert_zerodha_status(
        self,
        context: UserContext,
        status: str,
        update_last_synced: bool,
    ) -> None:
        await self._session.execute(
            text(
                """
                INSERT INTO broker_connections (
                    tenant_id, user_id, broker, status, scopes, last_synced_at, updated_at
                )
                VALUES (
                    :tenant_id,
                    :user_id,
                    'zerodha',
                    :status,
                    ARRAY['read:portfolio', 'read:orders', 'read:positions', 'read:quotes'],
                    CASE WHEN :update_last_synced THEN now() ELSE NULL END,
                    now()
                )
                ON CONFLICT DO NOTHING
                """
            ),
            {
                "tenant_id": context.tenant_id,
                "user_id": context.user_id,
                "status": status,
                "update_last_synced": update_last_synced,
            },
        )
        await self._session.execute(
            text(
                """
                UPDATE broker_connections
                SET status = :status,
                    last_synced_at = CASE
                        WHEN :update_last_synced THEN now()
                        ELSE last_synced_at
                    END,
                    updated_at = now()
                WHERE id = (
                    SELECT id
                    FROM broker_connections
                    WHERE tenant_id = :tenant_id
                      AND user_id = :user_id
                      AND broker = 'zerodha'
                    ORDER BY created_at DESC
                    LIMIT 1
                )
                """
            ),
            {
                "tenant_id": context.tenant_id,
                "user_id": context.user_id,
                "status": status,
                "update_last_synced": update_last_synced,
            },
        )
        await self._session.commit()
