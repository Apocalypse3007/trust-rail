"""Generates the two seeded .eml samples for Epic 9's gate (spec §13, §17):
a plain forwarded email from a registered domain (no auth headers, as real
forwards typically arrive) and a lookalike-domain scam email. Fictional
entities/addresses only — no real people or brands.
"""
from email.message import EmailMessage
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "fixtures" / "eml_samples"


def _write(name: str, msg: EmailMessage) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    path.write_bytes(bytes(msg))
    print(f"wrote {path}")


def forwarded_legit() -> EmailMessage:
    """Registered domain, strong claim, no Authentication-Results — typical
    of a forward. No fraud signals -> expected OFFICIAL_CLAIM_UNVERIFIED
    (claim recognized, but this exact forward doesn't hash-match the
    original registered communication)."""
    msg = EmailMessage()
    msg["From"] = "investor-updates@suvarnamf.example"
    msg["To"] = "forwarded@example.com"
    msg["Subject"] = "Fwd: Your July folio statement is ready"
    msg.set_content(
        "Dear investor,\n\n"
        "This is Suvarna Mutual Fund writing to let you know your July folio "
        "statement is now available at suvarnamf.example/statements.\n\n"
        "We never ask for OTPs or payments over email.\n\n"
        "— Suvarna Mutual Fund, SEBI reg DEMO-MF-000021"
    )
    return msg


def lookalike_scam() -> EmailMessage:
    """Lookalike/blacklisted domain impersonating the regulator, with
    urgency + a payment ask -> expected LIKELY_FAKE."""
    msg = EmailMessage()
    msg["From"] = "compliance@demosecboard-verify.xyz"
    msg["To"] = "investor@example.com"
    msg["Subject"] = "URGENT: Compliance verification required within 2 hours"
    msg.set_content(
        "Dear Investor,\n\n"
        "Demo Securities Board compliance notice: your trading account requires "
        "urgent verification. Pay the processing fee via UPI to compliance@okpay "
        "within the last 2 hours to avoid suspension.\n\n"
        "Verify now: http://demosecboard-verify.xyz/kyc\n\n"
        "— Demo Securities Board Compliance Cell"
    )
    return msg


def main() -> None:
    _write("forwarded_legit.eml", forwarded_legit())
    _write("lookalike_scam.eml", lookalike_scam())


if __name__ == "__main__":
    main()
