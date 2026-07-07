from sqlalchemy import text

from src.db.session import engine


async def ensure_runtime_schema() -> None:
    async with engine.begin() as connection:
        await connection.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
        await connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS app_settings (
                  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                  user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
                  setting_key TEXT NOT NULL,
                  setting_value_ciphertext TEXT NOT NULL,
                  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                  UNIQUE (tenant_id, user_id, setting_key)
                )
                """
            )
        )
        await connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS app_settings_tenant_user_idx
                ON app_settings(tenant_id, user_id)
                """
            )
        )
