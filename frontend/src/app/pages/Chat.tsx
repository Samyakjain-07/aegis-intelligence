import React, { useState } from 'react';
import { useAppContext } from '../components/Layout';
import { FileText, Send, Sparkles, AlertTriangle, ChevronDown, CheckCircle2, UploadCloud } from 'lucide-react';
import { useNavigate } from 'react-router';

const MOCK_CITATIONS = {
  '1': {
    id: '1',
    source: 'NVDA Q4 FY24 Earnings Call',
    type: 'Transcript',
    page: 12,
    date: 'Feb 21, 2024',
    snippet: 'Colette Kress: "Data Center revenue for the fourth quarter was a record $18.4 billion, up 27% sequentially and up 409% year-on-year. **The incredible growth was driven by generative AI and large language model training.**"'
  },
  '2': {
    id: '2',
    source: 'NVDA 10-K FY2024',
    type: '10-K',
    page: 45,
    date: 'Feb 21, 2024',
    snippet: 'Management\'s Discussion and Analysis: "**Supply chain constraints have gradually improved, though certain advanced packaging components remain tight.** We are working closely with our suppliers to secure additional capacity for our Hopper architecture products."'
  }
};

export function Chat() {
  const { setActiveCitation, activeProject } = useAppContext();
  const [query, setQuery] = useState('');
  const navigate = useNavigate();

  const handleCitationClick = (id: string) => {
    setActiveCitation(MOCK_CITATIONS[id as keyof typeof MOCK_CITATIONS]);
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
          
          {/* User Message */}
          <div className="flex gap-4">
            <div className="w-8 h-8 rounded-full bg-blue-600/20 flex items-center justify-center shrink-0 border border-blue-500/30">
              <span className="text-xs text-blue-400 font-bold">JD</span>
            </div>
            <div className="flex-1 pt-1">
              <p className="text-zinc-200 text-sm leading-relaxed">
                How did Nvidia's data center revenue trend over the last 4 quarters, and what did management say about supply constraints?
              </p>
            </div>
          </div>

          {/* AI Response */}
          <div className="flex gap-4">
            <div className="w-8 h-8 rounded-full bg-emerald-600/20 flex items-center justify-center shrink-0 border border-emerald-500/30">
              <Sparkles className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="flex-1 pt-1 space-y-4">
              <div className="text-zinc-300 text-sm leading-relaxed">
                Nvidia's Data Center revenue has shown unprecedented consecutive growth over the last four quarters (FY2024), driven primarily by generative AI and large language model training 
                <button onClick={() => handleCitationClick('1')} className="inline-flex items-center justify-center px-1.5 py-0.5 ml-1 text-[10px] font-bold bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/40 rounded border border-emerald-500/30 transition-colors align-middle">
                  1
                </button>.
              </div>

              {/* Data Table */}
              <div className="border border-zinc-800 rounded-lg overflow-hidden bg-[#111113]">
                <table className="w-full text-sm text-left">
                  <thead className="bg-zinc-800/50 text-xs text-zinc-400 uppercase tracking-wider">
                    <tr>
                      <th className="px-4 py-3 border-b border-zinc-800 font-medium">Quarter</th>
                      <th className="px-4 py-3 border-b border-zinc-800 font-medium text-right">Data Center Rev ($B)</th>
                      <th className="px-4 py-3 border-b border-zinc-800 font-medium text-right">QoQ Growth</th>
                      <th className="px-4 py-3 border-b border-zinc-800 font-medium text-right">YoY Growth</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/50">
                    <tr className="hover:bg-zinc-800/20">
                      <td className="px-4 py-2.5 font-medium text-zinc-300">Q1 FY24</td>
                      <td className="px-4 py-2.5 text-right font-mono">$4.28</td>
                      <td className="px-4 py-2.5 text-right text-emerald-400 font-mono">+18%</td>
                      <td className="px-4 py-2.5 text-right text-emerald-400 font-mono">+14%</td>
                    </tr>
                    <tr className="hover:bg-zinc-800/20">
                      <td className="px-4 py-2.5 font-medium text-zinc-300">Q2 FY24</td>
                      <td className="px-4 py-2.5 text-right font-mono">$10.32</td>
                      <td className="px-4 py-2.5 text-right text-emerald-400 font-mono">+141%</td>
                      <td className="px-4 py-2.5 text-right text-emerald-400 font-mono">+171%</td>
                    </tr>
                    <tr className="hover:bg-zinc-800/20">
                      <td className="px-4 py-2.5 font-medium text-zinc-300">Q3 FY24</td>
                      <td className="px-4 py-2.5 text-right font-mono">$14.51</td>
                      <td className="px-4 py-2.5 text-right text-emerald-400 font-mono">+41%</td>
                      <td className="px-4 py-2.5 text-right text-emerald-400 font-mono">+279%</td>
                    </tr>
                    <tr className="hover:bg-zinc-800/20">
                      <td className="px-4 py-2.5 font-medium text-zinc-300 flex items-center gap-2">
                        Q4 FY24
                        <span title="High Confidence Retrieval" className="text-emerald-500"><CheckCircle2 className="w-3 h-3" /></span>
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono">$18.40</td>
                      <td className="px-4 py-2.5 text-right text-emerald-400 font-mono">+27%</td>
                      <td className="px-4 py-2.5 text-right text-emerald-400 font-mono">+409%</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div className="text-zinc-300 text-sm leading-relaxed mt-4">
                Regarding supply constraints, management noted that while constraints have "gradually improved", certain advanced packaging components (specifically CoWoS) remain tight. They are actively working with suppliers to secure additional capacity for Hopper architecture products 
                <button onClick={() => handleCitationClick('2')} className="inline-flex items-center justify-center px-1.5 py-0.5 ml-1 text-[10px] font-bold bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/40 rounded border border-emerald-500/30 transition-colors align-middle">
                  2
                </button>.
              </div>

              {/* Data Confidence Indicator */}
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-md bg-zinc-800/50 border border-zinc-700/50 text-xs">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                <span className="text-zinc-300">
                  <span className="text-amber-400 font-medium mr-1">Note:</span> 
                  Q1 FY24 YoY growth figures required implicit calculation from historical tables; verify against prior year 10-K if critical.
                </span>
              </div>
            </div>
          </div>
          
        </div>
      </div>

      {/* Input Area */}
      <div className="p-4 bg-[#0a0a0a] border-t border-zinc-800">
        <div className="max-w-4xl mx-auto relative flex items-end bg-[#111113] border border-zinc-700 rounded-xl overflow-hidden focus-within:border-blue-500/50 focus-within:ring-1 focus-within:ring-blue-500/50 transition-all shadow-sm">
          <div className="flex flex-col w-full">
            <textarea 
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={`Ask a question in ${activeProject.name}...`}
              className="w-full max-h-32 min-h-[56px] bg-transparent text-sm text-zinc-100 p-4 resize-none focus:outline-none placeholder:text-zinc-500 font-sans"
              rows={1}
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
              <button className="bg-blue-600 hover:bg-blue-500 text-white rounded-lg p-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
                <Send className="w-4 h-4" />
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
