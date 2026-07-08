from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import hash_password, hash_session_token, verify_password
from src.domain.auth import UserContext


SESSION_DAYS = 14


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_context_by_external_id(self, external_auth_id: str) -> UserContext | None:
        result = await self._session.execute(
            text(
                """
                SELECT tenant_id, id AS user_id, external_auth_id, email, full_name
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
            email=row["email"],
            full_name=row["full_name"],
        )

    async def get_context_by_session_token(self, token: str) -> UserContext | None:
        result = await self._session.execute(
            text(
                """
                SELECT users.tenant_id, users.id AS user_id, users.external_auth_id, users.email, users.full_name
                FROM auth_sessions sessions
                JOIN app_users users ON users.id = sessions.user_id AND users.tenant_id = sessions.tenant_id
                WHERE sessions.token_hash = :token_hash
                  AND sessions.revoked_at IS NULL
                  AND sessions.expires_at > now()
                """
            ),
            {"token_hash": hash_session_token(token)},
        )
        row = result.mappings().first()
        if row is None:
            return None
        return UserContext(
            tenant_id=row["tenant_id"],
            user_id=row["user_id"],
            external_auth_id=row["external_auth_id"],
            email=row["email"],
            full_name=row["full_name"],
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

    async def create_user_with_tenant(
        self,
        email: str,
        password: str,
        full_name: str,
    ) -> UserContext:
        normalized_email = email.strip().lower()
        existing = await self._session.execute(
            text("SELECT id FROM app_users WHERE lower(email) = :email"),
            {"email": normalized_email},
        )
        if existing.first() is not None:
            raise ValueError("An account already exists for this email.")

        tenant_result = await self._session.execute(
            text(
                """
                INSERT INTO tenants (name, plan)
                VALUES (:name, 'starter')
                RETURNING id
                """
            ),
            {"name": full_name.strip() or normalized_email},
        )
        tenant_id = tenant_result.scalar_one()
        user_result = await self._session.execute(
            text(
                """
                INSERT INTO app_users (tenant_id, external_auth_id, email, full_name, password_hash)
                VALUES (:tenant_id, :external_auth_id, :email, :full_name, :password_hash)
                RETURNING id
                """
            ),
            {
                "tenant_id": tenant_id,
                "external_auth_id": normalized_email,
                "email": normalized_email,
                "full_name": full_name.strip() or "Investor",
                "password_hash": hash_password(password),
            },
        )
        user_id = user_result.scalar_one()
        await self._session.commit()
        return UserContext(
            tenant_id=tenant_id,
            user_id=user_id,
            external_auth_id=normalized_email,
            email=normalized_email,
            full_name=full_name.strip() or "Investor",
        )

    async def authenticate(self, email: str, password: str) -> UserContext | None:
        result = await self._session.execute(
            text(
                """
                SELECT tenant_id, id AS user_id, external_auth_id, email, full_name, password_hash
                FROM app_users
                WHERE lower(email) = :email
                """
            ),
            {"email": email.strip().lower()},
        )
        row = result.mappings().first()
        if row is None or not verify_password(password, row["password_hash"]):
            return None
        return UserContext(
            tenant_id=row["tenant_id"],
            user_id=row["user_id"],
            external_auth_id=row["external_auth_id"],
            email=row["email"],
            full_name=row["full_name"],
        )

    async def create_session(self, context: UserContext, token: str, user_agent: str | None) -> datetime:
        expires_at = datetime.now(UTC) + timedelta(days=SESSION_DAYS)
        await self._session.execute(
            text(
                """
                INSERT INTO auth_sessions (tenant_id, user_id, token_hash, user_agent, expires_at)
                VALUES (:tenant_id, :user_id, :token_hash, :user_agent, :expires_at)
                """
            ),
            {
                "tenant_id": context.tenant_id,
                "user_id": context.user_id,
                "token_hash": hash_session_token(token),
                "user_agent": user_agent,
                "expires_at": expires_at,
            },
        )
        await self._session.commit()
        return expires_at

    async def revoke_session(self, token: str) -> None:
        await self._session.execute(
            text(
                """
                UPDATE auth_sessions
                SET revoked_at = now()
                WHERE token_hash = :token_hash AND revoked_at IS NULL
                """
            ),
            {"token_hash": hash_session_token(token)},
        )
        await self._session.commit()
