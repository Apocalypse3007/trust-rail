"""One-time certificate view tokens (spec §9, §10.4): GET /api/c/{token}.
Views are single-use — the second GET of a consumed token returns 410 with
a clean error explaining how to get a fresh one.
"""
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Communication, Entity, Key, Verification, ViewToken
from app.schemas import err, ok
from app.trust import merkle

router = APIRouter(prefix="/api", tags=["certificate"])


def _expired_or_used(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=err(code, message))


@router.get("/c/{token}")
def get_certificate(token: str, db: Session = Depends(get_db)):
    row = db.execute(select(ViewToken).where(ViewToken.token == token)).scalars().first()
    if row is None:
        return _expired_or_used(410, "not_found", "This link is invalid.")
    if row.used_at is not None:
        return _expired_or_used(
            410, "used", "This one-time link has already been viewed. Request a fresh certificate link."
        )
    if row.expires_at <= datetime.now(UTC):
        return _expired_or_used(410, "expired", "This link has expired. Request a fresh certificate link.")

    verdict: str | None = None
    comm: Communication | None = None
    if row.verification_id is not None:
        v = db.get(Verification, row.verification_id)
        if v is None or v.matched_communication_id is None:
            return _expired_or_used(410, "not_found", "Nothing to show for this link.")
        verdict = v.verdict.value
        comm = db.get(Communication, v.matched_communication_id)
    elif row.communication_id is not None:
        comm = db.get(Communication, row.communication_id)

    if comm is None:
        return _expired_or_used(410, "not_found", "Nothing to show for this link.")

    entity = db.get(Entity, comm.entity_id)
    maker_key = db.get(Key, comm.maker_key_id) if comm.maker_key_id else None
    checker_key = db.get(Key, comm.checker_key_id) if comm.checker_key_id else None
    proof = merkle.proof_for_seq(db, comm.log_seq) if comm.log_seq is not None else None

    payload = {
        "verdict": verdict,
        "entity": (
            {"id": str(entity.id), "name": entity.name, "sebi_reg_no": entity.sebi_reg_no}
            if entity is not None
            else None
        ),
        "communication": {
            "id": str(comm.id),
            "title": comm.title,
            "channel": comm.channel.value,
            "published_at": comm.published_at.isoformat() if comm.published_at else None,
            "log_seq": comm.log_seq,
        },
        "artifact_sha256": comm.artifact.sha256 if comm.artifact else None,
        "signature_chain": {
            "maker_key_id": str(maker_key.id) if maker_key else None,
            "maker_key_status": maker_key.status.value if maker_key else None,
            "checker_key_id": str(checker_key.id) if checker_key else None,
            "checker_key_status": checker_key.status.value if checker_key else None,
        },
        "inclusion_proof": proof.model_dump() if proof else None,
    }
    row.used_at = datetime.now(UTC)
    db.commit()
    return ok(payload)
