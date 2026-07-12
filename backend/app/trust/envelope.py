"""TrustRail Signature Envelope v1 (spec §7.2).

Signing bytes = SHA-256 of the canonical envelope JSON with BOTH maker.sig
and checker.sig blanked. Maker and checker Ed25519-sign those same bytes;
the checker signature is required only for market_moving communications.
"""
import hashlib
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

from app.trust.ca import verify_bytes
from app.trust.canonical import canonical_json

MARKET_MOVING = "market_moving"


class SigBlock(BaseModel):
    key_id: str
    sig: str = ""


class Envelope(BaseModel):
    v: Literal[1] = 1
    artifact_sha256: str
    entity_id: str
    sebi_reg_no: str
    communication_id: str
    channel: str
    impact: str
    issued_at: datetime
    maker: SigBlock
    checker: SigBlock | None = None

    def to_wire(self) -> dict[str, Any]:
        d = self.model_dump(mode="json")
        if self.checker is None:
            d.pop("checker")
        return d


class KeyInfo(BaseModel):
    """Public half + lifecycle state of a signing key (from DB in later epics)."""

    key_id: str
    public_key_ed25519: str  # b64
    status: Literal["active", "revoked"] = "active"
    revoked_at: datetime | None = None


class EnvelopeResult(BaseModel):
    valid: bool
    maker_ok: bool = False
    checker_ok: bool | None = None  # None = checker not required and absent
    checker_required: bool = False
    key_states: dict[str, KeyInfo] = {}
    signed_at: datetime | None = None
    entity_active: bool = True
    error: str | None = None


KeyLookup = Any  # Callable[[str], KeyInfo | None] — kept loose for DB adapters


def signing_bytes(env: Envelope) -> bytes:
    """SHA-256 over canonical JSON with every sig field blanked."""
    blank = env.model_copy(deep=True)
    blank.maker.sig = ""
    if blank.checker is not None:
        blank.checker.sig = ""
    return hashlib.sha256(canonical_json(blank.to_wire())).digest()


def build_envelope(
    *,
    artifact_sha256: str,
    entity_id: str,
    sebi_reg_no: str,
    communication_id: str,
    channel: str,
    impact: str,
    issued_at: datetime,
    maker_key_id: str,
    checker_key_id: str | None = None,
) -> Envelope:
    """Unsigned envelope. checker_key_id must be set up front for
    market_moving comms so maker and checker sign identical bytes."""
    return Envelope(
        artifact_sha256=artifact_sha256,
        entity_id=entity_id,
        sebi_reg_no=sebi_reg_no,
        communication_id=communication_id,
        channel=channel,
        impact=impact,
        issued_at=issued_at,
        maker=SigBlock(key_id=maker_key_id),
        checker=SigBlock(key_id=checker_key_id) if checker_key_id else None,
    )


def envelope_digest(env: Envelope) -> str:
    """SHA-256 hex of the full (signed) canonical envelope — for log entries."""
    return hashlib.sha256(canonical_json(env.to_wire())).hexdigest()


def verify_envelope(
    env_raw: dict[str, Any],
    key_lookup: KeyLookup,
    entity_status: str = "active",
) -> EnvelopeResult:
    """Structured verification. Never raises on bad input.

    `valid` means: required signatures cryptographically verify against the
    looked-up public keys AND the entity is active. Key revocation *timing*
    (VERIFIED vs VERIFIED_NOTICE vs tampered) is decided by the verdict
    engine from `key_states` + `signed_at`.
    """
    try:
        env = Envelope.model_validate(env_raw)
    except (ValidationError, TypeError) as exc:
        return EnvelopeResult(valid=False, error=f"malformed envelope: {exc.__class__.__name__}")

    msg = signing_bytes(env)
    key_states: dict[str, KeyInfo] = {}
    entity_active = entity_status == "active"
    checker_required = env.impact == MARKET_MOVING

    def check_sig(block: SigBlock | None) -> bool:
        if block is None or not block.sig:
            return False
        info = key_lookup(block.key_id)
        if info is None:
            return False
        key_states[block.key_id] = info
        return verify_bytes(info.public_key_ed25519, msg, block.sig)

    maker_ok = check_sig(env.maker)

    checker_ok: bool | None
    if env.checker is not None and env.checker.sig:
        checker_ok = check_sig(env.checker)
    elif checker_required:
        checker_ok = False
    else:
        checker_ok = None

    valid = maker_ok and entity_active and (checker_ok is not False)
    return EnvelopeResult(
        valid=valid,
        maker_ok=maker_ok,
        checker_ok=checker_ok,
        checker_required=checker_required,
        key_states=key_states,
        signed_at=env.issued_at,
        entity_active=entity_active,
        error=None if valid else "signature chain did not validate",
    )
