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
        await connection.execute(text("ALTER TABLE app_users ADD COLUMN IF NOT EXISTS password_hash TEXT"))
        await connection.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS app_users_email_unique_idx
                ON app_users (lower(email))
                WHERE email IS NOT NULL
                """
            )
        )
        await connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS auth_sessions (
                  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                  user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
                  token_hash TEXT NOT NULL UNIQUE,
                  user_agent TEXT,
                  expires_at TIMESTAMPTZ NOT NULL,
                  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                  revoked_at TIMESTAMPTZ
                )
                """
            )
        )
        await connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS auth_sessions_user_active_idx
                ON auth_sessions(user_id, expires_at)
                WHERE revoked_at IS NULL
                """
            )
        )
