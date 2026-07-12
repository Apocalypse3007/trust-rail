import type { TraceStep } from "@/lib/api";

const STAGE_LABEL: Record<string, string> = {
  hard_binding: "Hard binding",
  registry_match: "Registry match",
  claims_risk: "Claims & risk",
};

// Presentation only — reformats the API's own outcome string (e.g.
// "no_manifest" -> "no manifest"); never invents new wording.
function humanizeOutcome(outcome: string): string {
  return outcome.replace(/_/g, " ");
}

export function PipelineTrace({ trace }: { trace: TraceStep[] }) {
  if (trace.length === 0) return null;
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:gap-0">
      {trace.map((step, i) => (
        <div key={step.stage} className="flex flex-1 items-stretch">
          <div className="flex-1 rounded border border-hairline bg-paper px-3 py-2">
            <div className="font-display text-xs font-semibold uppercase tracking-wide text-info">
              {STAGE_LABEL[step.stage] ?? step.stage}
            </div>
            <div className="mt-1 font-mono text-sm text-ink">
              {humanizeOutcome(step.outcome)}
            </div>
            <div className="mt-0.5 font-mono text-xs text-info">{step.ms}ms</div>
          </div>
          {i < trace.length - 1 && (
            <div
              className="hidden w-4 shrink-0 items-center justify-center text-hairline sm:flex"
              aria-hidden
            >
              →
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
