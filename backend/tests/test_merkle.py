"""Trust-core gate tests: RFC 6962 tree, inclusion proofs, STHs."""
import hashlib
from datetime import UTC, datetime

from app.trust import merkle
from app.trust.ca import generate_ed25519_keypair
from app.trust.canonical import canonical_json


def _leaves(n: int) -> list[bytes]:
    return [merkle.leaf_hash({"seq": i, "payload": f"entry-{i}"}) for i in range(n)]


def sha(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


class TestRootKnownAnswers:
    """Longhand oracles computed directly with hashlib, independent of the
    library's recursion."""

    def test_empty_tree(self) -> None:
        assert merkle.root_hash([]) == sha(b"")

    def test_single_leaf_root_is_leaf(self) -> None:
        leaf = sha(b"\x00" + canonical_json({"a": 1}))
        assert merkle.root_hash([leaf]) == leaf

    def test_two_leaves(self) -> None:
        l0, l1 = _leaves(2)
        assert merkle.root_hash([l0, l1]) == sha(b"\x01" + l0 + l1)

    def test_three_leaves_splits_at_two(self) -> None:
        l0, l1, l2 = _leaves(3)
        expected = sha(b"\x01" + sha(b"\x01" + l0 + l1) + l2)
        assert merkle.root_hash([l0, l1, l2]) == expected

    def test_five_leaves(self) -> None:
        ls = _leaves(5)
        left = sha(b"\x01" + sha(b"\x01" + ls[0] + ls[1]) + sha(b"\x01" + ls[2] + ls[3]))
        assert merkle.root_hash(ls) == sha(b"\x01" + left + ls[4])


class TestInclusionProofs:
    def test_every_leaf_verifies_for_sizes_1_to_40(self) -> None:
        for n in range(1, 41):
            leaves = _leaves(n)
            root = merkle.root_hash(leaves).hex()
            for i in range(n):
                proof = merkle.inclusion_proof(i, leaves)
                assert merkle.verify_inclusion(
                    proof.leaf_hash, i, proof.audit_path, n, root
                ), f"proof failed for leaf {i} of {n}"

    def test_tampered_entry_fails(self) -> None:
        """Gate case: a modified log entry must not verify against the root."""
        entries = [{"seq": i, "payload": f"entry-{i}"} for i in range(8)]
        leaves = [merkle.leaf_hash(e) for e in entries]
        root = merkle.root_hash(leaves).hex()
        proof = merkle.inclusion_proof(3, leaves)

        tampered = dict(entries[3], payload="entry-3-DOCTORED")
        tampered_leaf = merkle.leaf_hash(tampered).hex()
        assert not merkle.verify_inclusion(
            tampered_leaf, 3, proof.audit_path, 8, root
        )

    def test_tampered_audit_path_fails(self) -> None:
        leaves = _leaves(8)
        root = merkle.root_hash(leaves).hex()
        proof = merkle.inclusion_proof(2, leaves)
        bad_path = list(proof.audit_path)
        bad_path[0] = sha(b"evil").hex()
        assert not merkle.verify_inclusion(proof.leaf_hash, 2, bad_path, 8, root)

    def test_wrong_root_fails(self) -> None:
        leaves = _leaves(8)
        proof = merkle.inclusion_proof(2, leaves)
        assert not merkle.verify_inclusion(
            proof.leaf_hash, 2, proof.audit_path, 8, sha(b"other").hex()
        )

    def test_wrong_index_fails(self) -> None:
        leaves = _leaves(8)
        root = merkle.root_hash(leaves).hex()
        proof = merkle.inclusion_proof(2, leaves)
        assert not merkle.verify_inclusion(proof.leaf_hash, 5, proof.audit_path, 8, root)

    def test_garbage_input_returns_false_not_raise(self) -> None:
        assert not merkle.verify_inclusion("zz-not-hex", 0, ["also-bad"], 4, "nope")
        assert not merkle.verify_inclusion(sha(b"x").hex(), -1, [], 4, sha(b"y").hex())
        assert not merkle.verify_inclusion(sha(b"x").hex(), 9, [], 4, sha(b"y").hex())

    def test_append_only_root_changes(self) -> None:
        leaves = _leaves(6)
        old_root = merkle.root_hash(leaves)
        leaves.append(merkle.leaf_hash({"seq": 6, "payload": "entry-6"}))
        assert merkle.root_hash(leaves) != old_root
        # old proofs still verify against the OLD root (append-only history)
        proof = merkle.inclusion_proof(1, leaves[:6])
        assert merkle.verify_inclusion(proof.leaf_hash, 1, proof.audit_path, 6, old_root.hex())


class TestSTH:
    def test_sign_and_verify(self) -> None:
        kp = generate_ed25519_keypair()
        ts = datetime.now(UTC)
        root = merkle.root_hash(_leaves(5)).hex()
        sig = merkle.sign_sth(5, root, ts, kp.private_key_b64)
        assert merkle.verify_sth(5, root, ts, sig, kp.public_key_b64)
        # any field change breaks the signature
        assert not merkle.verify_sth(6, root, ts, sig, kp.public_key_b64)
        assert not merkle.verify_sth(5, sha(b"z").hex(), ts, sig, kp.public_key_b64)
        other = generate_ed25519_keypair()
        assert not merkle.verify_sth(5, root, ts, sig, other.public_key_b64)
