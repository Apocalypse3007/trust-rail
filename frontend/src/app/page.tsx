import { ShieldCheck, FileSignature, Map } from "lucide-react";
import { getTelemetrySummary } from "@/lib/api";

export default async function LandingPage() {
  const summary = await getTelemetrySummary().catch(() => null);
  const totals = summary?.data?.totals_by_verdict ?? {};
  const totalVerifications = Object.values(totals).reduce((a, b) => a + b, 0);
  const flagged = (totals["LIKELY_FAKE"] ?? 0) + (totals["OFFICIAL_CLAIM_UNVERIFIED"] ?? 0);

  return (
    <div className="mx-auto max-w-3xl px-6 py-24">
      <h1 className="font-display text-4xl font-bold tracking-tight text-ink">TrustRail</h1>
      <p className="mt-4 text-lg text-info">
        Forward it. We&apos;ll tell you if the market actually said it.
      </p>

      <div className="mt-8 flex gap-6 rounded border border-hairline bg-card px-5 py-3 font-mono text-sm text-info">
        <span>
          <span className="text-ink">{totalVerifications}</span> verifications (14d)
        </span>
        <span>
          <span className="text-ink">{flagged}</span> flagged
        </span>
      </div>

      <div className="mt-10 grid gap-4 sm:grid-cols-3">
        <a
          href="/verify"
          className="rounded border-l-4 border-verified bg-card p-5 shadow-sm hover:bg-paper"
        >
          <ShieldCheck className="h-6 w-6 text-verified" />
          <div className="mt-3 font-display font-semibold text-ink">Verify</div>
          <p className="mt-1 text-sm text-info">
            Forward suspicious content and get an honest, reasoned verdict.
          </p>
        </a>
        <a
          href="/issuer"
          className="rounded border-l-4 border-seal bg-card p-5 shadow-sm hover:bg-paper"
        >
          <FileSignature className="h-6 w-6 text-seal" />
          <div className="mt-3 font-display font-semibold text-ink">Issuer</div>
          <p className="mt-1 text-sm text-info">
            Maker-checker publishing into a tamper-evident log.
          </p>
        </a>
        <a
          href="/supervision"
          className="rounded border-l-4 border-info bg-card p-5 shadow-sm hover:bg-paper"
        >
          <Map className="h-6 w-6 text-info" />
          <div className="mt-3 font-display font-semibold text-ink">Supervision</div>
          <p className="mt-1 text-sm text-info">
            Where impersonation attempts are landing, live.
          </p>
        </a>
      </div>
    </div>
  );
}
