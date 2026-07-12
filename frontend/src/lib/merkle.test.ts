import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { verifyInclusion, verifySth } from "./merkle";

// Same fixture Python's test_merkle.py checks itself against — regenerate
// both sides with `python -m scripts.gen_merkle_vectors` (carry-forward #1).
interface Case {
  label: string;
  leaf_hash: string;
  leaf_index: number;
  audit_path: string[];
  tree_size: number;
  root_hash: string;
  expected: boolean;
}
interface SthCase {
  tree_size: number;
  root_hash: string;
  timestamp: string;
  sig: string;
  registry_public_key: string;
}

const fixturePath = join(__dirname, "..", "..", "..", "fixtures", "merkle_vectors.json");
const { cases, sth_case: sthCase } = JSON.parse(readFileSync(fixturePath, "utf-8")) as {
  cases: Case[];
  sth_case: SthCase;
};

describe("verifyInclusion matches the shared Python fixture", () => {
  it("has the expected vector count", () => {
    expect(cases.length).toBeGreaterThan(800);
  });

  for (const c of cases) {
    it(c.label, async () => {
      const result = await verifyInclusion(
        c.leaf_hash,
        c.leaf_index,
        c.audit_path,
        c.tree_size,
        c.root_hash
      );
      expect(result).toBe(c.expected);
    });
  }
});

describe("verifySth against a Python-signed vector (real cross-language check)", () => {
  it("verifies a signature produced by Python's canonical_json + PyNaCl", () => {
    const ok = verifySth(
      sthCase.tree_size,
      sthCase.root_hash,
      sthCase.timestamp,
      sthCase.sig,
      sthCase.registry_public_key
    );
    expect(ok).toBe(true);
  });

  it("rejects a tampered field", () => {
    const ok = verifySth(
      sthCase.tree_size + 1,
      sthCase.root_hash,
      sthCase.timestamp,
      sthCase.sig,
      sthCase.registry_public_key
    );
    expect(ok).toBe(false);
  });

  it("rejects the wrong public key", () => {
    const ok = verifySth(
      sthCase.tree_size,
      sthCase.root_hash,
      sthCase.timestamp,
      sthCase.sig,
      sthCase.root_hash // 32 valid-looking but wrong bytes, not the real key
    );
    expect(ok).toBe(false);
  });
});
