"""spec §12.1 — THE ONLY place verdict -> human-readable copy happens.
The verify API and the (flag-gated) WhatsApp adapter both consume this;
card strings never get invented in the frontend or in a channel adapter.
"""
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.pipeline.verdict import Decision, ReasonCode, Verdict

_I18N_DIR = Path(__file__).resolve().parents[1] / "i18n"
_CACHE: dict[str, dict[str, Any]] = {}

_VERDICT_KEY = {
    Verdict.VERIFIED: "verified",
    Verdict.VERIFIED_NOTICE: "verified_notice",
    Verdict.OFFICIAL_CLAIM_UNVERIFIED: "official_claim_unverified",
    Verdict.LIKELY_FAKE: "likely_fake",
    Verdict.INFORMATIONAL: "informational",
}

# Priority order for picking LIKELY_FAKE's {top_reason} — most alarming first.
_TOP_REASON_PRIORITY = [
    ReasonCode.BLACKLIST_MATCH,
    ReasonCode.LOOKALIKE_DOMAIN,
    ReasonCode.TAMPERED_SIGNATURE,
    ReasonCode.TAMPERED_CONTENT,
    ReasonCode.HOMOGLYPH_ENTITY,
    ReasonCode.PAYMENT_ASK,
    ReasonCode.RISK_PHRASES,
    ReasonCode.URL_RISK,
    ReasonCode.ENTITY_CLAIM_STRONG,
    ReasonCode.ENTITY_CLAIM_WEAK,
]


def _load(locale: str) -> dict[str, Any]:
    if locale not in _CACHE:
        path = _I18N_DIR / f"{locale}.json"
        if not path.exists():
            path = _I18N_DIR / "en.json"
        _CACHE[locale] = json.loads(path.read_text(encoding="utf-8"))
    return _CACHE[locale]


class EntityRef(BaseModel):
    id: str
    name: str
    sebi_reg_no: str


class CommunicationRef(BaseModel):
    id: str
    title: str
    published_at: str | None = None
    log_seq: int | None = None
    channel: str | None = None


class Button(BaseModel):
    kind: str
    label: str
    url: str


class CardPayload(BaseModel):
    verification_id: str
    verdict: str
    headline: str
    body: str
    reasons: list[str]
    reason_strings: list[str]
    advice: list[str]
    buttons: list[Button]
    matched_entity: EntityRef | None = None
    matched_communication: CommunicationRef | None = None
    claimed_entity_text: str | None = None
    pipeline_trace: list[dict[str, Any]]
    locale: str


class RenderContext(BaseModel):
    """Everything render_verdict needs beyond the raw Decision, resolved by
    the caller (verify.py) via DB lookups — this module stays DB-free so it
    can be shared by the simulator and the WhatsApp adapter unchanged."""

    verification_id: str
    decision: Decision
    locale: str = "en"
    matched_entity: EntityRef | None = None
    matched_communication: CommunicationRef | None = None
    claimed_entity_text: str | None = None
    revoked_date: str | None = None
    certificate_url: str | None = None
    sebi_check_url: str = "#"


def _reason_string(strings: dict[str, Any], code: str) -> str:
    return strings.get("reasons", {}).get(code, code)


def render_verdict(ctx: RenderContext) -> CardPayload:
    strings = _load(ctx.locale)
    d: Decision = ctx.decision
    reason_values = [r.value for r in d.reasons]
    reason_strings = [_reason_string(strings, code) for code in reason_values]

    v = strings["verdict"][_VERDICT_KEY[d.verdict]]

    fmt: dict[str, Any] = {}
    if ctx.matched_entity is not None:
        fmt["entity"] = ctx.matched_entity.name
        fmt["reg"] = ctx.matched_entity.sebi_reg_no
    if ctx.matched_communication is not None:
        fmt["date"] = ctx.matched_communication.published_at or ""
        fmt["channel"] = ctx.matched_communication.channel or ""
        fmt["seq"] = ctx.matched_communication.log_seq
    if ctx.claimed_entity_text:
        fmt["claimed"] = ctx.claimed_entity_text
    elif d.verdict == Verdict.OFFICIAL_CLAIM_UNVERIFIED:
        fmt["claimed"] = "an official source"
    if ctx.revoked_date:
        fmt["revoked_date"] = ctx.revoked_date

    top_reason = ""
    for code in _TOP_REASON_PRIORITY:
        if code in d.reasons:
            top_reason = _reason_string(strings, code.value)
            break
    if not top_reason and reason_strings:
        top_reason = reason_strings[0]
    fmt["top_reason"] = top_reason

    try:
        body = v["body"].format(**fmt)
    except (KeyError, IndexError):
        body = v["body"]

    advice: list[str] = []
    buttons: list[Button] = []
    if d.verdict in (Verdict.VERIFIED, Verdict.VERIFIED_NOTICE):
        advice.append(strings["advice"]["sebi_check"])
        if ctx.certificate_url:
            buttons.append(
                Button(kind="certificate", label=strings["button"]["view_certificate"],
                       url=ctx.certificate_url)
            )
        buttons.append(
            Button(kind="sebi_check", label=strings["button"]["sebi_check"], url=ctx.sebi_check_url)
        )
    elif d.verdict in (Verdict.OFFICIAL_CLAIM_UNVERIFIED, Verdict.LIKELY_FAKE):
        advice.append(strings["advice"]["sebi_check"])
        if d.verdict == Verdict.LIKELY_FAKE:
            advice.append(strings["advice"]["radar_added"])
        buttons.append(
            Button(kind="sebi_check", label=strings["button"]["sebi_check"], url=ctx.sebi_check_url)
        )
    buttons.append(Button(kind="expand_trace", label=strings["button"]["expand_trace"], url=""))

    return CardPayload(
        verification_id=ctx.verification_id,
        verdict=d.verdict.value,
        headline=v["title"],
        body=body,
        reasons=reason_values,
        reason_strings=reason_strings,
        advice=advice,
        buttons=buttons[:3],
        matched_entity=ctx.matched_entity,
        matched_communication=ctx.matched_communication,
        claimed_entity_text=ctx.claimed_entity_text,
        pipeline_trace=[t.model_dump() for t in d.trace],
        locale=ctx.locale,
    )
