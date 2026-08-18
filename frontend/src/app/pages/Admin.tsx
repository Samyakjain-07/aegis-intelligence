import React, { useEffect, useState } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Activity, AlertTriangle, BookOpen, Loader2, Users } from 'lucide-react';
import { AdminAnalytics, FlaggedAnswer, fetchAdminAnalytics, fetchFlaggedAnswers } from '../lib/api';

function formatChartDate(iso: string): string {
  // "2026-08-09" -> "Aug 9" -- compact enough for 7 x-axis ticks without
  // ambiguity across a week boundary (unlike a bare weekday name).
  const [, month, day] = iso.split('-').map(Number);
  return new Date(Date.UTC(2000, month - 1, day)).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  });
}

function formatPercent(rate: number | null): string {
  return rate === null ? '--' : `${(rate * 100).toFixed(1)}%`;
}

export function Admin() {
  const [analytics, setAnalytics] = useState<AdminAnalytics | null>(null);
  const [analyticsError, setAnalyticsError] = useState<string | null>(null);
  const [flagged, setFlagged] = useState<FlaggedAnswer[]>([]);
  const [flaggedTotal, setFlaggedTotal] = useState(0);
  const [flaggedError, setFlaggedError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    Promise.allSettled([fetchAdminAnalytics(), fetchFlaggedAnswers(10)]).then(([analyticsResult, flaggedResult]) => {
      if (cancelled) return;
      if (analyticsResult.status === 'fulfilled') {
        setAnalytics(analyticsResult.value);
      } else {
        setAnalyticsError(
          analyticsResult.reason instanceof Error ? analyticsResult.reason.message : 'Failed to load analytics.'
        );
      }
      if (flaggedResult.status === 'fulfilled') {
        setFlagged(flaggedResult.value.flagged_answers);
        setFlaggedTotal(flaggedResult.value.total);
      } else {
        setFlaggedError(
          flaggedResult.reason instanceof Error ? flaggedResult.reason.message : 'Failed to load flagged answers.'
        );
      }
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const chartData =
    analytics?.query_volume_last_7_days.map((day) => ({
      date: formatChartDate(day.date),
      queries: day.query_count,
      flagged: day.flagged_count,
    })) ?? [];

  const kpis = analytics
    ? [
        { label: 'Total Queries', value: analytics.total_queries.toLocaleString(), icon: Activity, color: 'text-blue-400' },
        { label: 'Low Confidence Rate', value: formatPercent(analytics.low_confidence_rate), icon: AlertTriangle, color: 'text-amber-400' },
        { label: 'Active Analysts', value: analytics.active_analyst_count.toLocaleString(), icon: Users, color: 'text-emerald-400' },
        { label: 'Indexed Documents', value: `${analytics.indexed_document_count} / ${analytics.total_documents}`, icon: BookOpen, color: 'text-purple-400' },
      ]
    : [];

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0a0a0a] overflow-auto">
      {/* Header */}
      <div className="h-16 border-b border-zinc-800 flex items-center px-6 shrink-0 bg-[#0f0f11]">
        <div>
          <h1 className="text-lg font-semibold text-zinc-100">System Analytics & Safety</h1>
          <p className="text-xs text-zinc-400">Internal oversight for RAG retrieval quality and usage.</p>
        </div>
      </div>

      {loading ? (
        <div className="flex-1 flex items-center justify-center text-zinc-500 text-sm gap-2">
          <Loader2 className="w-4 h-4 animate-spin" /> Loading analytics...
        </div>
      ) : (
        <div className="p-6 max-w-6xl w-full mx-auto space-y-6">
          {analyticsError ? (
            <div className="bg-rose-500/10 border border-rose-500/20 rounded-xl p-4 text-sm text-rose-300">
              Failed to load analytics: {analyticsError}
            </div>
          ) : (
            <>
              {/* KPI Cards */}
              <div className="grid grid-cols-4 gap-4">
                {kpis.map((stat, idx) => (
                  <div key={idx} className="bg-[#0f0f11] border border-zinc-800 rounded-xl p-5 flex flex-col gap-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-zinc-400">{stat.label}</span>
                      <stat.icon className={`w-4 h-4 ${stat.color}`} />
                    </div>
                    <span className="text-2xl font-semibold text-zinc-100">{stat.value}</span>
                  </div>
                ))}
              </div>

              {/* Charts Row */}
              <div className="grid grid-cols-3 gap-6">
                <div className="col-span-2 bg-[#0f0f11] border border-zinc-800 rounded-xl p-5">
                  <h2 className="text-sm font-semibold text-zinc-200 mb-6">Query Volume vs Flagged Responses (7d)</h2>
                  <div className="h-72 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={chartData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                        <defs>
                          <linearGradient id="colorQueries" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                          </linearGradient>
                          <linearGradient id="colorFlagged" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#fbbf24" stopOpacity={0.3} />
                            <stop offset="95%" stopColor="#fbbf24" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                        <XAxis dataKey="date" stroke="#52525b" fontSize={12} tickLine={false} axisLine={false} />
                        <YAxis stroke="#52525b" fontSize={12} tickLine={false} axisLine={false} allowDecimals={false} />
                        <Tooltip
                          contentStyle={{ backgroundColor: '#18181b', borderColor: '#27272a', borderRadius: '8px' }}
                          itemStyle={{ color: '#e4e4e7', fontSize: '12px' }}
                        />
                        <Area type="monotone" dataKey="queries" stroke="#3b82f6" strokeWidth={2} fillOpacity={1} fill="url(#colorQueries)" />
                        <Area type="monotone" dataKey="flagged" stroke="#fbbf24" strokeWidth={2} fillOpacity={1} fill="url(#colorFlagged)" />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                <div className="col-span-1 bg-[#0f0f11] border border-zinc-800 rounded-xl p-5 flex flex-col">
                  <h2 className="text-sm font-semibold text-zinc-200 mb-4">Most-Cited Companies</h2>
                  <div className="flex-1 space-y-4">
                    {analytics && analytics.top_cited_tickers.length === 0 ? (
                      <p className="text-xs text-zinc-500">No citations recorded yet.</p>
                    ) : (
                      analytics?.top_cited_tickers.map((item) => (
                        <div key={item.ticker}>
                          <div className="flex justify-between text-xs text-zinc-400 mb-1">
                            <span>{item.ticker}</span>
                            <span>{item.citation_count} citation{item.citation_count === 1 ? '' : 's'}</span>
                          </div>
                          <div className="w-full bg-zinc-800 rounded-full h-1.5">
                            <div className="bg-blue-500 h-1.5 rounded-full" style={{ width: `${item.percent_of_max}%` }}></div>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            </>
          )}

          {/* Flagged Answers Log */}
          <div className="bg-[#0f0f11] border border-zinc-800 rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-zinc-200">Recent Flagged Answers (Needs Human Review)</h2>
              {flaggedTotal > flagged.length && (
                <span className="text-xs font-medium text-zinc-500">Showing {flagged.length} of {flaggedTotal}</span>
              )}
            </div>
            {flaggedError ? (
              <p className="text-sm text-rose-400">Failed to load flagged answers: {flaggedError}</p>
            ) : flagged.length === 0 ? (
              <p className="text-sm text-zinc-500">No flagged answers -- every recent answer met the confidence threshold.</p>
            ) : (
              <table className="w-full text-left">
                <thead className="bg-[#111113]">
                  <tr>
                    <th className="py-2 px-4 text-xs font-medium text-zinc-400 uppercase tracking-wider border-b border-zinc-800">User</th>
                    <th className="py-2 px-4 text-xs font-medium text-zinc-400 uppercase tracking-wider border-b border-zinc-800">Query Snippet</th>
                    <th className="py-2 px-4 text-xs font-medium text-zinc-400 uppercase tracking-wider border-b border-zinc-800">Flag Reason</th>
                    <th className="py-2 px-4 text-xs font-medium text-zinc-400 uppercase tracking-wider text-right border-b border-zinc-800">Confidence</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/50">
                  {flagged.map((answer) => (
                    <tr key={answer.answer_id} className="hover:bg-zinc-800/20">
                      <td className="py-3 px-4 text-sm text-zinc-300">{answer.user_email}</td>
                      <td className="py-3 px-4 text-sm text-zinc-300 truncate max-w-xs">{answer.query_text}</td>
                      <td className="py-3 px-4 text-sm text-amber-400 flex items-center gap-1.5">
                        <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                        {answer.flag_reason}
                      </td>
                      <td className="py-3 px-4 text-sm text-right">
                        <span className="inline-flex items-center px-2 py-1 rounded-md text-[10px] font-semibold uppercase tracking-wider bg-amber-500/10 text-amber-400 border border-amber-500/20">
                          {(answer.confidence_score * 100).toFixed(0)}%
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
