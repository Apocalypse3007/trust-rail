"""Key + communication revocation (spec §7.4).

Both actions append a transparency-log entry — revocations are logged
events, not silent edits. Verdict timing rules (VERIFIED_NOTICE vs tampered)
live in the verdict engine; this module only changes state and logs it.
"""
import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import CommStatus, Communication, Key, KeyStatus, LogEntry
from app.trust import merkle


def revoke_key(
    db: Session, key: Key, reason: str, registry_private_b64: str
) -> LogEntry:
    now = datetime.now(UTC)
    key.status = KeyStatus.revoked
    key.revoked_at = now
    key.revocation_reason = reason
    return merkle.append_entry(
        db,
        {
            "kind": "key_revocation",
            "key_id": str(key.id),
            "entity_id": str(key.entity_id),
            "revoked_at": now.isoformat(),
            "reason": reason,
        },
        registry_private_b64,
    )


def revoke_communication(
    db: Session, comm: Communication, registry_private_b64: str
) -> LogEntry:
    now = datetime.now(UTC)
    comm.status = CommStatus.revoked
    return merkle.append_entry(
        db,
        {
            "kind": "communication_revocation",
            "communication_id": str(comm.id),
            "entity_id": str(comm.entity_id),
            "revoked_at": now.isoformat(),
        },
        registry_private_b64,
    )


def key_info_lookup(db: Session):
    """Adapter: envelope.verify_envelope key_lookup backed by the keys table."""
    from app.trust.envelope import KeyInfo

    def lookup(key_id: str) -> KeyInfo | None:
        try:
            key = db.get(Key, uuid.UUID(key_id))
        except ValueError:
            return None
        if key is None:
            return None
        return KeyInfo(
            key_id=str(key.id),
            public_key_ed25519=key.public_key_ed25519,
            status=key.status.value,
            revoked_at=key.revoked_at,
        )

    return lookup
