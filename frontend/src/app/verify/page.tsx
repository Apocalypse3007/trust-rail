"use client";

import { useState } from "react";
import { Composer } from "@/components/Composer";
import { VerdictCard } from "@/components/VerdictCard";
import { verifySubmit, type CardPayload, type VerifyInput } from "@/lib/api";
import { useLocaleStore } from "@/lib/store";
import { UI_COPY } from "@/lib/uiCopy";

type Message =
  | { kind: "user"; id: string; label: string }
  | { kind: "card"; id: string; card: CardPayload }
  | { kind: "error"; id: string; message: string };

export default function VerifyPage() {
  const { locale, setLocale } = useLocaleStore();
  const [messages, setMessages] = useState<Message[]>([]);
  const [busy, setBusy] = useState(false);
  const copy = UI_COPY[locale];

  async function handleSubmit(input: Omit<VerifyInput, "locale">) {
    const label = input.file
      ? input.file.name
      : input.text
        ? input.text.slice(0, 160)
        : (input.url ?? "");
    setMessages((m) => [...m, { kind: "user", id: crypto.randomUUID(), label }]);
    setBusy(true);
    try {
      const res = await verifySubmit({ ...input, locale });
      if (res.ok && res.data) {
        const card = res.data;
        setMessages((m) => [...m, { kind: "card", id: crypto.randomUUID(), card }]);
      } else {
        setMessages((m) => [
          ...m,
          { kind: "error", id: crypto.randomUUID(), message: res.error?.message ?? copy.genericError },
        ]);
      }
    } catch {
      setMessages((m) => [
        ...m,
        { kind: "error", id: crypto.randomUUID(), message: copy.networkError },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-2xl flex-col px-4 py-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight text-ink">
            {copy.verifyTitle}
          </h1>
          <p className="mt-1 text-sm text-info">{copy.verifySubtitle}</p>
        </div>
        <button
          type="button"
          onClick={() => setLocale(locale === "en" ? "hi" : "en")}
          className="rounded border border-hairline px-3 py-1.5 text-sm font-medium text-ink hover:bg-paper"
        >
          {copy.toggleLabel}
        </button>
      </div>

      <div className="mt-6 flex-1 space-y-4">
        {messages.length === 0 && (
          <div className="rounded border border-dashed border-hairline p-8 text-center">
            <p className="font-display text-lg font-semibold text-ink">{copy.emptyTitle}</p>
            <p className="mt-2 text-sm text-info">{copy.emptyHint}</p>
          </div>
        )}
        {messages.map((m) => {
          if (m.kind === "user") {
            return (
              <div
                key={m.id}
                className="ml-auto max-w-[80%] rounded bg-ink px-4 py-2 text-sm text-paper"
              >
                {m.label}
              </div>
            );
          }
          if (m.kind === "card") {
            return <VerdictCard key={m.id} card={m.card} />;
          }
          return (
            <div
              key={m.id}
              className="rounded border border-fake bg-card px-4 py-2 text-sm text-fake"
            >
              {m.message}
            </div>
          );
        })}
      </div>

      <div className="sticky bottom-4 mt-6">
        <Composer onSubmit={handleSubmit} busy={busy} copy={copy} />
      </div>
    </div>
  );
}
