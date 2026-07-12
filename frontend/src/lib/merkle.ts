// RFC 6962 / RFC 9162 Merkle-proof verification — TypeScript mirror of
// backend/app/trust/merkle.py's `verify_inclusion` and `verify_sth` (spec
// §7.3). Keep the control flow byte-for-byte identical to the Python side;
// both are tested against the same fixture (fixtures/merkle_vectors.json —
// see merkle.test.ts and backend/tests/test_merkle.py).
import nacl from "tweetnacl";
import { canonicalJsonBytes } from "./canonical";

const NODE_PREFIX = 0x01;

function hexToBytes(hex: string): Uint8Array {
  if (hex.length % 2 !== 0) throw new Error("odd-length hex");
  const out = new Uint8Array(hex.length / 2);
  for (let i = 0; i < out.length; i++) {
    const byte = Number.parseInt(hex.slice(i * 2, i * 2 + 2), 16);
    if (Number.isNaN(byte)) throw new Error("invalid hex");
    out[i] = byte;
  }
  return out;
}

function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

function base64ToBytes(b64: string): Uint8Array {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

async function nodeHash(left: Uint8Array, right: Uint8Array): Promise<Uint8Array> {
  const buf = new Uint8Array(1 + left.length + right.length);
  buf[0] = NODE_PREFIX;
  buf.set(left, 1);
  buf.set(right, 1 + left.length);
  const digest = await crypto.subtle.digest("SHA-256", buf);
  return new Uint8Array(digest);
}

/** Pure iterative verification (RFC 9162 §2.1.3.2). Never throws. */
export async function verifyInclusion(
  leafHashHex: string,
  leafIndex: number,
  auditPathHex: string[],
  treeSize: number,
  rootHashHex: string
): Promise<boolean> {
  try {
    if (leafIndex < 0 || treeSize < 1 || leafIndex >= treeSize) return false;
    let fn = leafIndex;
    let sn = treeSize - 1;
    let r = hexToBytes(leafHashHex);
    if (r.length !== 32) return false;

    for (const pHex of auditPathHex) {
      const p = hexToBytes(pHex);
      if (p.length !== 32) return false;
      if (sn === 0) return false;
      if (fn % 2 === 1 || fn === sn) {
        r = await nodeHash(p, r);
        if (fn % 2 === 0) {
          while (fn % 2 === 0 && fn !== 0) {
            fn = Math.floor(fn / 2);
            sn = Math.floor(sn / 2);
          }
        }
      } else {
        r = await nodeHash(r, p);
      }
      fn = Math.floor(fn / 2);
      sn = Math.floor(sn / 2);
    }
    return sn === 0 && bytesToHex(r) === rootHashHex;
  } catch {
    return false;
  }
}

/** Same combine steps as verifyInclusion, but yields each intermediate hash
 * for the certificate/log-explorer's animated proof (spec §10.2). */
export async function* verifyInclusionSteps(
  leafHashHex: string,
  leafIndex: number,
  auditPathHex: string[]
): AsyncGenerator<{ combinedWith: string; result: string; side: "left" | "right" }> {
  let fn = leafIndex;
  let r = hexToBytes(leafHashHex);
  for (const pHex of auditPathHex) {
    const p = hexToBytes(pHex);
    const onRight = fn % 2 === 1;
    r = onRight ? await nodeHash(p, r) : await nodeHash(r, p);
    yield { combinedWith: pHex, result: bytesToHex(r), side: onRight ? "left" : "right" };
    fn = Math.floor(fn / 2);
  }
}

/** Re-serializes the server's own STH fields — never generates a timestamp
 * itself, since Python's canonical_json({timestamp: dt.isoformat(), ...})
 * must be reproduced byte-for-byte from the exact string the API returned. */
function sthPayloadBytes(treeSize: number, rootHashHex: string, timestampIso: string): Uint8Array {
  return canonicalJsonBytes({
    tree_size: treeSize,
    root_hash: rootHashHex,
    timestamp: timestampIso,
  });
}

export function verifySth(
  treeSize: number,
  rootHashHex: string,
  timestampIso: string,
  sigB64: string,
  registryPublicKeyB64: string
): boolean {
  try {
    const msg = sthPayloadBytes(treeSize, rootHashHex, timestampIso);
    const sig = base64ToBytes(sigB64);
    const pub = base64ToBytes(registryPublicKeyB64);
    return nacl.sign.detached.verify(msg, sig, pub);
  } catch {
    return false;
  }
}
