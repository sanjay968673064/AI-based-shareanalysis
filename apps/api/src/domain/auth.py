from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class UserContext:
    tenant_id: UUID
    user_id: UUID
    external_auth_id: str
    email: str | None = None
    full_name: str | None = None
