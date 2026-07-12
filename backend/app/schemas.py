"""Pydantic I/O models. Every API response is ApiResponse-wrapped (spec §9)."""
import uuid
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ApiError(BaseModel):
    code: str
    message: str


class ApiResponse(BaseModel, Generic[T]):
    ok: bool
    data: T | None = None
    error: ApiError | None = None


def ok(data: Any) -> dict[str, Any]:
    return ApiResponse(ok=True, data=data).model_dump(mode="json")


def err(code: str, message: str) -> dict[str, Any]:
    return ApiResponse[Any](ok=False, error=ApiError(code=code, message=message)).model_dump(
        mode="json"
    )


# --- Registry ---

class KeyOut(BaseModel):
    """Public view of a signing key — private material never leaves the DB."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str
    role: str
    public_key_ed25519: str
    status: str
    valid_from: datetime
    revoked_at: datetime | None = None
    revocation_reason: str | None = None


class DomainOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    domain: str
    kind: str


class SmsHeaderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    header: str


class EntityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    kind: str
    sebi_reg_no: str
    status: str
    keys: list[KeyOut] = []


class EntityDetailOut(EntityOut):
    domains: list[DomainOut] = []
    sms_headers: list[SmsHeaderOut] = []
