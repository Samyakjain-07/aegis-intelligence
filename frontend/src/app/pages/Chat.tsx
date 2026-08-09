import React, { useState } from 'react';
import { useAppContext } from '../components/Layout';
import { FileText, Send, Sparkles, AlertTriangle, ChevronDown, UploadCloud, Loader2 } from 'lucide-react';
import { useNavigate } from 'react-router';
import { submitQuery, submitFollowupQuery, type CitationRecord, type DocumentType } from '../lib/api';

// Mirrors services/api/src/models/db/enums.py's DocumentType values --
// short display labels for the citation panel/inline badges.
const DOCUMENT_TYPE_LABELS: Record<DocumentType, string> = {
  form_10k: '10-K',
  form_10q: '10-Q',
  earnings_transcript: 'Transcript',
  investor_deck: 'Investor Deck',
};

/** Maps a backend CitationRecord onto Layout.tsx's Citation shape, which
 * the shared "Source Citation" side panel (in Layout, not this file)
 * already knows how to render -- no changes needed there. */
function toPanelCitation(citation: CitationRecord) {
  return {
    id: citation.citation_id,
    source: `${citation.ticker} ${citation.document_title}`,
    type: DOCUMENT_TYPE_LABELS[citation.document_type] ?? citation.document_type,
    page: citation.page_number,
    snippet: citation.snippet,
    date: citation.fiscal_quarter ? `FY${citation.fiscal_year} Q${citation.fiscal_quarter}` : `FY${citation.fiscal_year}`,
  };
}

/** Splits `text` on `[n]` citation markers and renders each as a
 * clickable badge -- `citations[n - 1]` is always what marker `[n]`
 * refers to (the API renumbers markers to guarantee this positional
 * mapping; see api.ts's CitationRecord docstring). A marker with no
 * matching citation (out of range) renders as plain text rather than a
 * dead button. */
function renderAnswerText(
  text: string,
  citations: CitationRecord[],
  onCitationClick: (citation: CitationRecord) => void,
): React.ReactNode[] {
  return text.split(/(\[\d+\])/g).map((part, index) => {
    const match = part.match(/^\[(\d+)\]$/);
    const citation = match ? citations[Number(match[1]) - 1] : undefined;
    if (match && citation) {
      return (
        <button
          key={index}
          onClick={() => onCitationClick(citation)}
          className="inline-flex items-center justify-center px-1.5 py-0.5 ml-1 text-[10px] font-bold bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/40 rounded border border-emerald-500/30 transition-colors align-middle"
        >
          {match[1]}
        </button>
      );
    }
    return <React.Fragment key={index}>{part}</React.Fragment>;
  });
}

type ChatMessage =
  | { role: 'user'; id: string; text: string }
  | {
      role: 'assistant';
      id: string;
      text: string;
      citations: CitationRecord[];
      confidenceScore: number;
      lowConfidence: boolean;
    };

export function Chat() {
  const { setActiveCitation, activeProject } = useAppContext();
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const handleCitationClick = (citation: CitationRecord) => {
    setActiveCitation(toPanelCitation(citation));
  };

  const handleSubmit = async () => {
    const text = query.trim();
    if (!text || isSubmitting) return;

    setError(null);
    setQuery('');
    setMessages((prev) => [...prev, { role: 'user', id: `${Date.now()}-user`, text }]);
    setIsSubmitting(true);
    try {
      // A conversation already in progress is always a follow-up --
      // /query/followup runs history-aware reformulation against this
      // conversation's prior turns before retrieving; the first question
      // has no history yet, so it goes to plain /query instead.
      const result = conversationId
        ? await submitFollowupQuery(text, conversationId)
        : await submitQuery(text);
      setConversationId(result.conversation_id);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          id: result.query_id,
          text: result.answer_text,
          citations: result.citations,
          confidenceScore: result.confidence_score,
          lowConfidence: result.low_confidence,
        },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The query failed. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void handleSubmit();
    }
  };

  if (activeProject.isEmpty) {
    return (
      <div className="flex-1 flex flex-col h-full bg-[#0a0a0a]">
        {/* Header matching standard layout */}
        <div className="h-14 border-b border-zinc-800 flex items-center px-6 shrink-0 justify-between bg-[#0f0f11]">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-zinc-500" />
            <span className="text-sm font-medium text-zinc-400">New Research Query</span>
          </div>
        </div>

        {/* Empty State */}
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="max-w-md w-full text-center space-y-6">
            <div className={`w-16 h-16 mx-auto rounded-2xl ${activeProject.color.replace('bg-', 'bg-')}/10 border border-zinc-700 flex items-center justify-center mb-6`}>
              <Database className="w-8 h-8 text-zinc-400" />
            </div>

            <div>
              <h2 className="text-xl font-semibold text-zinc-100 mb-2">Welcome to {activeProject.name}</h2>
              <p className="text-sm text-zinc-400 leading-relaxed">
                This project workspace is empty. To begin running queries, you can either upload new documents to this project or use the global index.
              </p>
            </div>

            <div className="flex flex-col gap-3 pt-4">
              <button
                onClick={() => navigate('/library')}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors"
              >
                <UploadCloud className="w-4 h-4" />
                Upload Documents
              </button>
              <button
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-[#111113] hover:bg-zinc-800 border border-zinc-700 text-zinc-300 text-sm font-medium rounded-lg transition-colors"
              >
                <SearchIcon className="w-4 h-4" />
                Query Global Index
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0a0a0a]">
      {/* Top Header */}
      <div className="h-14 border-b border-zinc-800 flex items-center px-6 shrink-0 justify-between bg-[#0f0f11]">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-emerald-400" />
          <span className="text-sm font-medium text-zinc-200">New Research Query</span>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5 px-2 py-1 bg-zinc-800/50 border border-zinc-700/50 rounded text-xs text-zinc-400">
            <span className={`w-1.5 h-1.5 rounded-full ${activeProject.color}`}></span>
            {activeProject.name}
          </div>
          <div className="flex items-center gap-2 text-xs text-zinc-500">
            <span>Model: Aegis-Fin-Pro</span>
            <ChevronDown className="w-3 h-3" />
          </div>
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto p-6 scroll-smooth">
        <div className="max-w-4xl mx-auto space-y-8">
          {messages.length === 0 && (
            <div className="text-center py-16">
              <Sparkles className="w-8 h-8 text-zinc-700 mx-auto mb-4" />
              <p className="text-sm text-zinc-500">
                Ask a question about the documents ingested into {activeProject.name}.
              </p>
              <p className="text-xs text-zinc-600 mt-1">
                e.g. "What was data center segment revenue in Q4 2025?"
              </p>
            </div>
          )}

          {messages.map((message) =>
            message.role === 'user' ? (
              <div key={message.id} className="flex gap-4">
                <div className="w-8 h-8 rounded-full bg-blue-600/20 flex items-center justify-center shrink-0 border border-blue-500/30">
                  <span className="text-xs text-blue-400 font-bold">JD</span>
                </div>
                <div className="flex-1 pt-1">
                  <p className="text-zinc-200 text-sm leading-relaxed whitespace-pre-wrap">{message.text}</p>
                </div>
              </div>
            ) : (
              <div key={message.id} className="flex gap-4">
                <div className="w-8 h-8 rounded-full bg-emerald-600/20 flex items-center justify-center shrink-0 border border-emerald-500/30">
                  <Sparkles className="w-4 h-4 text-emerald-400" />
                </div>
                <div className="flex-1 pt-1 space-y-4">
                  <div className="text-zinc-300 text-sm leading-relaxed whitespace-pre-wrap">
                    {renderAnswerText(message.text, message.citations, handleCitationClick)}
                  </div>

                  <div className="flex items-center gap-2 flex-wrap">
                    <div className="inline-flex items-center gap-1.5 px-2 py-1 rounded bg-zinc-800/50 border border-zinc-700/50 text-[10px] text-zinc-400">
                      Confidence {Math.round(message.confidenceScore * 100)}%
                    </div>
                    {message.lowConfidence && (
                      <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-md bg-zinc-800/50 border border-zinc-700/50 text-xs">
                        <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                        <span className="text-zinc-300">
                          <span className="text-amber-400 font-medium mr-1">Low confidence:</span>
                          verify against the cited sources directly before relying on this answer.
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ),
          )}

          {isSubmitting && (
            <div className="flex gap-4">
              <div className="w-8 h-8 rounded-full bg-emerald-600/20 flex items-center justify-center shrink-0 border border-emerald-500/30">
                <Sparkles className="w-4 h-4 text-emerald-400" />
              </div>
              <div className="flex-1 pt-1 flex items-center gap-2 text-sm text-zinc-500">
                <Loader2 className="w-4 h-4 animate-spin" />
                Retrieving and verifying sources...
              </div>
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 px-3 py-2 rounded-md bg-red-500/10 border border-red-500/30 text-xs text-red-300">
              <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
              {error}
            </div>
          )}
        </div>
      </div>

      {/* Input Area */}
      <div className="p-4 bg-[#0a0a0a] border-t border-zinc-800">
        <div className="max-w-4xl mx-auto relative flex items-end bg-[#111113] border border-zinc-700 rounded-xl overflow-hidden focus-within:border-blue-500/50 focus-within:ring-1 focus-within:ring-blue-500/50 transition-all shadow-sm">
          <div className="flex flex-col w-full">
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={`Ask a question in ${activeProject.name}...`}
              className="w-full max-h-32 min-h-[56px] bg-transparent text-sm text-zinc-100 p-4 resize-none focus:outline-none placeholder:text-zinc-500 font-sans"
              rows={1}
              disabled={isSubmitting}
            />
            <div className="flex items-center justify-between px-4 pb-3 pt-1">
              <div className="flex items-center gap-3">
                <button className="text-zinc-500 hover:text-zinc-300 transition-colors flex items-center gap-1.5 text-xs font-medium">
                  <FileText className="w-4 h-4" />
                  Attach Files
                </button>
                <div className="w-px h-3 bg-zinc-700"></div>
                <button className="text-zinc-500 hover:text-zinc-300 transition-colors flex items-center gap-1.5 text-xs font-medium">
                  / Slash Commands
                </button>
              </div>
              <button
                onClick={() => void handleSubmit()}
                disabled={!query.trim() || isSubmitting}
                className="bg-blue-600 hover:bg-blue-500 text-white rounded-lg p-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              </button>
            </div>
          </div>
        </div>
        <div className="max-w-4xl mx-auto mt-2 text-center">
          <span className="text-[10px] text-zinc-600">Aegis Intelligence can make mistakes. Always verify numerical claims using provided citations.</span>
        </div>
      </div>
    </div>
  );
}

// Ensure missing lucide-react imports for Empty State
import { Database, Search as SearchIcon } from 'lucide-react';
