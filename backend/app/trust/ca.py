"""TrustRail Demo Root — key material generation and persistence.

DEMO ONLY: private keys are stored as base64 JSON on disk and in the DB so
the demo is reproducible and inspectable. TODO(prod): HSM-held keys, real
CA hierarchy, key ceremonies.
"""
import base64
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey
from pydantic import BaseModel

TRUST_FILE = "trust_root.json"
P256_ROOT_KEY_FILE = "p256_root_key.pem"
P256_ROOT_CERT_FILE = "p256_root_cert.pem"


class Ed25519KeyPair(BaseModel):
    public_key_b64: str
    private_key_b64: str


class TrustMaterial(BaseModel):
    note: str = "TrustRail Demo Root — NOT a real authority"
    created_at: datetime
    root: Ed25519KeyPair
    registry_sth: Ed25519KeyPair


def generate_ed25519_keypair() -> Ed25519KeyPair:
    sk = SigningKey.generate()
    return Ed25519KeyPair(
        public_key_b64=base64.b64encode(bytes(sk.verify_key)).decode(),
        private_key_b64=base64.b64encode(bytes(sk)).decode(),
    )


def sign_bytes(private_key_b64: str, data: bytes) -> str:
    sk = SigningKey(base64.b64decode(private_key_b64))
    return base64.b64encode(sk.sign(data).signature).decode()


def verify_bytes(public_key_b64: str, data: bytes, sig_b64: str) -> bool:
    try:
        vk = VerifyKey(base64.b64decode(public_key_b64))
        vk.verify(data, base64.b64decode(sig_b64))
        return True
    except (BadSignatureError, ValueError, TypeError):
        return False


def ensure_trust_material(trust_dir: Path) -> TrustMaterial:
    """Create the demo root + registry STH keypairs on first run; load after."""
    trust_dir.mkdir(parents=True, exist_ok=True)
    path = trust_dir / TRUST_FILE
    if path.exists():
        return TrustMaterial.model_validate_json(path.read_text())
    material = TrustMaterial(
        created_at=datetime.now(UTC),
        root=generate_ed25519_keypair(),
        registry_sth=generate_ed25519_keypair(),
    )
    path.write_text(material.model_dump_json(indent=2))
    return material


# --- Optional P-256 X.509 chain (used only when c2pa-python is installed) ---

def ensure_p256_root(trust_dir: Path) -> tuple[ec.EllipticCurvePrivateKey, x509.Certificate]:
    """Self-signed P-256 root for C2PA leaf issuance. Create-or-load."""
    trust_dir.mkdir(parents=True, exist_ok=True)
    key_path = trust_dir / P256_ROOT_KEY_FILE
    cert_path = trust_dir / P256_ROOT_CERT_FILE
    if key_path.exists() and cert_path.exists():
        key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
        assert isinstance(key, ec.EllipticCurvePrivateKey)
        return key, x509.load_pem_x509_certificate(cert_path.read_bytes())

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "TrustRail Demo Root (NOT a real authority)")]
    )
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=1), critical=True)
        .sign(key, hashes.SHA256())
    )
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return key, cert


def issue_p256_leaf(
    trust_dir: Path, entity_name: str
) -> tuple[ec.EllipticCurvePrivateKey, x509.Certificate]:
    """Entity leaf cert chained to the P-256 root. EKU per c2pa signing rules."""
    root_key, root_cert = ensure_p256_root(trust_dir)
    key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, entity_name)]))
        .issuer_name(root_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.ExtendedKeyUsage(
                [ExtendedKeyUsageOID.EMAIL_PROTECTION, ExtendedKeyUsageOID.CLIENT_AUTH]
            ),
            critical=False,
        )
        .sign(root_key, hashes.SHA256())
    )
    return key, cert
