"""Email verification path (spec §13). .eml upload via the stdlib email
parser — never trusts a forwarded message's missing auth headers as if
they were a pass; says so honestly instead (AUTH_HEADERS_UNAVAILABLE).
"""
import email
import re
from email.policy import default as email_policy

from pydantic import BaseModel

from app.pipeline.risk import domain_lookalike

_ADDR_RE = re.compile(r"[\w.\-+]+@([\w.\-]+)")
_DKIM_RE = re.compile(r"dkim=(\w+)(?:[^;]*header\.d=([\w.\-]+))?", re.I)
_URL_RE = re.compile(r"https?://[^\s\"'<>]+")


class EmailParsed(BaseModel):
    from_addr: str | None = None
    from_domain: str | None = None
    reply_to: str | None = None
    reply_to_domain: str | None = None
    subject: str = ""
    body_text: str = ""
    links: list[str] = []
    auth_results_raw: str | None = None
    dkim_result: str | None = None  # "pass" | "fail" | None


def _domain_of(addr: str | None) -> str | None:
    if not addr:
        return None
    m = _ADDR_RE.search(addr)
    return m.group(1).lower() if m else None


def parse_eml(raw: bytes) -> EmailParsed:
    msg = email.message_from_bytes(raw, policy=email_policy)
    from_addr = msg.get("From")
    reply_to = msg.get("Reply-To")
    subject = str(msg.get("Subject", ""))
    body_part = msg.get_body(preferencelist=("plain", "html"))
    body_text = body_part.get_content() if body_part is not None else ""

    auth_raw = msg.get("Authentication-Results")
    dkim_result = None
    if auth_raw:
        m = _DKIM_RE.search(auth_raw)
        if m:
            dkim_result = m.group(1).lower()

    return EmailParsed(
        from_addr=from_addr,
        from_domain=_domain_of(from_addr),
        reply_to=reply_to,
        reply_to_domain=_domain_of(reply_to),
        subject=subject,
        body_text=body_text,
        links=_URL_RE.findall(body_text),
        auth_results_raw=auth_raw,
        dkim_result=dkim_result,
    )


class EmailReasons(BaseModel):
    """Extra reason codes for the verdict engine's `extra_reasons` — these
    are pure evidence, not fraud signals on their own; a legitimate forward
    genuinely lacks the original mail server's auth headers."""

    codes: list[str] = []
    domain_lookalike_of: str | None = None  # set only if from_domain imitates a registered one


def email_reason_codes(parsed: EmailParsed, registered_domains: list[str]) -> EmailReasons:
    codes: list[str] = []
    lookalike_of: str | None = None

    if parsed.from_domain:
        if parsed.from_domain in registered_domains:
            codes.append("DOMAIN_REGISTERED")
        else:
            codes.append("DOMAIN_NOT_REGISTERED")
            lookalike_of = domain_lookalike(parsed.from_domain, registered_domains)

    if parsed.auth_results_raw and parsed.dkim_result:
        codes.append("DKIM_ALIGN_PASS" if parsed.dkim_result == "pass" else "DKIM_ALIGN_FAIL")
    else:
        codes.append("AUTH_HEADERS_UNAVAILABLE")

    return EmailReasons(codes=codes, domain_lookalike_of=lookalike_of)
