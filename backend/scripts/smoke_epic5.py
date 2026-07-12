"""Epic 5 gate (spec §17): publish an image -> WhatsApp-mangle it ->
verify still returns VERIFIED via PHASH_MATCH; a used certificate token's
second GET returns 410. Kept as a throwaway self-check script (not part of
`make check`); its scenario gets folded into scripts/evaluate.py in Epic 10.
"""
import io
import sys

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Entity, Key, KeyRole
from scripts.seed import seed_entities, wipe
from scripts.wa_sim_transform import mangle_image


def check(cond: bool, label: str) -> None:
    print(("  ok    " if cond else "  FAIL  ") + label)
    if not cond:
        sys.exit(1)


def _test_image() -> bytes:
    im = Image.new("RGB", (640, 480))
    px = im.load()
    for y in range(480):
        for x in range(640):
            px[x, y] = (x % 256, y % 256, (x + y) % 256)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def main() -> None:
    client = TestClient(app)
    print("smoke5: reseed base world")
    with SessionLocal() as db:
        wipe(db)
        seed_entities(db)
        db.commit()
        kumaon = db.execute(select(Entity).where(Entity.name == "Kumaon Metals Ltd")).scalar_one()
        maker = db.execute(
            select(Key).where(Key.entity_id == kumaon.id, Key.role == KeyRole.maker)
        ).scalar_one()

    original = _test_image()

    print("smoke5: publish an image communication (standard impact)")
    r = client.post(
        "/api/issuer/communications",
        data={"entity_id": str(kumaon.id), "title": "Smoke5 image", "channel": "image", "impact": "standard"},
        files={"file": ("smoke5.jpg", original, "image/jpeg")},
        headers={"X-Demo-Persona": str(maker.id)},
    ).json()
    check(r["ok"], f"draft created: {r}")
    comm_id = r["data"]["id"]
    client.post(f"/api/issuer/communications/{comm_id}/sign", headers={"X-Demo-Persona": str(maker.id)})
    r = client.post(f"/api/issuer/communications/{comm_id}/cosign", headers={"X-Demo-Persona": str(maker.id)}).json()
    check(r["ok"] and r["data"]["status"] == "published", "published")

    print("smoke5: wa_sim_transform mangles the image")
    mangled = mangle_image(original)
    check(mangled != original and len(mangled) > 0, "mangled bytes differ from original")

    print("smoke5: verify the mangled copy -> VERIFIED via PHASH_MATCH")
    r = client.post(
        "/api/verify",
        data={"channel": "sim"},
        files={"file": ("mangled.jpg", mangled, "image/jpeg")},
    ).json()
    check(r["ok"], f"verify call ok: {r}")
    check(r["data"]["verdict"] == "VERIFIED", f"verdict is VERIFIED: {r['data']['verdict']}")
    check("PHASH_MATCH" in r["data"]["reasons"], f"PHASH_MATCH in reasons: {r['data']['reasons']}")
    check(r["data"]["matched_entity"]["name"] == "Kumaon Metals Ltd", "matched entity correct")
    cert_url = next((b["url"] for b in r["data"]["buttons"] if b["kind"] == "certificate"), None)
    check(bool(cert_url), f"certificate button present: {r['data']['buttons']}")

    print("smoke5: certificate token is single-use")
    token = cert_url.rsplit("/", 1)[-1]
    r1 = client.get(f"/api/{'c'}/{token}")
    check(r1.status_code == 200 and r1.json()["ok"], f"first GET succeeds: {r1.status_code} {r1.text}")
    r2 = client.get(f"/api/{'c'}/{token}")
    check(r2.status_code == 410, f"second GET of used token -> 410: {r2.status_code} {r2.text}")

    print("smoke5: key revocation downgrades a future match to VERIFIED_NOTICE")
    client.post(f"/api/admin/keys/{maker.id}/revoke", json={"reason": "smoke5: simulated compromise"})
    r = client.post(
        "/api/verify", data={"channel": "sim"}, files={"file": ("mangled2.jpg", mangled, "image/jpeg")}
    ).json()
    check(r["ok"] and r["data"]["verdict"] == "VERIFIED_NOTICE",
          f"post-revocation re-verify is VERIFIED_NOTICE: {r['data']['verdict']}")
    check("KEY_REVOKED_AFTER_SIGNING" in r["data"]["reasons"], f"reason present: {r['data']['reasons']}")

    print("SMOKE5 (Epic 5 gate) PASS")


if __name__ == "__main__":
    main()
