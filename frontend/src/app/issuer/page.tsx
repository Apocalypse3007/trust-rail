"use client";

import { useEffect, useMemo, useState } from "react";
import {
  cosignAndPublish,
  createCommunication,
  listCommunications,
  listEntities,
  makerSign,
  revokeCommunication,
  revokeKey,
  type CommOut,
  type EntityOut,
  type KeyOut,
} from "@/lib/api";

const CHANNELS = ["filing", "sms", "email", "video", "image", "pdf", "social"];
const STATUS_COLOR: Record<string, string> = {
  draft: "text-info",
  maker_signed: "text-notice",
  published: "text-verified",
  revoked: "text-fake",
};

export default function IssuerPage() {
  const [entities, setEntities] = useState<EntityOut[]>([]);
  const [entityId, setEntityId] = useState<string>("");
  const [personaKeyId, setPersonaKeyId] = useState<string>("");
  const [comms, setComms] = useState<CommOut[]>([]);
  const [rootDelta, setRootDelta] = useState<{ old: string; next: string } | null>(null);
  const [banner, setBanner] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const [title, setTitle] = useState("");
  const [channel, setChannel] = useState("filing");
  const [impact, setImpact] = useState<"standard" | "market_moving">("standard");
  const [file, setFile] = useState<File | null>(null);
  const [canonicalText, setCanonicalText] = useState("");

  const entity = entities.find((e) => e.id === entityId);
  const persona = entity?.keys.find((k) => k.id === personaKeyId) ?? null;

  useEffect(() => {
    listEntities().then((r) => {
      if (r.ok && r.data) {
        setEntities(r.data);
        const featured = r.data.find((e) => e.keys.length > 1) ?? r.data[0];
        if (featured) {
          setEntityId(featured.id);
          setPersonaKeyId(featured.keys[0]?.id ?? "");
        }
      }
    });
  }, []);

  useEffect(() => {
    if (!entityId) return;
    listCommunications(entityId).then((r) => {
      if (r.ok && r.data) setComms(r.data);
    });
    const keys = entities.find((e) => e.id === entityId)?.keys ?? [];
    if (!keys.some((k) => k.id === personaKeyId)) {
      setPersonaKeyId(keys[0]?.id ?? "");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entityId, entities]);

  async function refreshComms() {
    if (!entityId) return;
    const r = await listCommunications(entityId);
    if (r.ok && r.data) setComms(r.data);
  }

  async function handleCreate() {
    if (!entityId || !personaKeyId || !title) return;
    setBusy(true);
    const r = await createCommunication({
      entityId,
      title,
      channel,
      impact,
      file: file ?? undefined,
      canonicalText: file ? undefined : canonicalText,
      personaKeyId,
    });
    setBusy(false);
    if (r.ok) {
      setDrawerOpen(false);
      setTitle("");
      setFile(null);
      setCanonicalText("");
      await refreshComms();
    } else {
      setBanner(r.error?.message ?? "Could not create draft.");
    }
  }

  async function handleSign(commId: string) {
    setBusy(true);
    const r = await makerSign(commId, personaKeyId);
    setBusy(false);
    if (!r.ok) setBanner(r.error?.message ?? "Sign failed.");
    await refreshComms();
  }

  async function handleCosign(commId: string) {
    setBusy(true);
    const r = await cosignAndPublish(commId, personaKeyId);
    setBusy(false);
    if (r.ok && r.data) {
      setRootDelta({ old: r.data.old_root, next: r.data.new_root });
    } else {
      setBanner(r.error?.message ?? "Publish failed.");
    }
    await refreshComms();
  }

  async function handleRevokeComm(commId: string) {
    setBusy(true);
    const r = await revokeCommunication(commId, personaKeyId);
    setBusy(false);
    if (!r.ok) setBanner(r.error?.message ?? "Withdrawal failed.");
    await refreshComms();
  }

  async function handleSimulateCompromise(key: KeyOut) {
    setBusy(true);
    const r = await revokeKey(key.id, "Simulated key compromise (demo)");
    setBusy(false);
    if (r.ok) {
      setBanner(
        `Key "${key.label}" revoked. Content signed before now stays VERIFIED WITH NOTICE — signatures created after this point will no longer validate.`
      );
      const rr = await listEntities();
      if (rr.ok && rr.data) setEntities(rr.data);
    } else {
      setBanner(r.error?.message ?? "Revoke failed.");
    }
  }

  const personaOptions = useMemo(() => entity?.keys ?? [], [entity]);

  return (
    <div className="mx-auto max-w-4xl px-6 py-12">
      <h1 className="font-display text-2xl font-bold text-ink">Issuer console</h1>
      <p className="mt-1 text-sm text-info">Maker-checker publishing into the transparency log.</p>

      <div className="mt-6 flex flex-wrap gap-3">
        <select
          value={entityId}
          onChange={(e) => setEntityId(e.target.value)}
          className="rounded border border-hairline px-3 py-1.5 text-sm text-ink"
        >
          {entities.map((e) => (
            <option key={e.id} value={e.id}>
              {e.name}
            </option>
          ))}
        </select>
        <select
          value={personaKeyId}
          onChange={(e) => setPersonaKeyId(e.target.value)}
          className="rounded border border-hairline px-3 py-1.5 text-sm text-ink"
        >
          {personaOptions.map((k) => (
            <option key={k.id} value={k.id}>
              {k.label} ({k.role}, {k.status})
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => setDrawerOpen(true)}
          className="ml-auto rounded bg-ink px-4 py-1.5 text-sm font-medium text-paper"
        >
          New communication
        </button>
      </div>

      {persona && (
        <button
          type="button"
          onClick={() => handleSimulateCompromise(persona)}
          disabled={persona.status === "revoked" || busy}
          className="mt-3 rounded border border-fake px-3 py-1.5 text-sm font-medium text-fake disabled:opacity-40"
        >
          Simulate key compromise ({persona.label})
        </button>
      )}

      {rootDelta && (
        <div className="mt-4 rounded border border-verified bg-card p-3 font-mono text-xs text-ink">
          Log root updated: {rootDelta.old.slice(0, 12)}… → {rootDelta.next.slice(0, 12)}…
        </div>
      )}
      {banner && (
        <div className="mt-4 rounded border border-notice bg-card p-3 text-sm text-ink">
          {banner}
          <button
            type="button"
            onClick={() => setBanner(null)}
            className="ml-3 text-xs text-info underline"
          >
            dismiss
          </button>
        </div>
      )}

      <div className="mt-6 rounded border border-hairline bg-card">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-hairline text-left text-info">
              <th className="p-3 font-medium">Title</th>
              <th className="p-3 font-medium">Channel</th>
              <th className="p-3 font-medium">Impact</th>
              <th className="p-3 font-medium">Status</th>
              <th className="p-3" />
            </tr>
          </thead>
          <tbody>
            {comms.map((c) => (
              <tr key={c.id} className="border-b border-hairline last:border-0">
                <td className="p-3 text-ink">{c.title}</td>
                <td className="p-3 text-info">{c.channel}</td>
                <td className="p-3 text-info">{c.impact}</td>
                <td className={`p-3 font-medium ${STATUS_COLOR[c.status] ?? "text-info"}`}>
                  {c.status}
                  {c.log_seq !== null && (
                    <span className="ml-1 font-mono text-xs text-info">#{c.log_seq}</span>
                  )}
                </td>
                <td className="p-3 text-right">
                  {c.status === "draft" && (
                    <button
                      type="button"
                      onClick={() => handleSign(c.id)}
                      disabled={busy}
                      className="rounded border border-hairline px-2 py-1 text-xs font-medium text-ink hover:bg-paper"
                    >
                      Sign (maker)
                    </button>
                  )}
                  {c.status === "maker_signed" && (
                    <button
                      type="button"
                      onClick={() => handleCosign(c.id)}
                      disabled={busy}
                      className="rounded border border-hairline px-2 py-1 text-xs font-medium text-ink hover:bg-paper"
                    >
                      Co-sign & publish
                    </button>
                  )}
                  {c.status === "published" && (
                    <button
                      type="button"
                      onClick={() => handleRevokeComm(c.id)}
                      disabled={busy}
                      className="rounded border border-hairline px-2 py-1 text-xs font-medium text-fake hover:bg-paper"
                    >
                      Withdraw
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {drawerOpen && (
        <div className="fixed inset-0 flex items-center justify-center bg-ink/40 p-4">
          <div className="w-full max-w-md rounded bg-card p-5 shadow-sm">
            <h2 className="font-display text-lg font-semibold text-ink">New communication</h2>
            <div className="mt-4 space-y-3">
              <input
                type="text"
                placeholder="Title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full rounded border border-hairline px-2 py-1.5 text-sm"
              />
              <div className="flex gap-2">
                <select
                  value={channel}
                  onChange={(e) => setChannel(e.target.value)}
                  className="flex-1 rounded border border-hairline px-2 py-1.5 text-sm"
                >
                  {CHANNELS.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
                <select
                  value={impact}
                  onChange={(e) => setImpact(e.target.value as "standard" | "market_moving")}
                  className="flex-1 rounded border border-hairline px-2 py-1.5 text-sm"
                >
                  <option value="standard">standard</option>
                  <option value="market_moving">market_moving</option>
                </select>
              </div>
              <input
                type="file"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="w-full text-sm"
              />
              <div className="text-center text-xs text-info">— or —</div>
              <textarea
                placeholder="Canonical text (for sms/email)"
                value={canonicalText}
                onChange={(e) => setCanonicalText(e.target.value)}
                rows={3}
                className="w-full resize-none rounded border border-hairline px-2 py-1.5 text-sm"
              />
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setDrawerOpen(false)}
                className="rounded border border-hairline px-3 py-1.5 text-sm"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleCreate}
                disabled={busy || !title || (!file && !canonicalText)}
                className="rounded bg-ink px-3 py-1.5 text-sm font-medium text-paper disabled:opacity-40"
              >
                Create draft
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
