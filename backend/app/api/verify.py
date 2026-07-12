"""spec §9 — POST /api/verify + supporting endpoints. Runs the full
ingest -> hash -> registry match -> claims/risk -> verdict pipeline and
renders the result through channels/render.py (the only place verdict
copy is produced — spec §12.1).

Hard binding (stage 1) stays honestly "no manifest" for this endpoint —
there's no sidecar-envelope input field in the §9 contract, and the demo's
own mangled-media path strips any embedded manifest anyway. A registry
match (stage 2) is the sole proof path here, so a match against a
PUBLISHED communication surfaces its real reason code (HASH_EXACT_MATCH /
PHASH_MATCH / SIMHASH_MATCH / VIDEO_MATCH) rather than being silently
reattributed to SIG_CHAIN_VALID.

decide() (Epic 4, gate-tested) has no notion of key status for a stage-2
match — only communication-level withdrawal. `_downgrade_if_key_revoked`
below is a deliberate post-processing step, outside the frozen verdict
engine, so a signing-key revocation still downgrades a perceptual-match
VERIFIED to VERIFIED_NOTICE on the next re-verification (the demo's key-
compromise moment) without touching Epic 4's tested `decide()` logic.
"""
import io
import re
import tempfile
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, UploadFile
from fastapi.responses import JSONResponse
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.channels.render import CommunicationRef, EntityRef, RenderContext, render_verdict
from app.config import get_settings
from app.db import get_db, get_redis
from app.models import (
    Communication,
    CommStatus,
    Entity,
    InputKind,
    Key,
    KeyStatus,
    ScamBlacklist,
    Verdict as VerdictModel,
    Verification,
    VerifyChannel,
    ViewToken,
)
from app.pipeline import hashing, media
from app.pipeline.claims import extract_claim, load_entity_refs
from app.pipeline.emailcheck import EmailParsed, email_reason_codes, parse_eml
from app.pipeline.ingest import IngestError, IngestResult, ingest_file, ingest_text, ingest_url
from app.pipeline.risk import BlacklistRef, RiskSignal, analyze_risk
from app.pipeline.verdict import (
    Candidate,
    Decision,
    DecisionInput,
    MatchThresholds,
    QueryHashes,
    ReasonCode,
    Verdict as VerdictEnum,
    decide,
    match_registry,
)
from app.schemas import err, ok

router = APIRouter(prefix="/api", tags=["verify"])

_CERT_LINK_RE = re.compile(r"/c/([A-Za-z0-9]+)")


def _bad(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content=err(code, message))


# --- rate limiting: Redis token bucket (spec §9 — 30/min/IP) ---

def _rate_limit(redis, ip: str, capacity: int) -> tuple[bool, int]:
    key = f"trustrail:ratelimit:verify:{ip}"
    now = time.time()
    raw = redis.hgetall(key)
    tokens = float(raw.get(b"tokens", capacity)) if raw else float(capacity)
    last = float(raw.get(b"ts", now)) if raw else now
    refill_per_sec = capacity / 60.0
    tokens = min(capacity, tokens + max(0.0, now - last) * refill_per_sec)
    if tokens < 1.0:
        redis.hset(key, mapping={"tokens": tokens, "ts": now})
        redis.expire(key, 120)
        return False, max(1, int((1.0 - tokens) / refill_per_sec))
    redis.hset(key, mapping={"tokens": tokens - 1.0, "ts": now})
    redis.expire(key, 120)
    return True, 0


def _load_candidates(db: Session) -> list[Candidate]:
    comms = (
        db.execute(
            select(Communication).where(
                Communication.status.in_([CommStatus.published, CommStatus.revoked])
            )
        )
        .scalars()
        .all()
    )
    out: list[Candidate] = []
    for c in comms:
        if c.artifact is None:
            continue
        out.append(
            Candidate(
                communication_id=c.id,
                entity_id=c.entity_id,
                comm_status="published" if c.status == CommStatus.published else "revoked",
                sha256=c.artifact.sha256,
                phash64=c.artifact.phash64,
                pdq256=c.artifact.pdq256,
                simhash64=c.artifact.simhash64,
                video_frame_hashes=c.artifact.video_frame_hashes,
            )
        )
    return out


def _blacklist_refs(db: Session) -> list[BlacklistRef]:
    rows = db.execute(select(ScamBlacklist).where(ScamBlacklist.active.is_(True))).scalars().all()
    return [BlacklistRef(kind=r.kind.value, value=r.value, campaign=r.campaign) for r in rows]


def _query_hashes_and_text(
    ir: IngestResult,
) -> tuple[QueryHashes, str, EmailParsed | None]:
    """Per-kind query hashes + the text fed to claims/risk. Captions/OCR are
    out of scope (spec §8.4) — image/video claims come only from the
    explicit claimed_sender_text field the caller mixes in."""
    if ir.kind == InputKind.image:
        data = ir.data or b""
        return (
            QueryHashes(
                sha256=hashing.sha256_hex(data),
                phash64=hashing.phash64_hex(data),
                pdq256=hashing.pdq256_hex(data),
            ),
            "",
            None,
        )
    if ir.kind == InputKind.video:
        data = ir.data or b""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp.write(data)
            tmp_path = Path(tmp.name)
        try:
            frames = media.extract_frame_phashes(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)
        return QueryHashes(sha256=hashing.sha256_hex(data), video_frame_hashes=frames), "", None
    if ir.kind == InputKind.pdf:
        data = ir.data or b""
        text = "".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages)
        simhash = hashing.simhash64_hex(text) if text.strip() else None
        return QueryHashes(sha256=hashing.sha256_hex(data), simhash64=simhash), text, None
    if ir.kind == InputKind.eml:
        parsed = parse_eml(ir.data or b"")
        full_text = f"{parsed.subject}\n{parsed.body_text}"
        simhash = hashing.simhash64_hex(full_text) if full_text.strip() else None
        return QueryHashes(simhash64=simhash), full_text, parsed
    if ir.kind == InputKind.text:
        text = ir.text or ""
        return (
            QueryHashes(
                sha256=hashing.sha256_hex(text.encode("utf-8")),
                simhash64=hashing.simhash64_hex(text),
            ),
            text,
            None,
        )
    if ir.kind == InputKind.url:
        return QueryHashes(), ir.url or "", None
    return QueryHashes(), "", None


def _downgrade_if_key_revoked(db: Session, decision: Decision) -> Decision:
    """A perceptual/hash registry match only proves content identity, not
    current signing-key state — decide() (Epic 4) never looks at keys for
    a stage-2 match. Checking that here, outside the frozen verdict engine,
    so revoking a key still downgrades a matched VERIFIED to VERIFIED_NOTICE
    on the next re-verification (the demo's key-compromise moment)."""
    if decision.verdict != VerdictEnum.VERIFIED or decision.matched_communication_id is None:
        return decision
    comm = db.get(Communication, decision.matched_communication_id)
    if comm is None:
        return decision
    keys = [db.get(Key, comm.maker_key_id)]
    if comm.checker_key_id:
        keys.append(db.get(Key, comm.checker_key_id))
    if not any(k is not None and k.status == KeyStatus.revoked for k in keys):
        return decision
    decision.verdict = VerdictEnum.VERIFIED_NOTICE
    if ReasonCode.KEY_REVOKED_AFTER_SIGNING not in decision.reasons:
        decision.reasons.append(ReasonCode.KEY_REVOKED_AFTER_SIGNING)
    return decision


def _referenced_comm_sha256(db: Session, text: str) -> str | None:
    """TAMPERED_CONTENT support: input pastes a certificate link for a
    specific communication but the submitted content doesn't match it."""
    m = _CERT_LINK_RE.search(text or "")
    if not m:
        return None
    token_row = db.execute(select(ViewToken).where(ViewToken.token == m.group(1))).scalars().first()
    if token_row is None or token_row.verification_id is None:
        return None
    verification = db.get(Verification, token_row.verification_id)
    if verification is None or verification.matched_communication_id is None:
        return None
    comm = db.get(Communication, verification.matched_communication_id)
    return comm.artifact.sha256 if comm and comm.artifact else None


def _entity_ref_out(db: Session, entity_id: uuid.UUID | None) -> EntityRef | None:
    if entity_id is None:
        return None
    entity = db.get(Entity, entity_id)
    if entity is None:
        return None
    return EntityRef(id=str(entity.id), name=entity.name, sebi_reg_no=entity.sebi_reg_no)


def _comm_ref_out(db: Session, comm_id: uuid.UUID | None) -> CommunicationRef | None:
    if comm_id is None:
        return None
    comm = db.get(Communication, comm_id)
    if comm is None:
        return None
    return CommunicationRef(
        id=str(comm.id),
        title=comm.title,
        published_at=comm.published_at.isoformat() if comm.published_at else None,
        log_seq=comm.log_seq,
        channel=comm.channel.value,
    )


def _issue_certificate_token(db: Session, verification_id: uuid.UUID) -> ViewToken:
    settings = get_settings()
    token = ViewToken(
        token=uuid.uuid4().hex + uuid.uuid4().hex,
        verification_id=verification_id,
        expires_at=datetime.now(UTC) + timedelta(minutes=settings.cert_link_ttl_minutes),
    )
    db.add(token)
    db.flush()
    return token


@router.post("/verify")
async def verify(
    request: Request,
    file: UploadFile | None = None,
    text: str | None = Form(None),
    url: str | None = Form(None),
    claimed_sender_text: str | None = Form(None),
    state_code: str | None = Form(None),
    locale: str | None = Form(None),
    channel: VerifyChannel = Form(VerifyChannel.sim),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    redis = get_redis()
    ip = request.client.host if request.client else "unknown"
    try:
        allowed, retry_after = _rate_limit(redis, ip, settings.verify_rate_limit_per_min)
    except Exception:
        allowed, retry_after = True, 0  # rate limiting is best-effort, never blocks the demo
    if not allowed:
        return JSONResponse(
            status_code=429,
            content=err("rate_limited", f"Too many requests. Retry in {retry_after}s."),
            headers={"Retry-After": str(retry_after)},
        )

    if sum(x is not None for x in (file, text, url)) != 1:
        return _bad(422, "bad_input", "Provide exactly one of file, text, or url.")

    t0 = time.monotonic()
    try:
        if file is not None:
            data = await file.read()
            ingest_result = ingest_file(data, file.filename)
        elif text is not None:
            ingest_result = ingest_text(text)
        else:
            assert url is not None
            ingest_result = ingest_url(url)
    except IngestError as exc:
        return _bad(422, exc.code, exc.message)

    resolved_locale = locale if locale in ("en", "hi") else settings.default_locale

    query_hashes, body_text, email_parsed = _query_hashes_and_text(ingest_result)
    combined_text = " ".join(t for t in (claimed_sender_text, body_text) if t)

    entities = load_entity_refs(db)
    claims = extract_claim(combined_text, entities)
    registered_domains = [d for e in entities for d in e.domains]
    risk = analyze_risk(
        combined_text,
        registered_domains,
        _blacklist_refs(db),
        phash64=query_hashes.phash64,
        phash_match_max_dist=settings.phash_match_max_dist,
    )

    extra_reasons: list[ReasonCode] = []
    if email_parsed is not None:
        email_reasons = email_reason_codes(email_parsed, registered_domains)
        extra_reasons = [ReasonCode(c) for c in email_reasons.codes]
        if email_reasons.domain_lookalike_of:
            # From-domain lookalike (spec §13) is a fraud-positive, same as an
            # in-body lookalike link — analyze_risk() never sees the From:
            # header, so it's folded in here rather than duplicating the
            # lookalike sweep inside decide() itself.
            risk.signals.append(
                RiskSignal(
                    code="LOOKALIKE_DOMAIN",
                    weight=5,
                    evidence=f"From: {email_parsed.from_domain} imitates {email_reasons.domain_lookalike_of}",
                )
            )
            risk.fraud_positive = True
            risk.risk_high = True

    thresholds = MatchThresholds(
        phash_match_max_dist=settings.phash_match_max_dist,
        phash_near_max_dist=settings.phash_near_max_dist,
        pdq_match_max_dist=settings.pdq_match_max_dist,
        video_frame_match_ratio=settings.video_frame_match_ratio,
        simhash_match_max_dist=settings.simhash_match_max_dist,
    )
    registry_match = match_registry(query_hashes, _load_candidates(db), thresholds)

    decision: Decision = decide(
        DecisionInput(
            registry_match=registry_match,
            claims=claims,
            risk=risk,
            referenced_comm_sha256=_referenced_comm_sha256(db, combined_text),
            query_sha256=query_hashes.sha256,
            extra_reasons=extra_reasons,
        )
    )
    decision = _downgrade_if_key_revoked(db, decision)
    latency_ms = int((time.monotonic() - t0) * 1000)

    verification = Verification(
        channel=channel,
        input_kind=ingest_result.kind,
        verdict=VerdictModel(decision.verdict.value),
        reasons=[r.value for r in decision.reasons],
        signals={
            "trace": [t.model_dump() for t in decision.trace],
            "risk_signals": [s.model_dump() for s in risk.signals],
        },
        matched_entity_id=decision.matched_entity_id,
        matched_communication_id=decision.matched_communication_id,
        claimed_entity_text=claims.claimed_entity_text,
        campaign=decision.campaign,
        state_code=state_code,
        latency_ms=latency_ms,
    )
    db.add(verification)
    db.flush()

    cert_url = None
    if decision.verdict in (VerdictEnum.VERIFIED, VerdictEnum.VERIFIED_NOTICE):
        token = _issue_certificate_token(db, verification.id)
        cert_url = f"/c/{token.token}"
    db.commit()

    ctx = RenderContext(
        verification_id=str(verification.id),
        decision=decision,
        locale=resolved_locale,
        matched_entity=_entity_ref_out(db, decision.matched_entity_id),
        matched_communication=_comm_ref_out(db, decision.matched_communication_id),
        claimed_entity_text=claims.claimed_entity_text,
        certificate_url=cert_url,
        sebi_check_url=settings.sebi_check_url,
    )
    return ok(render_verdict(ctx).model_dump(mode="json"))


@router.get("/verifications/{verification_id}")
def get_verification(verification_id: uuid.UUID, locale: str = "en", db: Session = Depends(get_db)):
    from app.pipeline.verdict import ReasonCode, TraceStep

    v = db.get(Verification, verification_id)
    if v is None:
        return _bad(404, "not_found", "No such verification.")

    decision = Decision(
        verdict=VerdictEnum(v.verdict.value),
        reasons=[ReasonCode(r) for r in v.reasons],
        matched_communication_id=v.matched_communication_id,
        matched_entity_id=v.matched_entity_id,
        campaign=v.campaign,
        trace=[TraceStep(**t) for t in v.signals.get("trace", [])],
    )
    token_row = db.execute(
        select(ViewToken)
        .where(ViewToken.verification_id == v.id)
        .order_by(ViewToken.created_at.desc())
    ).scalars().first()
    cert_url = None
    if token_row is not None and token_row.used_at is None and token_row.expires_at > datetime.now(UTC):
        cert_url = f"/c/{token_row.token}"

    ctx = RenderContext(
        verification_id=str(v.id),
        decision=decision,
        locale=locale if locale in ("en", "hi") else "en",
        matched_entity=_entity_ref_out(db, v.matched_entity_id),
        matched_communication=_comm_ref_out(db, v.matched_communication_id),
        claimed_entity_text=v.claimed_entity_text,
        certificate_url=cert_url,
        sebi_check_url=get_settings().sebi_check_url,
    )
    return ok(render_verdict(ctx).model_dump(mode="json"))


@router.post("/verifications/{verification_id}/certificate-token")
def create_certificate_token(verification_id: uuid.UUID, db: Session = Depends(get_db)):
    v = db.get(Verification, verification_id)
    if v is None:
        return _bad(404, "not_found", "No such verification.")
    if v.verdict.value not in ("VERIFIED", "VERIFIED_NOTICE"):
        return _bad(409, "bad_state", "Certificates are only available for VERIFIED or VERIFIED_NOTICE results.")
    token = _issue_certificate_token(db, v.id)
    db.commit()
    return ok({"token": token.token, "url": f"/c/{token.token}", "expires_at": token.expires_at.isoformat()})
