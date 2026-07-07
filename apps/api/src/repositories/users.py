from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.auth import UserContext


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_context_by_external_id(self, external_auth_id: str) -> UserContext | None:
        result = await self._session.execute(
            text(
                """
                SELECT tenant_id, id AS user_id, external_auth_id
                FROM app_users
                WHERE external_auth_id = :external_auth_id
                """
            ),
            {"external_auth_id": external_auth_id},
        )
        row = result.mappings().first()
        if row is None:
            return None
        return UserContext(
            tenant_id=row["tenant_id"],
            user_id=row["user_id"],
            external_auth_id=row["external_auth_id"],
        )

    async def list_contexts_with_holdings(self) -> list[UserContext]:
        result = await self._session.execute(
            text(
                """
                SELECT DISTINCT users.tenant_id, users.id AS user_id, users.external_auth_id
                FROM app_users users
                JOIN holdings ON holdings.tenant_id = users.tenant_id AND holdings.user_id = users.id
                ORDER BY users.external_auth_id
                """
            )
        )
        return [
            UserContext(
                tenant_id=row["tenant_id"],
                user_id=row["user_id"],
                external_auth_id=row["external_auth_id"],
            )
            for row in result.mappings().all()
        ]
