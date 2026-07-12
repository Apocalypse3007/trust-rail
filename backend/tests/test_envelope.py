"""Trust-core gate tests: Signature Envelope v1 sign/verify."""
from datetime import UTC, datetime

from app.trust.ca import generate_ed25519_keypair, sign_bytes
from app.trust.envelope import (
    Envelope,
    KeyInfo,
    build_envelope,
    signing_bytes,
    verify_envelope,
)

MAKER = generate_ed25519_keypair()
CHECKER = generate_ed25519_keypair()
STRANGER = generate_ed25519_keypair()

KEYS = {
    "maker-1": KeyInfo(key_id="maker-1", public_key_ed25519=MAKER.public_key_b64),
    "checker-1": KeyInfo(key_id="checker-1", public_key_ed25519=CHECKER.public_key_b64),
}


def lookup(key_id: str) -> KeyInfo | None:
    return KEYS.get(key_id)


def _envelope(impact: str = "standard", checker_key_id: str | None = None) -> Envelope:
    return build_envelope(
        artifact_sha256="ab" * 32,
        entity_id="00000000-0000-0000-0000-000000000001",
        sebi_reg_no="DEMO-INZ-000123",
        communication_id="00000000-0000-0000-0000-000000000002",
        channel="pdf",
        impact=impact,
        issued_at=datetime(2026, 7, 10, 9, 30, tzinfo=UTC),
        maker_key_id="maker-1",
        checker_key_id=checker_key_id,
    )


def _maker_sign(env: Envelope, keypair=MAKER) -> None:
    env.maker.sig = sign_bytes(keypair.private_key_b64, signing_bytes(env))


def _checker_sign(env: Envelope, keypair=CHECKER) -> None:
    assert env.checker is not None
    env.checker.sig = sign_bytes(keypair.private_key_b64, signing_bytes(env))


def test_standard_maker_only_valid() -> None:
    env = _envelope()
    _maker_sign(env)
    res = verify_envelope(env.to_wire(), lookup)
    assert res.valid and res.maker_ok
    assert res.checker_ok is None and not res.checker_required
    assert res.signed_at == env.issued_at


def test_market_moving_maker_and_checker_valid() -> None:
    env = _envelope("market_moving", "checker-1")
    _maker_sign(env)
    _checker_sign(env)
    res = verify_envelope(env.to_wire(), lookup)
    assert res.valid and res.maker_ok and res.checker_ok and res.checker_required


def test_checker_required_but_missing_invalid() -> None:
    """Gate case: market_moving without a checker co-sign must be invalid."""
    env = _envelope("market_moving", "checker-1")
    _maker_sign(env)  # checker never co-signs
    res = verify_envelope(env.to_wire(), lookup)
    assert not res.valid and res.maker_ok and res.checker_ok is False


def test_wrong_key_invalid() -> None:
    """Gate case: signature from a key other than the registered one fails."""
    env = _envelope()
    _maker_sign(env, STRANGER)  # signs with an unregistered private key
    res = verify_envelope(env.to_wire(), lookup)
    assert not res.valid and not res.maker_ok


def test_tampered_field_invalid() -> None:
    env = _envelope()
    _maker_sign(env)
    wire = env.to_wire()
    wire["artifact_sha256"] = "cd" * 32  # doctored after signing
    res = verify_envelope(wire, lookup)
    assert not res.valid and not res.maker_ok


def test_maker_and_checker_sign_identical_bytes() -> None:
    env = _envelope("market_moving", "checker-1")
    before = signing_bytes(env)
    _maker_sign(env)
    assert signing_bytes(env) == before  # maker's own sig excluded from bytes
    _checker_sign(env)
    assert signing_bytes(env) == before


def test_suspended_entity_invalid() -> None:
    env = _envelope()
    _maker_sign(env)
    res = verify_envelope(env.to_wire(), lookup, entity_status="suspended")
    assert not res.valid and res.maker_ok and not res.entity_active


def test_revoked_key_state_surfaces_but_crypto_validity_holds() -> None:
    """Revocation timing is the verdict engine's decision; the envelope
    reports facts: signature verifies, key state says revoked."""
    revoked = KeyInfo(
        key_id="maker-1",
        public_key_ed25519=MAKER.public_key_b64,
        status="revoked",
        revoked_at=datetime(2026, 7, 12, tzinfo=UTC),
    )
    env = _envelope()
    _maker_sign(env)
    res = verify_envelope(env.to_wire(), lambda k: revoked if k == "maker-1" else None)
    assert res.valid and res.maker_ok
    assert res.key_states["maker-1"].status == "revoked"
    assert res.key_states["maker-1"].revoked_at is not None


def test_unknown_key_id_invalid() -> None:
    env = _envelope()
    _maker_sign(env)
    res = verify_envelope(env.to_wire(), lambda _k: None)
    assert not res.valid and not res.maker_ok


def test_garbage_input_never_raises() -> None:
    for garbage in [{}, {"v": 2}, {"v": 1, "maker": "nope"}, {"v": 1, "issued_at": "xx"}]:
        res = verify_envelope(garbage, lookup)
        assert not res.valid and res.error is not None
