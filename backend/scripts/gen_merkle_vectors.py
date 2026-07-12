"""Generates the shared Merkle test-vector fixture consumed by both
test_merkle.py (Python) and the TypeScript verify_inclusion mirror
(frontend/src/lib/merkle.test.ts) — spec carry-forward item #1: the two
implementations must be tested against the exact same vectors.
"""
import hashlib
import json
from pathlib import Path

from app.trust import merkle

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = REPO_ROOT / "fixtures" / "merkle_vectors.json"


def _leaves(n: int) -> list[bytes]:
    return [merkle.leaf_hash({"seq": i, "payload": f"entry-{i}"}) for i in range(n)]


def main() -> None:
    cases: list[dict] = []

    # every leaf, every tree size 1-40 (mirrors test_merkle.py's exhaustive check)
    for n in range(1, 41):
        leaves = _leaves(n)
        root = merkle.root_hash(leaves).hex()
        for i in range(n):
            proof = merkle.inclusion_proof(i, leaves)
            cases.append(
                {
                    "label": f"valid_n{n}_i{i}",
                    "leaf_hash": proof.leaf_hash,
                    "leaf_index": i,
                    "audit_path": proof.audit_path,
                    "tree_size": n,
                    "root_hash": root,
                    "expected": True,
                }
            )

    # tamper cases (mirrors test_merkle.py's TestInclusionProofs)
    entries = [{"seq": i, "payload": f"entry-{i}"} for i in range(8)]
    leaves8 = [merkle.leaf_hash(e) for e in entries]
    root8 = merkle.root_hash(leaves8).hex()
    proof3 = merkle.inclusion_proof(3, leaves8)
    tampered_leaf = merkle.leaf_hash(dict(entries[3], payload="entry-3-DOCTORED")).hex()
    cases.append(
        {
            "label": "tampered_entry",
            "leaf_hash": tampered_leaf,
            "leaf_index": 3,
            "audit_path": proof3.audit_path,
            "tree_size": 8,
            "root_hash": root8,
            "expected": False,
        }
    )

    proof2 = merkle.inclusion_proof(2, leaves8)
    bad_path = list(proof2.audit_path)
    bad_path[0] = hashlib.sha256(b"evil").hexdigest()
    cases.append(
        {
            "label": "tampered_audit_path",
            "leaf_hash": proof2.leaf_hash,
            "leaf_index": 2,
            "audit_path": bad_path,
            "tree_size": 8,
            "root_hash": root8,
            "expected": False,
        }
    )
    cases.append(
        {
            "label": "wrong_root",
            "leaf_hash": proof2.leaf_hash,
            "leaf_index": 2,
            "audit_path": proof2.audit_path,
            "tree_size": 8,
            "root_hash": hashlib.sha256(b"other").hexdigest(),
            "expected": False,
        }
    )
    cases.append(
        {
            "label": "wrong_index",
            "leaf_hash": proof2.leaf_hash,
            "leaf_index": 5,
            "audit_path": proof2.audit_path,
            "tree_size": 8,
            "root_hash": root8,
            "expected": False,
        }
    )
    cases.append(
        {
            "label": "garbage_hash",
            "leaf_hash": "zz-not-hex",
            "leaf_index": 0,
            "audit_path": ["also-bad"],
            "tree_size": 4,
            "root_hash": "nope",
            "expected": False,
        }
    )
    cases.append(
        {
            "label": "negative_index",
            "leaf_hash": hashlib.sha256(b"x").hexdigest(),
            "leaf_index": -1,
            "audit_path": [],
            "tree_size": 4,
            "root_hash": hashlib.sha256(b"y").hexdigest(),
            "expected": False,
        }
    )
    cases.append(
        {
            "label": "index_out_of_range",
            "leaf_hash": hashlib.sha256(b"x").hexdigest(),
            "leaf_index": 9,
            "audit_path": [],
            "tree_size": 4,
            "root_hash": hashlib.sha256(b"y").hexdigest(),
            "expected": False,
        }
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({"cases": cases}, indent=2))
    print(f"wrote {len(cases)} vectors to {OUT_PATH}")


if __name__ == "__main__":
    main()
