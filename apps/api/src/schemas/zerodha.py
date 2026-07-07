from datetime import datetime

from pydantic import BaseModel, Field


class BrokerStatusRead(BaseModel):
    broker: str
    status: str
    read_only: bool
    last_synced_at: datetime | None


class ReadOnlyConnectResponse(BaseModel):
    authorization_url: str
    read_only: bool = True
    message: str


class ReadOnlyConnectRequest(BaseModel):
    zerodha_user_id: str = Field(validation_alias="zerodhaUserId")
    account_label: str = Field(default="Primary Zerodha", validation_alias="accountLabel")


class McpConnectResponse(BaseModel):
    authorization_url: str
    read_only: bool = True
    message: str


class McpSyncResponse(BaseModel):
    imported_count: int = Field(serialization_alias="importedCount")
    skipped_count: int = Field(serialization_alias="skippedCount")
    message: str
