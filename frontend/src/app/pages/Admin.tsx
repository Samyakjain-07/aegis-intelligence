import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Activity, AlertTriangle, Users, BookOpen } from 'lucide-react';

const MOCK_CHART_DATA = [
  { date: 'Mon', queries: 140, flagged: 12 },
  { date: 'Tue', queries: 210, flagged: 8 },
  { date: 'Wed', queries: 350, flagged: 22 },
  { date: 'Thu', queries: 280, flagged: 15 },
  { date: 'Fri', queries: 420, flagged: 30 },
  { date: 'Sat', queries: 90, flagged: 5 },
  { date: 'Sun', queries: 110, flagged: 2 },
];

const FLAGGED_QUERIES = [
  { id: 1, user: 'jdoe@fund.com', query: 'What was TSMC\'s exact 3nm yield rate in Q1?', reason: 'Low Confidence (Implicit Extraction)', status: 'Pending Review' },
  { id: 2, user: 'mchen@fund.com', query: 'Compare Azure and AWS operating margins strictly for IaaS.', reason: 'Conflicting Sources', status: 'Pending Review' },
  { id: 3, user: 'sroberts@fpanda.com', query: 'Break down Apple\'s wearables gross margin vs services margin.', reason: 'Data Not Explicitly Disclosed', status: 'Reviewed' },
];

export function Admin() {
  return (
    <div className="flex-1 flex flex-col h-full bg-[#0a0a0a] overflow-auto">
      {/* Header */}
      <div className="h-16 border-b border-zinc-800 flex items-center px-6 shrink-0 bg-[#0f0f11]">
        <div>
          <h1 className="text-lg font-semibold text-zinc-100">System Analytics & Safety</h1>
          <p className="text-xs text-zinc-400">Internal oversight for RAG retrieval quality and usage.</p>
        </div>
      </div>

      <div className="p-6 max-w-6xl w-full mx-auto space-y-6">
        {/* KPI Cards */}
        <div className="grid grid-cols-4 gap-4">
          {[
            { label: 'Total Queries (7d)', value: '1,600', icon: Activity, color: 'text-blue-400' },
            { label: 'Low Confidence Rate', value: '5.8%', icon: AlertTriangle, color: 'text-amber-400' },
            { label: 'Active Analysts', value: '42', icon: Users, color: 'text-emerald-400' },
            { label: 'Indexed Documents', value: '2,845', icon: BookOpen, color: 'text-purple-400' },
          ].map((stat, idx) => (
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
            <h2 className="text-sm font-semibold text-zinc-200 mb-6">Query Volume vs Flagged Responses</h2>
            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={MOCK_CHART_DATA} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorQueries" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                    </linearGradient>
                    <linearGradient id="colorFlagged" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#fbbf24" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#fbbf24" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                  <XAxis dataKey="date" stroke="#52525b" fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis stroke="#52525b" fontSize={12} tickLine={false} axisLine={false} />
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
            <h2 className="text-sm font-semibold text-zinc-200 mb-4">Top Query Topics</h2>
            <div className="flex-1 space-y-4">
              {[
                { topic: 'NVDA Data Center Growth', percent: 85 },
                { topic: 'MSFT Cloud Capex', percent: 72 },
                { topic: 'AMD AI Revenue Guide', percent: 64 },
                { topic: 'TSM CoWoS Capacity', percent: 45 },
                { topic: 'AAPL Service Margins', percent: 30 },
              ].map((item, idx) => (
                <div key={idx}>
                  <div className="flex justify-between text-xs text-zinc-400 mb-1">
                    <span>{item.topic}</span>
                    <span>{item.percent}%</span>
                  </div>
                  <div className="w-full bg-zinc-800 rounded-full h-1.5">
                    <div className="bg-blue-500 h-1.5 rounded-full" style={{ width: `${item.percent}%` }}></div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Flagged Answers Log */}
        <div className="bg-[#0f0f11] border border-zinc-800 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-zinc-200">Recent Flagged Answers (Needs Human Review)</h2>
            <button className="text-xs font-medium text-blue-400 hover:text-blue-300">View All Queue</button>
          </div>
          <table className="w-full text-left">
            <thead className="bg-[#111113]">
              <tr>
                <th className="py-2 px-4 text-xs font-medium text-zinc-400 uppercase tracking-wider border-b border-zinc-800">User</th>
                <th className="py-2 px-4 text-xs font-medium text-zinc-400 uppercase tracking-wider border-b border-zinc-800">Query Snippet</th>
                <th className="py-2 px-4 text-xs font-medium text-zinc-400 uppercase tracking-wider border-b border-zinc-800">Flag Reason</th>
                <th className="py-2 px-4 text-xs font-medium text-zinc-400 uppercase tracking-wider text-right border-b border-zinc-800">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/50">
              {FLAGGED_QUERIES.map((flag) => (
                <tr key={flag.id} className="hover:bg-zinc-800/20">
                  <td className="py-3 px-4 text-sm text-zinc-300">{flag.user}</td>
                  <td className="py-3 px-4 text-sm text-zinc-300 truncate max-w-xs">{flag.query}</td>
                  <td className="py-3 px-4 text-sm text-amber-400 flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5" />
                    {flag.reason}
                  </td>
                  <td className="py-3 px-4 text-sm text-right">
                    <span className={`inline-flex items-center px-2 py-1 rounded-md text-[10px] font-semibold uppercase tracking-wider ${
                      flag.status === 'Reviewed' 
                        ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' 
                        : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                    }`}>
                      {flag.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
