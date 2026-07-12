"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ComposableMap,
  Geographies,
  Geography,
} from "react-simple-maps";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getTelemetrySummary, type TelemetrySummary } from "@/lib/api";

const GEO_URL = "/india_states.json";
const POLL_MS = 10_000;

// spec §14's 12 weighted states -> react-simple-maps' st_nm property
const STATE_CODE_TO_NAME: Record<string, string> = {
  "IN-MH": "Maharashtra",
  "IN-KA": "Karnataka",
  "IN-RJ": "Rajasthan",
  "IN-DL": "Delhi",
  "IN-UP": "Uttar Pradesh",
  "IN-GJ": "Gujarat",
  "IN-TN": "Tamil Nadu",
  "IN-TS": "Telangana",
  "IN-WB": "West Bengal",
  "IN-MP": "Madhya Pradesh",
  "IN-HR": "Haryana",
  "IN-PB": "Punjab",
};

function shade(count: number, max: number): string {
  if (count === 0) return "#F7F5F0";
  const t = max > 0 ? count / max : 0;
  // interpolate paper -> fake (vermilion), matching the design tokens
  const from = { r: 0xf7, g: 0xf5, b: 0xf0 };
  const to = { r: 0xc6, g: 0x36, b: 0x2b };
  const r = Math.round(from.r + (to.r - from.r) * t);
  const g = Math.round(from.g + (to.g - from.g) * t);
  const b = Math.round(from.b + (to.b - from.b) * t);
  return `rgb(${r},${g},${b})`;
}

export default function SupervisionPage() {
  const [summary, setSummary] = useState<TelemetrySummary | null>(null);
  const [hover, setHover] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const r = await getTelemetrySummary();
      if (!cancelled && r.ok && r.data) setSummary(r.data);
    }
    load();
    const id = setInterval(load, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const totals = summary?.totals_by_verdict ?? {};
  const total24h = Object.values(totals).reduce((a, b) => a + b, 0);
  const flagged =
    (totals["LIKELY_FAKE"] ?? 0) + (totals["OFFICIAL_CLAIM_UNVERIFIED"] ?? 0);
  const pctFlagged = total24h > 0 ? Math.round((flagged / total24h) * 100) : 0;

  const byNameCount = useMemo(() => {
    const map: Record<string, number> = {};
    for (const row of summary?.by_state ?? []) {
      const name = STATE_CODE_TO_NAME[row.state_code];
      if (name) map[name] = row.count_flagged;
    }
    return map;
  }, [summary]);
  const maxCount = Math.max(1, ...Object.values(byNameCount));

  return (
    <div className="mx-auto max-w-5xl px-6 py-12">
      <h1 className="font-display text-2xl font-bold text-ink">Supervision</h1>
      <p className="mt-1 text-sm text-info">
        Where impersonation attempts are landing, live. Refreshes every 10s.
      </p>

      <div className="mt-6 grid grid-cols-3 gap-4">
        <div className="rounded border border-hairline bg-card p-4">
          <div className="font-mono text-2xl text-ink">{total24h}</div>
          <div className="text-xs text-info">verifications (14d)</div>
        </div>
        <div className="rounded border border-hairline bg-card p-4">
          <div className="font-mono text-2xl text-fake">{pctFlagged}%</div>
          <div className="text-xs text-info">flagged</div>
        </div>
        <div className="rounded border border-hairline bg-card p-4">
          <div className="font-mono text-2xl text-ink">
            {Object.entries(totals).sort((a, b) => b[1] - a[1])[0]?.[0] ?? "—"}
          </div>
          <div className="text-xs text-info">top verdict</div>
        </div>
      </div>

      <div className="mt-6 grid gap-6 md:grid-cols-2">
        <div className="rounded border border-hairline bg-card p-3">
          <div className="mb-2 text-xs font-medium uppercase tracking-wide text-info">
            Flagged reports by state
          </div>
          <ComposableMap
            projection="geoMercator"
            projectionConfig={{ center: [82, 22], scale: 900 }}
            width={380}
            height={420}
          >
            <Geographies geography={GEO_URL}>
              {({ geographies }) =>
                geographies.map((geo) => {
                  const name = geo.properties.st_nm as string;
                  const count = byNameCount[name] ?? 0;
                  return (
                    <Geography
                      key={geo.rsmKey}
                      geography={geo}
                      onMouseEnter={() => setHover(`${name}: ${count} flagged`)}
                      onMouseLeave={() => setHover(null)}
                      style={{
                        default: {
                          fill: shade(count, maxCount),
                          stroke: "#E4E0D6",
                          strokeWidth: 0.5,
                          outline: "none",
                        },
                        hover: { fill: "#8A6D1D", outline: "none" },
                        pressed: { outline: "none" },
                      }}
                    />
                  );
                })
              }
            </Geographies>
          </ComposableMap>
          <div className="h-5 text-center text-xs text-info">{hover}</div>
        </div>

        <div className="rounded border border-hairline bg-card p-3">
          <div className="mb-2 text-xs font-medium uppercase tracking-wide text-info">
            Top impersonated entities
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={summary?.top_impersonated ?? []} layout="vertical" margin={{ left: 24 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E4E0D6" />
              <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="entity" width={140} tick={{ fontSize: 11 }} />
              <RechartsTooltip />
              <Bar dataKey="count" fill="#C6362B" radius={2} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="mt-6 rounded border border-hairline bg-card">
        <div className="border-b border-hairline p-3 text-xs font-medium uppercase tracking-wide text-info">
          Campaign clusters
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-hairline text-left text-info">
              <th className="p-3 font-medium">Campaign</th>
              <th className="p-3 font-medium">Count</th>
              <th className="p-3 font-medium">Last seen</th>
              <th className="p-3 font-medium">Channels</th>
            </tr>
          </thead>
          <tbody>
            {(summary?.campaigns ?? []).map((c) => (
              <tr key={c.campaign} className="border-b border-hairline last:border-0">
                <td className="p-3 font-mono text-fake">{c.campaign}</td>
                <td className="p-3 text-ink">{c.count}</td>
                <td className="p-3 text-xs text-info">{c.last_seen.slice(0, 19)}</td>
                <td className="p-3 text-info">{c.channels.join(", ")}</td>
              </tr>
            ))}
            {(summary?.campaigns ?? []).length === 0 && (
              <tr>
                <td className="p-3 text-info" colSpan={4}>
                  No campaign clusters yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
