import React, { useState } from 'react';
import { ArrowRight, ChevronDown, Plus, TrendingUp, TrendingDown } from 'lucide-react';
import { useAppContext } from '../components/Layout';

const MOCK_METRICS = [
  { name: 'Revenue', q1: '$4.28B', q2: '$10.32B', q3: '$14.51B', q4: '$18.40B', yoy: '+409%', yoyUp: true },
  { name: 'Gross Margin (Non-GAAP)', q1: '66.8%', q2: '71.2%', q3: '75.0%', q4: '76.7%', yoy: '+10.6 pts', yoyUp: true },
  { name: 'Operating Expenses', q1: '$1.75B', q2: '$1.84B', q3: '$2.03B', q4: '$2.21B', yoy: '+25%', yoyUp: false },
  { name: 'Operating Income', q1: '$3.05B', q2: '$7.78B', q3: '$11.56B', q4: '$14.75B', yoy: '+983%', yoyUp: true },
  { name: 'Net Income', q1: '$2.71B', q2: '$6.74B', q3: '$10.02B', q4: '$12.84B', yoy: '+769%', yoyUp: true },
  { name: 'EPS (Diluted)', q1: '$1.09', q2: '$2.70', q3: '$4.02', q4: '$5.16', yoy: '+765%', yoyUp: true },
];

export function Compare() {
  const { activeProject } = useAppContext();
  const [ticker, setTicker] = useState('NVDA');

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
        <div className="flex gap-2">
          <button className="flex items-center gap-2 px-3 py-1.5 bg-[#111113] border border-zinc-700 hover:border-zinc-600 text-zinc-300 text-sm font-medium rounded-md transition">
            Export to Excel
          </button>
        </div>
      </div>

      {/* Toolbar */}
      <div className="p-4 px-6 border-b border-zinc-800 flex items-center gap-4 bg-[#0a0a0a]">
        <div className="flex items-center gap-2">
          <span className="text-sm text-zinc-400">Entity:</span>
          <button className="flex items-center gap-2 px-3 py-1.5 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 font-medium">
            <div className="w-5 h-5 rounded-sm bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-[10px]">
              NV
            </div>
            {ticker}
            <ChevronDown className="w-4 h-4 text-zinc-500 ml-2" />
          </button>
        </div>
        <ArrowRight className="w-4 h-4 text-zinc-600" />
        <div className="flex items-center gap-2">
          <span className="text-sm text-zinc-400">Timeframe:</span>
          <button className="flex items-center gap-2 px-3 py-1.5 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 font-medium">
            LTM (Last 4 Quarters)
            <ChevronDown className="w-4 h-4 text-zinc-500 ml-2" />
          </button>
        </div>
        
        <div className="ml-auto">
          <button className="flex items-center gap-1.5 text-blue-400 hover:text-blue-300 text-sm font-medium transition">
            <Plus className="w-4 h-4" /> Add Entity for Peer Comp
          </button>
        </div>
      </div>

      {/* Data Table */}
      <div className="flex-1 p-6 overflow-auto bg-[#0a0a0a]">
        {activeProject.isEmpty ? (
           <div className="flex-1 flex items-center justify-center h-full">
            <p className="text-zinc-500 text-sm">No data available for comparison. Upload documents to this project first.</p>
           </div>
        ) : (
          <div className="border border-zinc-800 rounded-xl overflow-hidden bg-[#0f0f11] shadow-xl">
            <div className="p-4 border-b border-zinc-800 flex items-center justify-between bg-[#111113]">
              <h2 className="text-sm font-semibold text-zinc-200">Income Statement Summary (Data Center Focus)</h2>
              <span className="text-xs text-zinc-500">Values in USD unless otherwise specified</span>
            </div>
            <table className="w-full text-left">
              <thead className="bg-[#111113]">
                <tr>
                  <th className="py-3 px-6 text-xs font-medium text-zinc-400 uppercase tracking-wider border-b border-zinc-800">Metric</th>
                  <th className="py-3 px-6 text-xs font-medium text-zinc-400 uppercase tracking-wider text-right border-b border-zinc-800">Q1 FY24</th>
                  <th className="py-3 px-6 text-xs font-medium text-zinc-400 uppercase tracking-wider text-right border-b border-zinc-800">Q2 FY24</th>
                  <th className="py-3 px-6 text-xs font-medium text-zinc-400 uppercase tracking-wider text-right border-b border-zinc-800">Q3 FY24</th>
                  <th className="py-3 px-6 text-xs font-medium text-zinc-400 uppercase tracking-wider text-right border-b border-zinc-800 border-l border-zinc-800/50 bg-blue-500/5">Q4 FY24</th>
                  <th className="py-3 px-6 text-xs font-medium text-zinc-400 uppercase tracking-wider text-right border-b border-zinc-800">YoY (Q4 vs Q4)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/50">
                {MOCK_METRICS.map((row, idx) => (
                  <tr key={idx} className="hover:bg-zinc-800/30 transition-colors">
                    <td className="py-4 px-6 text-sm font-medium text-zinc-200">{row.name}</td>
                    <td className="py-4 px-6 text-sm font-mono text-zinc-400 text-right">{row.q1}</td>
                    <td className="py-4 px-6 text-sm font-mono text-zinc-400 text-right">{row.q2}</td>
                    <td className="py-4 px-6 text-sm font-mono text-zinc-400 text-right">{row.q3}</td>
                    <td className="py-4 px-6 text-sm font-mono text-zinc-100 font-semibold text-right border-l border-zinc-800/50 bg-blue-500/5">{row.q4}</td>
                    <td className="py-4 px-6 text-right">
                      <span className={`inline-flex items-center gap-1 text-sm font-mono font-medium ${row.yoyUp ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {row.yoyUp ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
                        {row.yoy}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="p-3 bg-zinc-900/50 border-t border-zinc-800 text-xs text-zinc-500 text-center">
              Data sourced from official SEC Filings & Earnings Transcripts. Click on any cell to trace back to source.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
