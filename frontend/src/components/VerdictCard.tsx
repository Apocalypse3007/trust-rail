"use client";

import { useState } from "react";
import {
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  Info,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import type { CardPayload } from "@/lib/api";
import { PipelineTrace } from "./PipelineTrace";

const VERDICT_STYLE: Record<
  string,
  { color: string; border: string; Icon: typeof ShieldCheck }
> = {
  VERIFIED: { color: "text-verified", border: "border-verified", Icon: ShieldCheck },
  VERIFIED_NOTICE: { color: "text-notice", border: "border-notice", Icon: ShieldAlert },
  OFFICIAL_CLAIM_UNVERIFIED: { color: "text-notice", border: "border-notice", Icon: AlertTriangle },
  LIKELY_FAKE: { color: "text-fake", border: "border-fake", Icon: AlertTriangle },
  INFORMATIONAL: { color: "text-info", border: "border-info", Icon: Info },
};

export function VerdictCard({ card }: { card: CardPayload }) {
  const [traceOpen, setTraceOpen] = useState(false);
  const style = VERDICT_STYLE[card.verdict] ?? VERDICT_STYLE.INFORMATIONAL;
  const { Icon } = style;
  const traceButton = card.buttons.find((b) => b.kind === "expand_trace");
  const otherButtons = card.buttons.filter((b) => b.kind !== "expand_trace");

  return (
    <div
      className={`rounded border-l-4 bg-card shadow-sm ${style.border} max-w-2xl`}
    >
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          <h3 className="font-display text-lg font-semibold tracking-tight text-ink">
            {card.headline}
          </h3>
          <Icon className={`h-6 w-6 shrink-0 ${style.color}`} aria-hidden />
        </div>

        <p className="mt-2 text-sm leading-relaxed text-ink">{card.body}</p>

        {(card.matched_entity || card.matched_communication) && (
          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 font-mono text-xs text-info">
            {card.matched_entity && <span>{card.matched_entity.sebi_reg_no}</span>}
            {card.matched_communication?.published_at && (
              <span>
                published {card.matched_communication.published_at.slice(0, 10)}
              </span>
            )}
            {card.matched_communication?.log_seq !== null &&
              card.matched_communication?.log_seq !== undefined && (
                <span>log #{card.matched_communication.log_seq}</span>
              )}
          </div>
        )}

        {card.advice.length > 0 && (
          <ul className="mt-3 space-y-1 text-sm text-ink">
            {card.advice.map((line, i) => (
              <li key={i}>• {line}</li>
            ))}
          </ul>
        )}

        <div className="mt-4 flex flex-wrap gap-2">
          {otherButtons.map((b) => (
            <a
              key={b.kind}
              href={b.url}
              className="rounded border border-hairline px-3 py-1.5 text-sm font-medium text-ink hover:bg-paper"
            >
              {b.label}
            </a>
          ))}
          {traceButton && (
            <button
              type="button"
              onClick={() => setTraceOpen((v) => !v)}
              className="flex items-center gap-1 rounded border border-hairline px-3 py-1.5 text-sm font-medium text-ink hover:bg-paper"
            >
              {traceButton.label}
              {traceOpen ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </button>
          )}
        </div>

        {traceOpen && (
          <div className="mt-4 border-t border-hairline pt-4">
            <PipelineTrace trace={card.pipeline_trace} />
          </div>
        )}
      </div>
    </div>
  );
}
