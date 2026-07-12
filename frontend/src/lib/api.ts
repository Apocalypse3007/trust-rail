// Typed API client (spec §9). Card copy comes ONLY from these responses —
// components must never invent verdict strings themselves.

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export interface ApiError {
  code: string;
  message: string;
}

export interface ApiResponse<T> {
  ok: boolean;
  data: T | null;
  error: ApiError | null;
}

export interface EntityRef {
  id: string;
  name: string;
  sebi_reg_no: string;
}

export interface CommunicationRef {
  id: string;
  title: string;
  published_at: string | null;
  log_seq: number | null;
  channel: string | null;
}

export interface ButtonSpec {
  kind: string;
  label: string;
  url: string;
}

export interface TraceStep {
  stage: string;
  outcome: string;
  ms: number;
}

export interface CardPayload {
  verification_id: string;
  verdict: string;
  headline: string;
  body: string;
  reasons: string[];
  reason_strings: string[];
  advice: string[];
  buttons: ButtonSpec[];
  matched_entity: EntityRef | null;
  matched_communication: CommunicationRef | null;
  claimed_entity_text: string | null;
  pipeline_trace: TraceStep[];
  locale: string;
}

export interface CertificatePayload {
  verdict: string | null;
  entity: EntityRef | null;
  communication: CommunicationRef;
  artifact_sha256: string | null;
  signature_chain: {
    maker_key_id: string | null;
    maker_key_status: string | null;
    checker_key_id: string | null;
    checker_key_status: string | null;
  };
  inclusion_proof: {
    leaf_index: number;
    leaf_hash: string;
    audit_path: string[];
    tree_size: number;
    root_hash: string;
  } | null;
}

export interface TelemetrySummary {
  totals_by_verdict: Record<string, number>;
  series_daily: Array<Record<string, string | number>>;
  by_state: Array<{ state_code: string; count_flagged: number }>;
  top_impersonated: Array<{ entity: string; count: number }>;
  campaigns: Array<{
    campaign: string;
    count: number;
    last_seen: string;
    channels: string[];
  }>;
}

export type Locale = "en" | "hi";

export interface VerifyInput {
  file?: File;
  text?: string;
  url?: string;
  claimedSenderText?: string;
  stateCode?: string;
  locale?: Locale;
  channel?: "sim" | "whatsapp";
}

export async function verifySubmit(
  input: VerifyInput
): Promise<ApiResponse<CardPayload>> {
  const form = new FormData();
  if (input.file) form.append("file", input.file);
  if (input.text !== undefined) form.append("text", input.text);
  if (input.url !== undefined) form.append("url", input.url);
  if (input.claimedSenderText) form.append("claimed_sender_text", input.claimedSenderText);
  if (input.stateCode) form.append("state_code", input.stateCode);
  form.append("locale", input.locale ?? "en");
  form.append("channel", input.channel ?? "sim");

  const res = await fetch(`${API_BASE_URL}/api/verify`, {
    method: "POST",
    body: form,
  });
  return res.json();
}

export async function getVerification(
  id: string,
  locale: Locale = "en"
): Promise<ApiResponse<CardPayload>> {
  const res = await fetch(
    `${API_BASE_URL}/api/verifications/${id}?locale=${locale}`
  );
  return res.json();
}

export async function getCertificate(
  token: string
): Promise<{ status: number; body: ApiResponse<CertificatePayload> }> {
  const res = await fetch(`${API_BASE_URL}/api/c/${token}`);
  return { status: res.status, body: await res.json() };
}

export async function getTelemetrySummary(
  window = "14d"
): Promise<ApiResponse<TelemetrySummary>> {
  const res = await fetch(
    `${API_BASE_URL}/api/telemetry/summary?window=${window}`
  );
  return res.json();
}
