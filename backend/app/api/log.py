"""Transparency log API (spec §9): STH, entries, inclusion proofs.

/api/log/root includes the registry public key (owner decision at Epic 2
gate) so the log explorer can verify STH signatures client-side.
"""
import json

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db, get_redis
from app.models import LogEntry
from app.schemas import err, ok
from app.trust import merkle
from app.trust.ca import ensure_trust_material

router = APIRouter(prefix="/api/log", tags=["log"])


def _latest_sth_payload(db: Session) -> dict:
    material = ensure_trust_material(get_settings().trust_dir)
    latest = db.execute(
        select(LogEntry).order_by(LogEntry.seq.desc()).limit(1)
    ).scalars().first()
    if latest is None:
        return {
            "tree_size": 0,
            "root_hash": merkle.root_hash([]).hex(),
            "timestamp": None,
            "sth_sig": None,
            "registry_public_key": material.registry_sth.public_key_b64,
        }
    return {
        "tree_size": latest.tree_size,
        "root_hash": latest.root_hash,
        "timestamp": latest.created_at.isoformat(),
        "sth_sig": latest.sth_sig,
        "registry_public_key": material.registry_sth.public_key_b64,
    }


@router.get("/root")
def get_root(db: Session = Depends(get_db)) -> dict:
    redis = get_redis()
    try:
        cached = redis.get(merkle.LATEST_ROOT_CACHE_KEY)
        if cached:
            return ok(json.loads(cached))
    except Exception:
        pass
    payload = _latest_sth_payload(db)
    try:
        redis.set(merkle.LATEST_ROOT_CACHE_KEY, json.dumps(payload), ex=60)
    except Exception:
        pass
    return ok(payload)


@router.get("/entries")
def list_entries(limit: int = 50, db: Session = Depends(get_db)) -> dict:
    rows = (
        db.execute(select(LogEntry).order_by(LogEntry.seq.desc()).limit(min(limit, 200)))
        .scalars()
        .all()
    )
    return ok(
        [
            {
                "seq": r.seq,
                "leaf_hash": r.leaf_hash,
                "entry": r.entry,
                "tree_size": r.tree_size,
                "root_hash": r.root_hash,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    )


@router.get("/entries/{seq}/proof")
def get_proof(seq: int, db: Session = Depends(get_db)):
    proof = merkle.proof_for_seq(db, seq)
    if proof is None:
        return JSONResponse(status_code=404, content=err("not_found", "No log entry with that seq."))
    return ok(proof.model_dump())
