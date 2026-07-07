from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.auth import UserContext


class AuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(self, context: UserContext, action: str, resource_type: str) -> None:
        await self._session.execute(
            text(
                """
                INSERT INTO audit_logs (tenant_id, user_id, action, resource_type)
                VALUES (:tenant_id, :user_id, :action, :resource_type)
                """
            ),
            {
                "tenant_id": context.tenant_id,
                "user_id": context.user_id,
                "action": action,
                "resource_type": resource_type,
            },
        )
        await self._session.commit()
