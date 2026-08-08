import React, { useCallback, useEffect, useState } from 'react';
import { Search, Filter, UploadCloud, FileText, CheckCircle2, Clock, XCircle, MoreHorizontal, Download, FolderOpen, Loader2, AlertTriangle, X } from 'lucide-react';
import { useAppContext } from '../components/Layout';
import { DocumentRecord, DocumentType, fetchDocuments, uploadDocument } from '../lib/api';

// Mirrors services/api/src/models/db/enums.py's DocumentType -- kept as a
// display-label lookup rather than a switch per render site.
const DOCUMENT_TYPE_LABELS: Record<DocumentType, string> = {
  form_10k: '10-K',
  form_10q: '10-Q',
  earnings_transcript: 'Transcript',
  investor_deck: 'Investor Deck',
};

// Every value POST /documents accepts for `document_type` -- drives the
// upload dialog's <select>. Order matches DOCUMENT_TYPE_LABELS' intent
// (filings, then transcript, then deck).
const DOCUMENT_TYPE_OPTIONS: DocumentType[] = ['form_10k', 'form_10q', 'earnings_transcript', 'investor_deck'];

function StatusBadge({ status }: { status: DocumentRecord['status'] }) {
  if (status === 'completed') {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-emerald-400 bg-emerald-400/10 px-2 py-1 rounded border border-emerald-400/20">
        <CheckCircle2 className="w-3.5 h-3.5" /> Indexed
      </span>
    );
  }
  if (status === 'failed') {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-rose-400 bg-rose-400/10 px-2 py-1 rounded border border-rose-400/20">
        <XCircle className="w-3.5 h-3.5" /> Failed
      </span>
    );
  }
  // 'pending' and 'processing' both read as "still working" to an analyst.
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-blue-400 bg-blue-400/10 px-2 py-1 rounded border border-blue-400/20">
      <Clock className="w-3.5 h-3.5 animate-pulse" /> Processing
    </span>
  );
}

/** Upload form, styled to match Layout.tsx's existing "New Project" modal
 * (a hand-rolled fixed-overlay div, not the shadcn Dialog primitive --
 * the shadcn Dialog's `bg-background`/`text-muted-foreground` tokens
 * aren't wired up to this app's dark palette, see docs/progress.md's
 * Known Issues, so it would render inconsistently next to everything
 * else on this page). Uncontrolled inputs + `FormData(e.target)`, same
 * idiom Layout.tsx's `handleCreateProject` already uses. */
function UploadDialog({
  onClose,
  onUploaded,
}: {
  onClose: () => void;
  onUploaded: (doc: DocumentRecord) => void;
}) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [documentType, setDocumentType] = useState<DocumentType>('form_10k');

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const formData = new FormData(form);

    if (!(formData.get('file') instanceof File) || (formData.get('file') as File).size === 0) {
      setError('Choose a PDF to upload.');
      return;
    }
    // fiscal_quarter is optional in the API -- an empty string from an
    // untouched number input would otherwise fail int-parsing server-side.
    if (formData.get('fiscal_quarter') === '') {
      formData.delete('fiscal_quarter');
    }

    setIsSubmitting(true);
    setError(null);
    try {
      const created = await uploadDocument(formData);
      onUploaded(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-[#0f0f11] border border-zinc-800 rounded-xl w-full max-w-md shadow-2xl flex flex-col overflow-hidden max-h-[90vh]">
        <div className="px-6 py-4 border-b border-zinc-800 flex items-center justify-between shrink-0">
          <h2 className="text-lg font-semibold text-zinc-100">Upload Document</h2>
          <button onClick={onClose} className="text-zinc-500 hover:text-zinc-300">
            <X className="w-5 h-5" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="p-6 flex flex-col gap-4 overflow-y-auto">
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5 uppercase tracking-wide">PDF File</label>
            <input
              name="file"
              type="file"
              accept="application/pdf"
              required
              className="w-full text-sm text-zinc-300 file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border file:border-zinc-700 file:bg-zinc-800 file:text-zinc-200 file:text-xs file:font-medium hover:file:bg-zinc-700 bg-[#111113] border border-zinc-700 rounded-md px-3 py-2 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1.5 uppercase tracking-wide">Ticker</label>
              <input
                name="ticker"
                required
                maxLength={10}
                placeholder="NVDA"
                className="w-full bg-[#111113] border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-blue-500 uppercase"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1.5 uppercase tracking-wide">Document Type</label>
              <select
                name="document_type"
                value={documentType}
                onChange={(e) => setDocumentType(e.target.value as DocumentType)}
                className="w-full bg-[#111113] border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-blue-500"
              >
                {DOCUMENT_TYPE_OPTIONS.map((type) => (
                  <option key={type} value={type}>{DOCUMENT_TYPE_LABELS[type]}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1.5 uppercase tracking-wide">Fiscal Year</label>
              <input
                name="fiscal_year"
                type="number"
                required
                min={1990}
                max={2100}
                placeholder="2024"
                className="w-full bg-[#111113] border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1.5 uppercase tracking-wide">Fiscal Quarter</label>
              <input
                name="fiscal_quarter"
                type="number"
                min={1}
                max={4}
                placeholder={documentType === 'form_10k' ? 'N/A' : 'Optional'}
                className="w-full bg-[#111113] border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5 uppercase tracking-wide">Title (optional)</label>
            <input
              name="title"
              placeholder="Defaults to the file name"
              className="w-full bg-[#111113] border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-blue-500"
            />
          </div>

          <details className="text-xs text-zinc-500">
            <summary className="cursor-pointer hover:text-zinc-300 select-none">Company details (only used for a new ticker)</summary>
            <div className="grid grid-cols-2 gap-3 mt-3">
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1.5 uppercase tracking-wide">Company Name</label>
                <input
                  name="company_name"
                  placeholder="Defaults to ticker"
                  className="w-full bg-[#111113] border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1.5 uppercase tracking-wide">Sector</label>
                <input
                  name="sector"
                  placeholder="Defaults to Unknown"
                  className="w-full bg-[#111113] border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>
          </details>

          {error && (
            <div className="flex items-start gap-2 text-xs text-rose-400 bg-rose-400/10 border border-rose-400/20 rounded-md px-3 py-2">
              <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <div className="mt-2 flex gap-3 justify-end shrink-0">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="px-4 py-2 rounded-md text-sm font-medium text-zinc-400 hover:text-zinc-200 transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium bg-blue-600 hover:bg-blue-500 text-white transition-colors disabled:opacity-60"
            >
              {isSubmitting && <Loader2 className="w-4 h-4 animate-spin" />}
              {isSubmitting ? 'Uploading…' : 'Upload'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function Library() {
  const { activeProject } = useAppContext();
  const [searchTerm, setSearchTerm] = useState('');
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isUploadOpen, setIsUploadOpen] = useState(false);

  const loadDocuments = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);
    try {
      const { documents: rows } = await fetchDocuments();
      setDocuments(rows);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : 'Failed to load documents.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  const handleUploaded = (doc: DocumentRecord) => {
    setDocuments((prev) => [doc, ...prev]);
    setIsUploadOpen(false);
  };

  const filteredDocuments = documents.filter(
    (d) =>
      d.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      d.company.ticker.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const uploadDialog = isUploadOpen && (
    <UploadDialog onClose={() => setIsUploadOpen(false)} onUploaded={handleUploaded} />
  );

  if (activeProject.isEmpty) {
    return (
      <div className="flex-1 flex flex-col h-full bg-[#0a0a0a]">
        {/* Header */}
        <div className="h-16 border-b border-zinc-800 flex items-center px-6 justify-between shrink-0 bg-[#0f0f11]">
          <div>
            <h1 className="text-lg font-semibold text-zinc-100">Document Library</h1>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className={`w-1.5 h-1.5 rounded-full ${activeProject.color}`}></span>
              <p className="text-xs text-zinc-400">{activeProject.name}</p>
            </div>
          </div>
          <button
            onClick={() => setIsUploadOpen(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-md transition"
          >
            <UploadCloud className="w-4 h-4" />
            Upload Documents
          </button>
        </div>

        {/* Empty State */}
        <div className="flex-1 flex items-center justify-center p-6 bg-[#0a0a0a]">
          <div className="max-w-md w-full text-center space-y-4">
            <div className="w-16 h-16 mx-auto rounded-2xl bg-zinc-800/50 border border-zinc-700 flex items-center justify-center mb-6">
              <FolderOpen className="w-8 h-8 text-zinc-500" />
            </div>

            <h2 className="text-xl font-semibold text-zinc-100">No documents indexed</h2>
            <p className="text-sm text-zinc-400 leading-relaxed max-w-sm mx-auto">
              This project's library is currently empty. Upload 10-Ks, earnings transcripts, or investor decks to begin analysis.
            </p>

            <div className="pt-4">
              <button
                onClick={() => setIsUploadOpen(true)}
                className="inline-flex items-center justify-center gap-2 px-5 py-2.5 bg-zinc-100 hover:bg-white text-zinc-900 text-sm font-semibold rounded-lg transition-colors"
              >
                <UploadCloud className="w-4 h-4" />
                Upload First Document
              </button>
            </div>
          </div>
        </div>
        {uploadDialog}
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0a0a0a]">
      {/* Header */}
      <div className="h-16 border-b border-zinc-800 flex items-center px-6 justify-between shrink-0 bg-[#0f0f11]">
        <div>
          <h1 className="text-lg font-semibold text-zinc-100">Document Library</h1>
          <div className="flex items-center gap-1.5 mt-0.5">
            <span className={`w-1.5 h-1.5 rounded-full ${activeProject.color}`}></span>
            <p className="text-xs text-zinc-400">{activeProject.name}</p>
          </div>
        </div>
        <button
          onClick={() => setIsUploadOpen(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-md transition"
        >
          <UploadCloud className="w-4 h-4" />
          Upload Documents
        </button>
      </div>

      {/* Toolbar */}
      <div className="p-4 px-6 border-b border-zinc-800 flex items-center justify-between bg-[#0a0a0a]">
        <div className="flex items-center gap-4 flex-1 max-w-2xl">
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
            <input
              type="text"
              placeholder={`Search in ${activeProject.name}...`}
              className="w-full bg-[#111113] border border-zinc-700 rounded-md py-1.5 pl-9 pr-3 text-sm text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:border-blue-500 transition-colors"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>

          <button className="flex items-center gap-2 px-3 py-1.5 bg-[#111113] border border-zinc-700 hover:border-zinc-600 rounded-md text-sm text-zinc-300 transition">
            <Filter className="w-4 h-4 text-zinc-500" />
            Filters
          </button>
        </div>
      </div>

      {loadError && (
        <div className="mx-6 mt-4 flex items-center justify-between gap-3 text-sm text-rose-400 bg-rose-400/10 border border-rose-400/20 rounded-md px-3 py-2">
          <span className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            {loadError}
          </span>
          <button onClick={loadDocuments} className="text-xs font-medium underline hover:text-rose-300 shrink-0">
            Retry
          </button>
        </div>
      )}

      {/* Data Grid */}
      <div className="flex-1 overflow-auto">
        <table className="w-full text-left border-collapse">
          <thead className="bg-[#0f0f11] sticky top-0 z-10 border-b border-zinc-800">
            <tr>
              <th className="py-3 px-6 text-xs font-medium text-zinc-400 uppercase tracking-wider w-12">
                <input type="checkbox" className="rounded border-zinc-700 bg-zinc-800" />
              </th>
              <th className="py-3 px-6 text-xs font-medium text-zinc-400 uppercase tracking-wider">Document Name</th>
              <th className="py-3 px-6 text-xs font-medium text-zinc-400 uppercase tracking-wider">Ticker</th>
              <th className="py-3 px-6 text-xs font-medium text-zinc-400 uppercase tracking-wider">Type</th>
              <th className="py-3 px-6 text-xs font-medium text-zinc-400 uppercase tracking-wider">Date Published</th>
              <th className="py-3 px-6 text-xs font-medium text-zinc-400 uppercase tracking-wider">Status</th>
              <th className="py-3 px-6 text-xs font-medium text-zinc-400 uppercase tracking-wider text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/50">
            {isLoading && (
              <tr>
                <td colSpan={7} className="py-10 text-center text-sm text-zinc-500">
                  <div className="flex items-center justify-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Loading documents…
                  </div>
                </td>
              </tr>
            )}
            {!isLoading && !loadError && filteredDocuments.length === 0 && (
              <tr>
                <td colSpan={7} className="py-10 text-center text-sm text-zinc-500">
                  {documents.length === 0
                    ? 'No documents yet — upload one to get started.'
                    : 'No documents match your search.'}
                </td>
              </tr>
            )}
            {!isLoading &&
              filteredDocuments.map((doc) => (
                <tr key={doc.document_id} className="hover:bg-zinc-800/30 group transition-colors">
                  <td className="py-3 px-6 whitespace-nowrap">
                    <input type="checkbox" className="rounded border-zinc-700 bg-zinc-800" />
                  </td>
                  <td className="py-3 px-6">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded bg-zinc-800 flex items-center justify-center border border-zinc-700 shrink-0">
                        <FileText className="w-4 h-4 text-blue-400" />
                      </div>
                      <span className="text-sm font-medium text-zinc-200 truncate max-w-[300px]">{doc.title}</span>
                    </div>
                  </td>
                  <td className="py-3 px-6 whitespace-nowrap">
                    <span className="inline-flex items-center px-2 py-1 rounded text-xs font-semibold bg-zinc-800 text-zinc-300 border border-zinc-700">
                      {doc.company.ticker}
                    </span>
                  </td>
                  <td className="py-3 px-6 whitespace-nowrap text-sm text-zinc-400">
                    {DOCUMENT_TYPE_LABELS[doc.document_type]}
                  </td>
                  <td className="py-3 px-6 whitespace-nowrap text-sm text-zinc-400 font-mono">
                    {doc.upload_date}
                  </td>
                  <td className="py-3 px-6 whitespace-nowrap">
                    <StatusBadge status={doc.status} />
                  </td>
                  <td className="py-3 px-6 whitespace-nowrap text-right text-zinc-500">
                    <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button className="p-1 hover:text-zinc-300 transition"><Download className="w-4 h-4" /></button>
                      <button className="p-1 hover:text-zinc-300 transition"><MoreHorizontal className="w-4 h-4" /></button>
                    </div>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
      {uploadDialog}
    </div>
  );
}
