from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.auth import UserContext


class AppSettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, context: UserContext, key: str) -> str | None:
        result = await self._session.execute(
            text(
                """
                SELECT setting_value_ciphertext
                FROM app_settings
                WHERE tenant_id = :tenant_id
                  AND user_id = :user_id
                  AND setting_key = :key
                LIMIT 1
                """
            ),
            {"tenant_id": context.tenant_id, "user_id": context.user_id, "key": key},
        )
        row = result.mappings().first()
        return row["setting_value_ciphertext"] if row else None

    async def upsert(self, context: UserContext, key: str, encrypted_value: str) -> None:
        await self._session.execute(
            text(
                """
                INSERT INTO app_settings (
                    tenant_id, user_id, setting_key, setting_value_ciphertext, updated_at
                )
                VALUES (:tenant_id, :user_id, :key, :encrypted_value, now())
                ON CONFLICT (tenant_id, user_id, setting_key)
                DO UPDATE SET
                    setting_value_ciphertext = EXCLUDED.setting_value_ciphertext,
                    updated_at = now()
                """
            ),
            {
                "tenant_id": context.tenant_id,
                "user_id": context.user_id,
                "key": key,
                "encrypted_value": encrypted_value,
            },
        )
        await self._session.commit()

    async def delete(self, context: UserContext, key: str) -> None:
        await self._session.execute(
            text(
                """
                DELETE FROM app_settings
                WHERE tenant_id = :tenant_id
                  AND user_id = :user_id
                  AND setting_key = :key
                """
            ),
            {"tenant_id": context.tenant_id, "user_id": context.user_id, "key": key},
        )
        await self._session.commit()
