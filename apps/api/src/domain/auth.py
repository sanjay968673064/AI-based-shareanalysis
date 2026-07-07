from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class UserContext:
    tenant_id: UUID
    user_id: UUID
    external_auth_id: str
