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

// --- Registry ---

export interface KeyOut {
  id: string;
  label: string;
  role: string;
  public_key_ed25519: string;
  status: string;
  valid_from: string;
  revoked_at: string | null;
  revocation_reason: string | null;
}

export interface EntityOut {
  id: string;
  name: string;
  kind: string;
  sebi_reg_no: string;
  status: string;
  keys: KeyOut[];
}

export interface EntityDetailOut extends EntityOut {
  domains: Array<{ domain: string; kind: string }>;
  sms_headers: Array<{ header: string }>;
}

export async function listEntities(): Promise<ApiResponse<EntityOut[]>> {
  const res = await fetch(`${API_BASE_URL}/api/registry/entities`);
  return res.json();
}

export async function getEntity(id: string): Promise<ApiResponse<EntityDetailOut>> {
  const res = await fetch(`${API_BASE_URL}/api/registry/entities/${id}`);
  return res.json();
}

// --- Transparency log ---

export interface LogRoot {
  tree_size: number;
  root_hash: string;
  timestamp: string | null;
  sth_sig: string | null;
  registry_public_key: string;
}

export interface LogEntryOut {
  seq: number;
  leaf_hash: string;
  entry: Record<string, unknown>;
  tree_size: number;
  root_hash: string;
  created_at: string;
}

export interface InclusionProof {
  leaf_index: number;
  leaf_hash: string;
  audit_path: string[];
  tree_size: number;
  root_hash: string;
}

export async function getLogRoot(): Promise<ApiResponse<LogRoot>> {
  const res = await fetch(`${API_BASE_URL}/api/log/root`);
  return res.json();
}

export async function listLogEntries(limit = 50): Promise<ApiResponse<LogEntryOut[]>> {
  const res = await fetch(`${API_BASE_URL}/api/log/entries?limit=${limit}`);
  return res.json();
}

export async function getInclusionProof(seq: number): Promise<ApiResponse<InclusionProof>> {
  const res = await fetch(`${API_BASE_URL}/api/log/entries/${seq}/proof`);
  return res.json();
}

// --- Issuer (demo persona via X-Demo-Persona header, no real auth) ---

export interface CommOut {
  id: string;
  entity_id: string;
  title: string;
  channel: string;
  impact: string;
  status: string;
  published_at: string | null;
  log_seq: number | null;
  artifact_sha256: string | null;
}

function personaHeaders(personaKeyId: string): HeadersInit {
  return { "X-Demo-Persona": personaKeyId };
}

export async function listCommunications(
  entityId: string
): Promise<ApiResponse<CommOut[]>> {
  const res = await fetch(
    `${API_BASE_URL}/api/issuer/communications?entity_id=${entityId}`
  );
  return res.json();
}

export async function createCommunication(input: {
  entityId: string;
  title: string;
  channel: string;
  impact: string;
  file?: File;
  canonicalText?: string;
  personaKeyId: string;
}): Promise<ApiResponse<CommOut>> {
  const form = new FormData();
  form.append("entity_id", input.entityId);
  form.append("title", input.title);
  form.append("channel", input.channel);
  form.append("impact", input.impact);
  if (input.file) form.append("file", input.file);
  if (input.canonicalText) form.append("canonical_text", input.canonicalText);
  const res = await fetch(`${API_BASE_URL}/api/issuer/communications`, {
    method: "POST",
    body: form,
    headers: personaHeaders(input.personaKeyId),
  });
  return res.json();
}

export async function makerSign(
  commId: string,
  personaKeyId: string
): Promise<ApiResponse<CommOut>> {
  const res = await fetch(
    `${API_BASE_URL}/api/issuer/communications/${commId}/sign`,
    { method: "POST", headers: personaHeaders(personaKeyId) }
  );
  return res.json();
}

export interface CosignResult extends CommOut {
  old_root: string;
  new_root: string;
}

export async function cosignAndPublish(
  commId: string,
  personaKeyId: string
): Promise<ApiResponse<CosignResult>> {
  const res = await fetch(
    `${API_BASE_URL}/api/issuer/communications/${commId}/cosign`,
    { method: "POST", headers: personaHeaders(personaKeyId) }
  );
  return res.json();
}

export async function revokeCommunication(
  commId: string,
  personaKeyId: string
): Promise<ApiResponse<CommOut & { revocation_log_seq: number }>> {
  const res = await fetch(
    `${API_BASE_URL}/api/issuer/communications/${commId}/revoke`,
    { method: "POST", headers: personaHeaders(personaKeyId) }
  );
  return res.json();
}

export async function revokeKey(
  keyId: string,
  reason: string
): Promise<
  ApiResponse<{ key_id: string; status: string; revoked_at: string | null; revocation_log_seq: number }>
> {
  const res = await fetch(`${API_BASE_URL}/api/admin/keys/${keyId}/revoke`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason }),
  });
  return res.json();
}
