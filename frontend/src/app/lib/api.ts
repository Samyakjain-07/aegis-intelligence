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
