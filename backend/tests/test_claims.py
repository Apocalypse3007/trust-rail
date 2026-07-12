"""Claim extraction: exact, fuzzy, homoglyph, weak-marker, none."""
import uuid

from app.pipeline.claims import EntityRef, extract_claim, skeleton

MERIDIAN = EntityRef(
    id=uuid.uuid4(),
    name="Meridian Broking Ltd",
    kind="broker",
    sebi_reg_no="DEMO-INZ-000123",
    domains=["meridianbroking.example"],
    sms_headers=["MERIDN"],
)
KUMAON = EntityRef(
    id=uuid.uuid4(),
    name="Kumaon Metals Ltd",
    kind="listed_company",
    sebi_reg_no="DEMO-INE-000451",
    domains=["kumaonmetals.example"],
    sms_headers=["KUMAON"],
)
ENTITIES = [MERIDIAN, KUMAON]


def test_exact_name_strong() -> None:
    r = extract_claim("Official notice from Meridian Broking Ltd regarding margins.", ENTITIES)
    assert r.claim_strength == "strong" and r.claimed_entity_id == MERIDIAN.id


def test_alias_without_suffix_strong() -> None:
    r = extract_claim("Kumaon Metals announces record quarterly results", ENTITIES)
    assert r.claim_strength == "strong" and r.claimed_entity_id == KUMAON.id


def test_reg_no_strong() -> None:
    r = extract_claim("Registered intermediary DEMO-INZ-000123 offers new plans", ENTITIES)
    assert r.claim_strength == "strong" and r.claimed_entity_id == MERIDIAN.id


def test_sms_header_strong() -> None:
    r = extract_claim("MERIDN: Your margin call is due tomorrow", ENTITIES)
    assert r.claim_strength == "strong" and r.claimed_entity_id == MERIDIAN.id


def test_fuzzy_misspelling_strong() -> None:
    r = extract_claim("Update from Meridian Brokking Limited for all clients", ENTITIES)
    assert r.claim_strength == "strong" and r.claimed_entity_id == MERIDIAN.id


def test_homoglyph_entity_detected() -> None:
    # Cyrillic е and а inside the name
    r = extract_claim("Announcement from Mеridiаn Broking Ltd — refund window open", ENTITIES)
    assert r.claim_strength == "strong"
    assert r.claimed_entity_id == MERIDIAN.id
    assert r.homoglyph_hit


def test_weak_marker_only() -> None:
    r = extract_claim("This circular from your registered intermediary requires action.", ENTITIES)
    assert r.claim_strength == "weak" and r.claimed_entity_id is None


def test_shared_suffix_words_do_not_claim() -> None:
    """Regression: token_set_ratio scored 100 for any token subset — a bare
    'ltd'/'broking' must never produce a strong claim."""
    for text in [
        "Quarterly update from some ltd company in the metals space",
        "Broking houses reported higher volumes this quarter",
        "Metals and mining stocks led the rally",
    ]:
        r = extract_claim(text, ENTITIES)
        assert r.claim_strength != "strong", text


def test_no_claim_plain_news() -> None:
    r = extract_claim(
        "Markets closed higher today as IT stocks rallied on strong global cues.", ENTITIES
    )
    assert r.claim_strength == "none" and r.claimed_entity_id is None


def test_empty_input() -> None:
    assert extract_claim("", ENTITIES).claim_strength == "none"
    assert extract_claim("   ", ENTITIES).claim_strength == "none"


def test_skeleton_maps_confusables() -> None:
    assert skeleton("Mеridiаn") == skeleton("Meridian")
