// Mirrors backend/app/trust/canonical.py: sorted-key JSON, no whitespace,
// UTF-8 bytes — must byte-match Python's
// json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).
// Only used for re-serializing values the server already gave us (log
// entries, STH payloads) — never for producing new signed data client-side.

type Json = string | number | boolean | null | Json[] | { [key: string]: Json };

function sortedStringify(value: Json): string {
  if (value === null || typeof value !== "object") {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return "[" + value.map(sortedStringify).join(",") + "]";
  }
  const keys = Object.keys(value).sort();
  const parts = keys.map((k) => JSON.stringify(k) + ":" + sortedStringify(value[k]));
  return "{" + parts.join(",") + "}";
}

export function canonicalJsonBytes(obj: Json): Uint8Array {
  return new TextEncoder().encode(sortedStringify(obj));
}
