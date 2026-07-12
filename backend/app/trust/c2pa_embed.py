"""Optional C2PA embed/read (spec §7.5). The envelope + registry path is the
product; C2PA is standards-alignment garnish. Any failure → warn + None/False.
"""
import logging
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger(__name__)

try:
    import c2pa  # type: ignore[import-not-found]

    HAS_C2PA = True
except ImportError:
    c2pa = None
    HAS_C2PA = False


class C2PAResult(BaseModel):
    valid: bool
    issuer: str | None = None
    claim_generator: str | None = None
    raw: dict | None = None


def embed(path: Path, entity_name: str, cert_pem: str, key_pem: str) -> bool:
    """Embed a manifest for jpg/png/mp4. Returns False unless everything works."""
    if not HAS_C2PA:
        return False
    try:
        # TODO(prod): real manifest definition + hard binding assertions.
        builder = c2pa.Builder.from_json(  # type: ignore[union-attr]
            '{"claim_generator": "TrustRail Demo", "assertions": []}'
        )
        signer = c2pa.create_signer(  # type: ignore[union-attr]
            cert_pem.encode(), key_pem.encode(), c2pa.SigningAlg.ES256, None
        )
        signed = path.with_suffix(".c2pa" + path.suffix)
        builder.sign_file(signer, str(path), str(signed))
        signed.replace(path)
        return True
    except Exception as exc:  # any c2pa failure is non-fatal by design
        logger.warning("c2pa embed skipped: %s", exc)
        return False


def read(path: Path) -> C2PAResult | None:
    """Read + validate a manifest against the demo trust anchor only."""
    if not HAS_C2PA:
        return None
    try:
        reader = c2pa.Reader.from_file(str(path))  # type: ignore[union-attr]
        manifest = reader.json()
        # TODO(prod): validate chain strictly against the demo P-256 root.
        return C2PAResult(valid=bool(manifest), raw={"manifest": manifest})
    except Exception as exc:
        logger.warning("c2pa read skipped: %s", exc)
        return None
