"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, XCircle, Loader2 } from "lucide-react";
import {
  getInclusionProof,
  getLogRoot,
  listLogEntries,
  type InclusionProof,
  type LogEntryOut,
  type LogRoot,
} from "@/lib/api";
import { verifyInclusion, verifySth } from "@/lib/merkle";

type SthState = "checking" | "valid" | "invalid";

export default function LogPage() {
  const [root, setRoot] = useState<LogRoot | null>(null);
  const [sthState, setSthState] = useState<SthState>("checking");
  const [entries, setEntries] = useState<LogEntryOut[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [proof, setProof] = useState<InclusionProof | null>(null);
  const [proofState, setProofState] = useState<SthState>("checking");

  useEffect(() => {
    getLogRoot().then((r) => {
      if (r.ok && r.data) {
        setRoot(r.data);
        if (r.data.sth_sig && r.data.timestamp) {
          const ok = verifySth(
            r.data.tree_size,
            r.data.root_hash,
            r.data.timestamp,
            r.data.sth_sig,
            r.data.registry_public_key
          );
          setSthState(ok ? "valid" : "invalid");
        }
      }
    });
    listLogEntries(50).then((r) => {
      if (r.ok && r.data) setEntries(r.data);
    });
  }, []);

  async function verifyEntry(seq: number) {
    setSelected(seq);
    setProof(null);
    setProofState("checking");
    const r = await getInclusionProof(seq);
    if (!r.ok || !r.data) {
      setProofState("invalid");
      return;
    }
    setProof(r.data);
    const ok = await verifyInclusion(
      r.data.leaf_hash,
      r.data.leaf_index,
      r.data.audit_path,
      r.data.tree_size,
      r.data.root_hash
    );
    setProofState(ok ? "valid" : "invalid");
  }

  function entryKind(entry: Record<string, unknown>): string {
    return typeof entry.kind === "string" ? entry.kind : "publish";
  }

  return (
    <div className="mx-auto max-w-4xl px-6 py-12">
      <h1 className="font-display text-2xl font-bold text-ink">Transparency log</h1>
      <p className="mt-1 text-sm text-info">
        Append-only, tamper-evident record of every publish and revocation.
      </p>

      {root && (
        <div className="mt-6 rounded border border-hairline bg-card p-4">
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2 font-mono text-sm">
            <span className="text-info">
              tree size <span className="text-ink">{root.tree_size}</span>
            </span>
            <span className="break-all text-info">
              root <span className="text-ink">{root.root_hash}</span>
            </span>
          </div>
          <div className="mt-2 flex items-center gap-1.5 text-sm">
            {sthState === "checking" && <Loader2 className="h-4 w-4 animate-spin text-info" />}
            {sthState === "valid" && <CheckCircle2 className="h-4 w-4 text-verified" />}
            {sthState === "invalid" && <XCircle className="h-4 w-4 text-fake" />}
            <span className={sthState === "invalid" ? "text-fake" : "text-info"}>
              STH signature {sthState === "checking" ? "checking…" : sthState === "valid" ? "verified against the registry public key" : "FAILED to verify"}
            </span>
          </div>
        </div>
      )}

      <div className="mt-6 rounded border border-hairline bg-card">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-hairline text-left text-info">
              <th className="p-3 font-medium">Seq</th>
              <th className="p-3 font-medium">Kind</th>
              <th className="p-3 font-medium">Leaf hash</th>
              <th className="p-3 font-medium">Created</th>
              <th className="p-3" />
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <tr
                key={e.seq}
                className={`border-b border-hairline last:border-0 ${
                  selected === e.seq ? "bg-paper" : ""
                }`}
              >
                <td className="p-3 font-mono text-ink">#{e.seq}</td>
                <td className="p-3 text-ink">{entryKind(e.entry)}</td>
                <td className="p-3 font-mono text-xs text-info">{e.leaf_hash.slice(0, 16)}…</td>
                <td className="p-3 text-xs text-info">{e.created_at.slice(0, 19)}</td>
                <td className="p-3">
                  <button
                    type="button"
                    onClick={() => verifyEntry(e.seq)}
                    className="rounded border border-hairline px-2 py-1 text-xs font-medium text-ink hover:bg-paper"
                  >
                    Verify inclusion proof
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selected !== null && (
        <div className="mt-6 rounded border border-hairline bg-card p-4">
          <h2 className="font-display text-lg font-semibold text-ink">
            Inclusion proof for #{selected}
          </h2>
          {proof && (
            <div className="mt-3 space-y-2 font-mono text-xs text-info">
              <div>
                leaf <span className="break-all text-ink">{proof.leaf_hash}</span>
              </div>
              <div>
                index {proof.leaf_index} of {proof.tree_size}
              </div>
              <div>audit path ({proof.audit_path.length} hashes)</div>
              {proof.audit_path.map((h, i) => (
                <div key={i} className="pl-4">
                  {h.slice(0, 24)}…
                </div>
              ))}
            </div>
          )}
          <div className="mt-3 flex items-center gap-1.5 text-sm">
            {proofState === "checking" && <Loader2 className="h-4 w-4 animate-spin text-info" />}
            {proofState === "valid" && <CheckCircle2 className="h-4 w-4 text-verified" />}
            {proofState === "invalid" && <XCircle className="h-4 w-4 text-fake" />}
            <span className={proofState === "invalid" ? "text-fake" : "text-ink"}>
              {proofState === "checking"
                ? "Verifying, hash by hash…"
                : proofState === "valid"
                  ? "Proof verifies — this entry is provably part of the current log."
                  : "Proof failed to verify."}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
