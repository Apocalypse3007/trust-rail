"use client";

import { useRef, useState } from "react";
import { Paperclip, Send } from "lucide-react";
import type { VerifyInput } from "@/lib/api";

const STATES: Array<{ code: string; name: string }> = [
  { code: "IN-MH", name: "Maharashtra" },
  { code: "IN-KA", name: "Karnataka" },
  { code: "IN-RJ", name: "Rajasthan" },
  { code: "IN-DL", name: "Delhi" },
  { code: "IN-UP", name: "Uttar Pradesh" },
  { code: "IN-GJ", name: "Gujarat" },
  { code: "IN-TN", name: "Tamil Nadu" },
  { code: "IN-TS", name: "Telangana" },
  { code: "IN-WB", name: "West Bengal" },
  { code: "IN-MP", name: "Madhya Pradesh" },
  { code: "IN-HR", name: "Haryana" },
  { code: "IN-PB", name: "Punjab" },
];

type Mode = "file" | "text" | "url";

interface ComposerProps {
  onSubmit: (input: Omit<VerifyInput, "locale">) => void;
  busy: boolean;
  copy: {
    dropHint: string;
    pasteText: string;
    pasteUrl: string;
    claimedSender: string;
    state: string;
    send: string;
  };
}

export function Composer({ onSubmit, busy, copy }: ComposerProps) {
  const [mode, setMode] = useState<Mode>("file");
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [claimedSenderText, setClaimedSenderText] = useState("");
  const [stateCode, setStateCode] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function reset() {
    setFile(null);
    setText("");
    setUrl("");
  }

  function handleSubmit() {
    if (mode === "file" && file) {
      onSubmit({ file, claimedSenderText, stateCode });
    } else if (mode === "text" && text.trim()) {
      onSubmit({ text, claimedSenderText, stateCode });
    } else if (mode === "url" && url.trim()) {
      onSubmit({ url, claimedSenderText, stateCode });
    } else {
      return;
    }
    reset();
  }

  const canSend =
    !busy &&
    ((mode === "file" && !!file) ||
      (mode === "text" && text.trim().length > 0) ||
      (mode === "url" && url.trim().length > 0));

  return (
    <div className="rounded border border-hairline bg-card p-3">
      <div className="flex gap-1 border-b border-hairline pb-2">
        {(["file", "text", "url"] as Mode[]).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => setMode(m)}
            className={`rounded px-3 py-1 text-sm font-medium ${
              mode === m ? "bg-ink text-paper" : "text-info hover:bg-paper"
            }`}
          >
            {m === "file" ? copy.dropHint : m === "text" ? copy.pasteText : copy.pasteUrl}
          </button>
        ))}
      </div>

      <div className="mt-3">
        {mode === "file" && (
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              const f = e.dataTransfer.files?.[0];
              if (f) setFile(f);
            }}
            onClick={() => fileInputRef.current?.click()}
            className={`flex cursor-pointer flex-col items-center justify-center rounded border-2 border-dashed p-6 text-sm text-info ${
              dragOver ? "border-ink bg-paper" : "border-hairline"
            }`}
          >
            <Paperclip className="mb-2 h-5 w-5" />
            {file ? (
              <span className="font-mono text-ink">{file.name}</span>
            ) : (
              <span>{copy.dropHint}</span>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*,video/*,.pdf,.eml"
              className="hidden"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>
        )}

        {mode === "text" && (
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={copy.pasteText}
            rows={3}
            className="w-full resize-none rounded border border-hairline p-2 text-sm text-ink outline-none focus:border-ink"
          />
        )}

        {mode === "url" && (
          <input
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder={copy.pasteUrl}
            className="w-full rounded border border-hairline p-2 text-sm text-ink outline-none focus:border-ink"
          />
        )}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <input
          type="text"
          value={claimedSenderText}
          onChange={(e) => setClaimedSenderText(e.target.value)}
          placeholder={copy.claimedSender}
          className="flex-1 min-w-[10rem] rounded border border-hairline px-2 py-1.5 text-sm text-ink outline-none focus:border-ink"
        />
        <select
          value={stateCode}
          onChange={(e) => setStateCode(e.target.value)}
          className="rounded border border-hairline px-2 py-1.5 text-sm text-ink outline-none focus:border-ink"
        >
          <option value="">{copy.state}</option>
          {STATES.map((s) => (
            <option key={s.code} value={s.code}>
              {s.name}
            </option>
          ))}
        </select>
        <button
          type="button"
          disabled={!canSend}
          onClick={handleSubmit}
          className="ml-auto flex items-center gap-1.5 rounded bg-ink px-4 py-1.5 text-sm font-medium text-paper disabled:opacity-40"
        >
          {copy.send}
          <Send className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
