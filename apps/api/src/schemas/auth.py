from datetime import datetime

from pydantic import BaseModel, Field


class AuthUserRead(BaseModel):
    id: str
    email: str | None = None
    full_name: str | None = Field(default=None, alias="fullName")
    tenant_id: str = Field(alias="tenantId")


class AuthSessionRead(BaseModel):
    token: str
    expires_at: datetime = Field(alias="expiresAt")
    user: AuthUserRead


class RegisterRequest(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=120, alias="fullName")


class LoginRequest(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)
    password: str = Field(min_length=1, max_length=128)
