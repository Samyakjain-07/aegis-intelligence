/// <reference types="vite/client" />
// Minimal fetch client for services/api (PROJECT_HANDBOOK.md Phase 4).
//
// A tiny shared module rather than inline fetch calls in every page --
// Phase 6/7 wire Chat.tsx/Compare.tsx/Admin.tsx to the same API next, and
// they'll want the same base-URL/error-parsing logic Library.tsx needs
// first. Kept deliberately small (types + two calls) rather than a full
// generated client -- no codegen tool is in the agreed stack
// (CLAUDE.md §3), and the API surface is still small enough that hand
// -written types are cheap.

export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8001/api/v1';

// Mirrors services/api/src/models/db/enums.py -- kept as plain string
// unions (not a TS enum) since these are only ever compared against JSON
// string values coming back from the API, never constructed locally.
export type DocumentType = 'form_10k' | 'form_10q' | 'earnings_transcript' | 'investor_deck';
export type DocumentStatus = 'pending' | 'processing' | 'completed' | 'failed';

// Mirrors services/api/src/models/schemas/document.py's CompanyResponse.
export interface CompanyRecord {
  company_id: string;
  ticker: string;
  name: string;
  sector: string;
}

// Mirrors services/api/src/models/schemas/document.py's DocumentResponse.
export interface DocumentRecord {
  document_id: string;
  company_id: string;
  company: CompanyRecord;
  document_type: DocumentType;
  fiscal_quarter: number | null;
  fiscal_year: number;
  upload_date: string;
  source_url: string;
  title: string;
  status: DocumentStatus;
}

export interface DocumentListResponse {
  documents: DocumentRecord[];
  total: number;
}

/** Pulls a human-readable message out of FastAPI's error envelope --
 * either `{"detail": "..."}` (HTTPException) or
 * `{"detail": [{"msg": "...", ...}, ...]}` (a 422 validation error) --
 * falling back to the HTTP status if the body isn't JSON at all. */
async function parseErrorDetail(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === 'string') return body.detail;
    if (Array.isArray(body?.detail)) {
      return body.detail
        .map((issue: { msg?: string; loc?: unknown[] }) => {
          const field = Array.isArray(issue.loc) ? issue.loc[issue.loc.length - 1] : undefined;
          return field ? `${field}: ${issue.msg}` : issue.msg;
        })
        .join('; ');
    }
  } catch {
    // Response body wasn't JSON -- fall through to the generic message.
  }
  return `Request failed with status ${response.status}`;
}

export async function fetchDocuments(): Promise<DocumentListResponse> {
  const response = await fetch(`${API_BASE_URL}/documents`);
  if (!response.ok) {
    throw new Error(await parseErrorDetail(response));
  }
  return response.json();
}

/** `formData` must contain a `file` part plus the `POST /documents` form
 * fields (`ticker`, `document_type`, `fiscal_year`, and optionally
 * `fiscal_quarter`/`company_name`/`sector`/`title`) -- see
 * services/api/src/api/v1/routes/documents.py. No `Content-Type` header is
 * set here on purpose: the browser fills in the multipart boundary itself
 * from the FormData, and overriding it manually is a classic way to send
 * a boundary-less/broken multipart body. */
export async function uploadDocument(formData: FormData): Promise<DocumentRecord> {
  const response = await fetch(`${API_BASE_URL}/documents`, {
    method: 'POST',
    body: formData,
  });
  if (!response.ok) {
    throw new Error(await parseErrorDetail(response));
  }
  return response.json();
}

// --- Query pipeline (PROJECT_HANDBOOK.md Phase 6) ---

/** Mirrors services/api/src/models/schemas/citation.py's CitationResponse.
 * `[n]` markers inside a QueryRecord's `answer_text` are 1-indexed and
 * positional into this array -- `citations[n - 1]` is always the citation
 * marker `[n]` refers to (services/api/src/api/v1/routes/query.py
 * renumbers the model's raw citation markers to guarantee this, so the
 * frontend never has to search for a matching id). */
export interface CitationRecord {
  citation_id: string;
  answer_id: string;
  chunk_id: string;
  exact_location: string;
  snippet: string;
  document_title: string;
  document_type: DocumentType;
  ticker: string;
  page_number: number;
  fiscal_year: number;
  fiscal_quarter: number | null;
}

/** Mirrors services/api/src/models/schemas/query.py's QueryResponse --
 * the shape both `POST /query` and `POST /query/followup` return. */
export interface QueryRecord {
  query_id: string;
  conversation_id: string;
  query_text: string;
  reformulated_query_text: string | null;
  answer_text: string;
  confidence_score: number;
  low_confidence: boolean;
  citations: CitationRecord[];
  created_at: string;
}

/** A fresh question. Omit `conversationId` to start a new conversation;
 * pass one to attach the question to an existing thread without
 * follow-up reformulation -- see `submitFollowupQuery` for that. */
export async function submitQuery(queryText: string, conversationId?: string): Promise<QueryRecord> {
  const response = await fetch(`${API_BASE_URL}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query_text: queryText, conversation_id: conversationId ?? null }),
  });
  if (!response.ok) {
    throw new Error(await parseErrorDetail(response));
  }
  return response.json();
}

/** A follow-up inside an existing conversation -- the backend rewrites it
 * into a self-contained question (history-aware reformulation) before
 * retrieving, using that conversation's prior turns. */
export async function submitFollowupQuery(queryText: string, conversationId: string): Promise<QueryRecord> {
  const response = await fetch(`${API_BASE_URL}/query/followup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query_text: queryText, conversation_id: conversationId }),
  });
  if (!response.ok) {
    throw new Error(await parseErrorDetail(response));
  }
  return response.json();
}

// --- Compare page (PROJECT_HANDBOOK.md Phase 7) ---

/** Mirrors services/api/src/models/schemas/compare.py's
 * CompareMetricPeriodResponse -- one ingested filing's matched row for the
 * requested metric. `headers`/`values` are parallel arrays straight from
 * that filing's own table (never a flattened string) -- see that schema's
 * docstring for why different periods can legitimately have different
 * column structure. */
export interface CompareMetricPeriod {
  document_id: string;
  document_title: string;
  document_type: DocumentType;
  fiscal_year: number;
  fiscal_quarter: number | null;
  page_number: number;
  matched_row_label: string;
  headers: string[];
  values: string[];
  exact_location: string;
}

/** Mirrors services/api/src/models/schemas/compare.py's
 * CompareMetricResponse. `periods` is ordered oldest-first (fiscal_year,
 * then fiscal_quarter) and contains at most one entry per ingested
 * document -- documents where `metric` matched no row are simply absent,
 * not a null placeholder. */
export interface CompareMetricResponse {
  ticker: string;
  company_name: string;
  metric_query: string;
  periods: CompareMetricPeriod[];
}

/** `GET /compare/metric` -- throws (via parseErrorDetail) on a 404, which
 * means no ingested company matches `ticker` at all. A 200 with an empty
 * `periods` array is a different, valid outcome: the company exists but
 * `metric` matched no table row in any of its filings. */
export async function compareMetric(ticker: string, metric: string): Promise<CompareMetricResponse> {
  const params = new URLSearchParams({ ticker, metric });
  const response = await fetch(`${API_BASE_URL}/compare/metric?${params.toString()}`);
  if (!response.ok) {
    throw new Error(await parseErrorDetail(response));
  }
  return response.json();
}

// --- Admin dashboard (PROJECT_HANDBOOK.md Phase 7) ---

/** Mirrors services/api/src/models/schemas/admin.py's
 * QueryVolumeDayResponse -- one point on the query-volume-vs-flagged
 * chart. */
export interface QueryVolumeDay {
  date: string;
  query_count: number;
  flagged_count: number;
}

/** Mirrors services/api/src/models/schemas/admin.py's
 * TickerCitationCountResponse. */
export interface TickerCitationCount {
  ticker: string;
  citation_count: number;
  percent_of_max: number;
}

/** Mirrors services/api/src/models/schemas/admin.py's
 * AdminAnalyticsResponse. */
export interface AdminAnalytics {
  total_documents: number;
  indexed_document_count: number;
  total_conversations: number;
  total_queries: number;
  average_confidence_score: number | null;
  flagged_answer_count: number;
  low_confidence_rate: number | null;
  active_analyst_count: number;
  query_volume_last_7_days: QueryVolumeDay[];
  top_cited_tickers: TickerCitationCount[];
}

export async function fetchAdminAnalytics(): Promise<AdminAnalytics> {
  const response = await fetch(`${API_BASE_URL}/admin/analytics`);
  if (!response.ok) {
    throw new Error(await parseErrorDetail(response));
  }
  return response.json();
}

/** Mirrors services/api/src/models/schemas/admin.py's
 * FlaggedAnswerResponse. */
export interface FlaggedAnswer {
  answer_id: string;
  query_id: string;
  conversation_id: string;
  user_email: string;
  query_text: string;
  answer_text: string;
  confidence_score: number;
  flag_reason: string;
  generated_at: string;
}

export interface FlaggedAnswersListResponse {
  flagged_answers: FlaggedAnswer[];
  total: number;
}

export async function fetchFlaggedAnswers(limit = 10): Promise<FlaggedAnswersListResponse> {
  const response = await fetch(`${API_BASE_URL}/admin/flagged-answers?limit=${limit}`);
  if (!response.ok) {
    throw new Error(await parseErrorDetail(response));
  }
  return response.json();
}
