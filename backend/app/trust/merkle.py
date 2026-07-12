"""RFC 6962-style Merkle tree for the transparency log (spec §7.3).

leaf_hash = SHA256(0x00 || canonical_json(entry))
node      = SHA256(0x01 || left || right)

Root/proof generation is recursive over the full leaf list — the demo tree
is small, and recomputing from DB rows on each append keeps it simple and
correct. `verify_inclusion` is the independent iterative algorithm from
RFC 9162 §2.1.3.2 and is mirrored in TypeScript for the log explorer.
"""
import hashlib
from datetime import datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from app.trust.ca import sign_bytes, verify_bytes
from app.trust.canonical import canonical_json

LEAF_PREFIX = b"\x00"
NODE_PREFIX = b"\x01"


class InclusionProof(BaseModel):
    leaf_index: int
    leaf_hash: str  # hex
    audit_path: list[str]  # hex, leaf-to-root order
    tree_size: int
    root_hash: str  # hex


def leaf_hash(entry: dict[str, Any]) -> bytes:
    return hashlib.sha256(LEAF_PREFIX + canonical_json(entry)).digest()


def _node(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(NODE_PREFIX + left + right).digest()


def _split(n: int) -> int:
    """Largest power of two strictly less than n (n >= 2)."""
    k = 1
    while k * 2 < n:
        k *= 2
    return k


def root_hash(leaves: list[bytes]) -> bytes:
    """Merkle tree head over already-hashed leaves (RFC 6962 §2.1)."""
    n = len(leaves)
    if n == 0:
        return hashlib.sha256(b"").digest()
    if n == 1:
        return leaves[0]
    k = _split(n)
    return _node(root_hash(leaves[:k]), root_hash(leaves[k:]))


def audit_path(index: int, leaves: list[bytes]) -> list[bytes]:
    """Inclusion proof path for leaves[index] (RFC 6962 §2.1.1)."""
    n = len(leaves)
    if index >= n or index < 0:
        raise IndexError(f"leaf index {index} out of range for tree size {n}")
    if n == 1:
        return []
    k = _split(n)
    if index < k:
        return audit_path(index, leaves[:k]) + [root_hash(leaves[k:])]
    return audit_path(index - k, leaves[k:]) + [root_hash(leaves[:k])]


def inclusion_proof(index: int, leaves: list[bytes]) -> InclusionProof:
    return InclusionProof(
        leaf_index=index,
        leaf_hash=leaves[index].hex(),
        audit_path=[h.hex() for h in audit_path(index, leaves)],
        tree_size=len(leaves),
        root_hash=root_hash(leaves).hex(),
    )


def verify_inclusion(
    leaf_hash_hex: str,
    leaf_index: int,
    audit_path_hex: list[str],
    tree_size: int,
    root_hash_hex: str,
) -> bool:
    """Pure iterative verification (RFC 9162 §2.1.3.2). Never raises.

    Mirrored in TypeScript at frontend/src/lib/merkle.ts — keep in sync.
    """
    try:
        if leaf_index < 0 or tree_size < 1 or leaf_index >= tree_size:
            return False
        fn, sn = leaf_index, tree_size - 1
        r = bytes.fromhex(leaf_hash_hex)
        if len(r) != 32:
            return False
        for p_hex in audit_path_hex:
            p = bytes.fromhex(p_hex)
            if len(p) != 32:
                return False
            if sn == 0:
                return False
            if fn % 2 == 1 or fn == sn:
                r = _node(p, r)
                if fn % 2 == 0:
                    while fn % 2 == 0 and fn != 0:
                        fn //= 2
                        sn //= 2
            else:
                r = _node(r, p)
            fn //= 2
            sn //= 2
        return sn == 0 and r.hex() == root_hash_hex
    except (ValueError, TypeError):
        return False


# --- Signed tree heads ---

def sth_payload(tree_size: int, root_hash_hex: str, timestamp: datetime) -> bytes:
    return canonical_json(
        {
            "tree_size": tree_size,
            "root_hash": root_hash_hex,
            "timestamp": timestamp.isoformat(),
        }
    )


def sign_sth(
    tree_size: int, root_hash_hex: str, timestamp: datetime, registry_private_b64: str
) -> str:
    return sign_bytes(registry_private_b64, sth_payload(tree_size, root_hash_hex, timestamp))


def verify_sth(
    tree_size: int,
    root_hash_hex: str,
    timestamp: datetime,
    sig_b64: str,
    registry_public_b64: str,
) -> bool:
    return verify_bytes(
        registry_public_b64, sth_payload(tree_size, root_hash_hex, timestamp), sig_b64
    )


# --- DB-backed transparency log (append + proofs over log_entries rows) ---
# Recomputing the whole tree from rows on each append is deliberate: demo
# scale, simple and correct (spec §7.3). TODO(prod): incremental tree store.

LATEST_ROOT_CACHE_KEY = "trustrail:log:latest_sth"


def load_leaves(db: "Session") -> list[bytes]:  # noqa: F821
    from sqlalchemy import select

    from app.models import LogEntry

    rows = db.execute(select(LogEntry.leaf_hash).order_by(LogEntry.seq)).scalars().all()
    return [bytes.fromhex(h) for h in rows]


def append_entry(db: "Session", entry: dict, registry_private_b64: str):  # noqa: F821
    """Append one entry: new leaf, recomputed root, signed tree head.
    Returns the new LogEntry (not yet committed). Invalidate the Redis root
    cache after commit."""
    from datetime import UTC

    from app.models import LogEntry

    leaves = load_leaves(db)
    leaf = leaf_hash(entry)
    leaves.append(leaf)
    new_root = root_hash(leaves).hex()
    now = datetime.now(UTC)
    row = LogEntry(
        seq=len(leaves) - 1,
        leaf_hash=leaf.hex(),
        entry=entry,
        tree_size=len(leaves),
        root_hash=new_root,
        sth_sig=sign_sth(len(leaves), new_root, now, registry_private_b64),
        created_at=now,
    )
    db.add(row)
    return row


def proof_for_seq(db: "Session", seq: int) -> InclusionProof | None:  # noqa: F821
    """Inclusion proof for entry `seq` against the CURRENT tree head."""
    leaves = load_leaves(db)
    if seq < 0 or seq >= len(leaves):
        return None
    return inclusion_proof(seq, leaves)
