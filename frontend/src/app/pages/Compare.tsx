import React, { useEffect, useMemo, useState } from 'react';
import { ArrowRight, ChevronDown, Loader2, Search, TrendingUp } from 'lucide-react';
import { useAppContext } from '../components/Layout';
import {
  CompareMetricPeriod,
  CompareMetricResponse,
  DocumentRecord,
  compareMetric,
  fetchDocuments,
} from '../lib/api';

// Common income-statement line items to try first -- a shortcut, not an
// exhaustive list; any free-text metric is still searchable via the input
// below. Matching happens server-side (services/api/src/core/
// metric_comparator.py) as a case-insensitive substring against each
// table row's own label, so these are suggestions, not an enum.
const SUGGESTED_METRICS = ['Revenue', 'Net Income', 'Operating Income', 'Gross Profit', 'Total'];

function periodLabel(period: CompareMetricPeriod): string {
  return period.fiscal_quarter ? `FY${period.fiscal_year} Q${period.fiscal_quarter}` : `FY${period.fiscal_year}`;
}

/** Best-effort "headline" figure for a matched row -- the first value cell
 * that isn't the row label itself and looks like it has a digit in it.
 * Display-only (for the compact summary card); the full headers/values
 * pair is always shown underneath regardless of whether this finds
 * anything. */
function primaryValue(period: CompareMetricPeriod): string | null {
  const candidate = period.values.slice(1).find((value) => /\d/.test(value));
  return candidate ?? null;
}

export function Compare() {
  const { activeProject, setActiveCitation } = useAppContext();
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState(true);
  const [documentsError, setDocumentsError] = useState<string | null>(null);

  const [ticker, setTicker] = useState<string>('');
  const [metric, setMetric] = useState<string>('Revenue');
  const [result, setResult] = useState<CompareMetricResponse | null>(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchDocuments()
      .then((data) => {
        if (cancelled) return;
        setDocuments(data.documents);
      })
      .catch((err) => {
        if (cancelled) return;
        setDocumentsError(err instanceof Error ? err.message : 'Failed to load documents.');
      })
      .finally(() => {
        if (!cancelled) setDocumentsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Only tickers with at least one fully-ingested document are worth
  // offering -- a `pending`/`processing`/`failed` filing has no chunks or
  // tables for /compare/metric to search yet.
  const availableCompanies = useMemo(() => {
    const byTicker = new Map<string, { ticker: string; name: string; count: number }>();
    for (const doc of documents) {
      if (doc.status !== 'completed') continue;
      const existing = byTicker.get(doc.company.ticker);
      if (existing) {
        existing.count += 1;
      } else {
        byTicker.set(doc.company.ticker, { ticker: doc.company.ticker, name: doc.company.name, count: 1 });
      }
    }
    return Array.from(byTicker.values()).sort((a, b) => a.ticker.localeCompare(b.ticker));
  }, [documents]);

  useEffect(() => {
    if (!ticker && availableCompanies.length > 0) {
      setTicker(availableCompanies[0].ticker);
    }
  }, [availableCompanies, ticker]);

  async function runCompare(tickerToUse: string, metricToUse: string) {
    if (!tickerToUse.trim() || !metricToUse.trim()) return;
    setSearchLoading(true);
    setSearchError(null);
    setHasSearched(true);
    try {
      const response = await compareMetric(tickerToUse.trim(), metricToUse.trim());
      setResult(response);
    } catch (err) {
      setResult(null);
      setSearchError(err instanceof Error ? err.message : 'Failed to compare metric.');
    } finally {
      setSearchLoading(false);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    void runCompare(ticker, metric);
  }

  function openSource(period: CompareMetricPeriod) {
    setActiveCitation({
      id: `${period.document_id}-${period.page_number}`,
      source: period.document_title,
      type: period.document_type,
      page: period.page_number,
      snippet: `**${period.matched_row_label}**\n${period.headers.join(' | ')}\n${period.values.join(' | ')}`,
      date: periodLabel(period),
    });
  }

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0a0a0a]">
      {/* Header */}
      <div className="h-16 border-b border-zinc-800 flex items-center px-6 justify-between shrink-0 bg-[#0f0f11]">
        <div>
          <h1 className="text-lg font-semibold text-zinc-100">Financial Comparison</h1>
          <div className="flex items-center gap-1.5 mt-0.5">
            <span className={`w-1.5 h-1.5 rounded-full ${activeProject.color}`}></span>
            <p className="text-xs text-zinc-400">{activeProject.name}</p>
          </div>
        </div>
      </div>

      {/* Toolbar */}
      <form onSubmit={handleSubmit} className="p-4 px-6 border-b border-zinc-800 flex items-center gap-4 bg-[#0a0a0a] flex-wrap">
        <div className="flex items-center gap-2">
          <span className="text-sm text-zinc-400">Entity:</span>
          <div className="relative">
            <select
              value={ticker}
              onChange={(e) => setTicker(e.target.value)}
              disabled={documentsLoading || availableCompanies.length === 0}
              className="appearance-none pl-3 pr-8 py-1.5 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 font-medium focus:outline-none focus:border-blue-500 disabled:opacity-50"
            >
              {availableCompanies.length === 0 && <option value="">No ingested companies</option>}
              {availableCompanies.map((c) => (
                <option key={c.ticker} value={c.ticker}>
                  {c.ticker} &middot; {c.name}
                </option>
              ))}
            </select>
            <ChevronDown className="w-4 h-4 text-zinc-500 absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>
        </div>
        <ArrowRight className="w-4 h-4 text-zinc-600" />
        <div className="flex items-center gap-2 flex-1 min-w-[240px]">
          <span className="text-sm text-zinc-400 shrink-0">Metric:</span>
          <div className="relative flex-1 max-w-xs">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-500" />
            <input
              value={metric}
              onChange={(e) => setMetric(e.target.value)}
              placeholder="e.g. Revenue, Net Income..."
              className="w-full bg-zinc-800 border border-zinc-700 rounded-md py-1.5 pl-8 pr-2 text-sm text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:border-blue-500"
            />
          </div>
          <div className="hidden lg:flex items-center gap-1.5">
            {SUGGESTED_METRICS.map((m) => (
              <button
                type="button"
                key={m}
                onClick={() => setMetric(m)}
                className={`px-2 py-1 rounded text-xs font-medium transition ${
                  metric === m
                    ? 'bg-blue-600/20 text-blue-300 border border-blue-500/30'
                    : 'bg-[#111113] text-zinc-400 border border-zinc-700 hover:border-zinc-600'
                }`}
              >
                {m}
              </button>
            ))}
          </div>
        </div>
        <button
          type="submit"
          disabled={searchLoading || !ticker || !metric.trim()}
          className="flex items-center gap-2 px-4 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:hover:bg-blue-600 text-white text-sm font-medium rounded-md transition"
        >
          {searchLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
          Compare
        </button>
      </form>

      {/* Results */}
      <div className="flex-1 p-6 overflow-auto bg-[#0a0a0a]">
        {activeProject.isEmpty ? (
          <div className="flex-1 flex items-center justify-center h-full">
            <p className="text-zinc-500 text-sm">No data available for comparison. Upload documents to this project first.</p>
          </div>
        ) : documentsLoading ? (
          <div className="flex items-center justify-center h-full text-zinc-500 text-sm gap-2">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading ingested documents...
          </div>
        ) : documentsError ? (
          <div className="flex items-center justify-center h-full text-rose-400 text-sm">{documentsError}</div>
        ) : availableCompanies.length === 0 ? (
          <div className="flex items-center justify-center h-full text-zinc-500 text-sm">
            No fully-ingested filings yet. Upload and wait for ingestion to complete on the Library page, then compare a metric here.
          </div>
        ) : !hasSearched ? (
          <div className="flex items-center justify-center h-full text-zinc-500 text-sm">
            Pick a company and a metric, then hit Compare.
          </div>
        ) : searchLoading ? (
          <div className="flex items-center justify-center h-full text-zinc-500 text-sm gap-2">
            <Loader2 className="w-4 h-4 animate-spin" /> Searching ingested filings...
          </div>
        ) : searchError ? (
          <div className="flex items-center justify-center h-full text-rose-400 text-sm">{searchError}</div>
        ) : result && result.periods.length === 0 ? (
          <div className="flex items-center justify-center h-full text-zinc-500 text-sm text-center max-w-md mx-auto">
            No table row matched &ldquo;{result.metric_query}&rdquo; in any ingested filing for {result.ticker}. Try a
            different line-item label -- matching is a substring search against each table's own row labels.
          </div>
        ) : result ? (
          <div className="border border-zinc-800 rounded-xl overflow-hidden bg-[#0f0f11] shadow-xl">
            <div className="p-4 border-b border-zinc-800 flex items-center justify-between bg-[#111113]">
              <h2 className="text-sm font-semibold text-zinc-200">
                {result.company_name} ({result.ticker}) &middot; &ldquo;{result.metric_query}&rdquo; across {result.periods.length}{' '}
                ingested filing{result.periods.length === 1 ? '' : 's'}
              </h2>
              <span className="text-xs text-zinc-500">Values as reported in each filing's own table</span>
            </div>
            <table className="w-full text-left">
              <thead className="bg-[#111113]">
                <tr>
                  <th className="py-3 px-6 text-xs font-medium text-zinc-400 uppercase tracking-wider border-b border-zinc-800">Period</th>
                  <th className="py-3 px-6 text-xs font-medium text-zinc-400 uppercase tracking-wider border-b border-zinc-800">Document</th>
                  <th className="py-3 px-6 text-xs font-medium text-zinc-400 uppercase tracking-wider border-b border-zinc-800">Matched Row</th>
                  <th className="py-3 px-6 text-xs font-medium text-zinc-400 uppercase tracking-wider border-b border-zinc-800">Reported Values</th>
                  <th className="py-3 px-6 text-xs font-medium text-zinc-400 uppercase tracking-wider text-right border-b border-zinc-800">Source</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/50">
                {result.periods.map((period) => {
                  const headline = primaryValue(period);
                  return (
                    <tr key={period.document_id} className="hover:bg-zinc-800/30 transition-colors align-top">
                      <td className="py-4 px-6 text-sm font-medium text-zinc-200 whitespace-nowrap">
                        {periodLabel(period)}
                        {headline && (
                          <div className="text-xs font-mono text-emerald-400 flex items-center gap-1 mt-1">
                            <TrendingUp className="w-3 h-3" /> {headline}
                          </div>
                        )}
                      </td>
                      <td className="py-4 px-6 text-sm text-zinc-400 max-w-[220px] truncate">{period.document_title}</td>
                      <td className="py-4 px-6 text-sm font-mono text-zinc-200">{period.matched_row_label}</td>
                      <td className="py-4 px-6 text-xs font-mono text-zinc-400">
                        <div className="flex flex-wrap gap-x-3 gap-y-1">
                          {period.headers.map((header, idx) => (
                            <span key={idx} className="whitespace-nowrap">
                              <span className="text-zinc-500">{header || `col ${idx}`}:</span>{' '}
                              <span className="text-zinc-200">{period.values[idx] ?? '--'}</span>
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="py-4 px-6 text-right">
                        <button
                          onClick={() => openSource(period)}
                          className="text-xs font-medium text-blue-400 hover:text-blue-300 whitespace-nowrap"
                        >
                          {period.exact_location}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <div className="p-3 bg-zinc-900/50 border-t border-zinc-800 text-xs text-zinc-500 text-center">
              Data sourced from official SEC Filings. Click a source location to trace back to the exact page/table.
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
