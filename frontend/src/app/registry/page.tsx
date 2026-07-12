"use client";

import { useEffect, useState } from "react";
import { getEntity, listEntities, type EntityDetailOut, type EntityOut } from "@/lib/api";

export default function RegistryPage() {
  const [entities, setEntities] = useState<EntityOut[]>([]);
  const [selected, setSelected] = useState<EntityDetailOut | null>(null);

  useEffect(() => {
    listEntities().then((r) => {
      if (r.ok && r.data) setEntities(r.data);
    });
  }, []);

  async function select(id: string) {
    const r = await getEntity(id);
    if (r.ok && r.data) setSelected(r.data);
  }

  return (
    <div className="mx-auto max-w-5xl px-6 py-12">
      <h1 className="font-display text-2xl font-bold text-ink">Registry</h1>
      <p className="mt-1 text-sm text-info">
        SEBI-registered demo entities and their signing keys.
      </p>

      <div className="mt-6 grid gap-6 md:grid-cols-2">
        <div className="rounded border border-hairline bg-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-hairline text-left text-info">
                <th className="p-3 font-medium">Name</th>
                <th className="p-3 font-medium">Kind</th>
                <th className="p-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {entities.map((e) => (
                <tr
                  key={e.id}
                  onClick={() => select(e.id)}
                  className={`cursor-pointer border-b border-hairline last:border-0 hover:bg-paper ${
                    selected?.id === e.id ? "bg-paper" : ""
                  }`}
                >
                  <td className="p-3 text-ink">{e.name}</td>
                  <td className="p-3 text-info">{e.kind}</td>
                  <td className="p-3">
                    <span
                      className={
                        e.status === "active" ? "text-verified" : "text-fake"
                      }
                    >
                      {e.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="rounded border border-hairline bg-card p-4">
          {!selected ? (
            <p className="text-sm text-info">Select an entity to see its detail.</p>
          ) : (
            <div>
              <h2 className="font-display text-lg font-semibold text-ink">{selected.name}</h2>
              <div className="mt-1 font-mono text-xs text-info">{selected.sebi_reg_no}</div>

              <div className="mt-4">
                <div className="text-xs font-medium uppercase tracking-wide text-info">
                  Domains
                </div>
                <ul className="mt-1 space-y-0.5 font-mono text-sm text-ink">
                  {selected.domains.map((d) => (
                    <li key={d.domain}>{d.domain}</li>
                  ))}
                </ul>
              </div>

              <div className="mt-4">
                <div className="text-xs font-medium uppercase tracking-wide text-info">
                  SMS headers
                </div>
                <ul className="mt-1 space-y-0.5 font-mono text-sm text-ink">
                  {selected.sms_headers.map((h) => (
                    <li key={h.header}>{h.header}</li>
                  ))}
                </ul>
              </div>

              <div className="mt-4">
                <div className="text-xs font-medium uppercase tracking-wide text-info">Keys</div>
                <div className="mt-1 space-y-2">
                  {selected.keys.map((k) => (
                    <div key={k.id} className="rounded border border-hairline p-2">
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-ink">{k.label}</span>
                        <span
                          className={`text-xs font-medium ${
                            k.status === "active" ? "text-verified" : "text-fake"
                          }`}
                        >
                          {k.status}
                        </span>
                      </div>
                      <div className="mt-1 font-mono text-xs text-info">{k.role}</div>
                      {k.revoked_at && (
                        <div className="mt-0.5 font-mono text-xs text-fake">
                          revoked {k.revoked_at.slice(0, 10)}
                          {k.revocation_reason ? ` — ${k.revocation_reason}` : ""}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
