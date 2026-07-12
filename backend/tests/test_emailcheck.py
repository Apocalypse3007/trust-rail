"""Email path gate tests (spec §13): domain registration, DKIM alignment,
honest handling of forwarded mail's missing auth headers, lookalike From
domains.
"""
from email.message import EmailMessage

from app.pipeline.emailcheck import email_reason_codes, parse_eml

REGISTERED = ["suvarnamf.example", "meridianbroking.example"]


def _eml(from_addr: str, auth_results: str | None = None, body: str = "hello") -> bytes:
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["Subject"] = "Test"
    if auth_results:
        msg["Authentication-Results"] = auth_results
    msg.set_content(body)
    return bytes(msg)


def test_registered_domain_no_auth_headers() -> None:
    """The common forwarded-mail case: registered domain, no auth headers —
    honest AUTH_HEADERS_UNAVAILABLE, not a silent pass."""
    parsed = parse_eml(_eml("updates@suvarnamf.example"))
    assert parsed.from_domain == "suvarnamf.example"
    r = email_reason_codes(parsed, REGISTERED)
    assert r.codes == ["DOMAIN_REGISTERED", "AUTH_HEADERS_UNAVAILABLE"]
    assert r.domain_lookalike_of is None


def test_unregistered_domain_no_lookalike() -> None:
    parsed = parse_eml(_eml("news@some-financial-blog.example"))
    r = email_reason_codes(parsed, REGISTERED)
    assert r.codes == ["DOMAIN_NOT_REGISTERED", "AUTH_HEADERS_UNAVAILABLE"]
    assert r.domain_lookalike_of is None


def test_lookalike_from_domain_detected() -> None:
    parsed = parse_eml(_eml("compliance@suvarnamf-verify.example"))
    r = email_reason_codes(parsed, REGISTERED)
    assert "DOMAIN_NOT_REGISTERED" in r.codes
    assert r.domain_lookalike_of == "suvarnamf.example"


def test_dkim_pass() -> None:
    parsed = parse_eml(
        _eml("updates@suvarnamf.example", auth_results="mx.example; dkim=pass header.d=suvarnamf.example")
    )
    r = email_reason_codes(parsed, REGISTERED)
    assert "DKIM_ALIGN_PASS" in r.codes
    assert "AUTH_HEADERS_UNAVAILABLE" not in r.codes


def test_dkim_fail() -> None:
    parsed = parse_eml(
        _eml("updates@suvarnamf.example", auth_results="mx.example; dkim=fail header.d=suvarnamf.example")
    )
    r = email_reason_codes(parsed, REGISTERED)
    assert "DKIM_ALIGN_FAIL" in r.codes


def test_links_extracted_from_body() -> None:
    parsed = parse_eml(
        _eml("x@unregistered.example", body="Click http://scam.top/claim now")
    )
    assert parsed.links == ["http://scam.top/claim"]
