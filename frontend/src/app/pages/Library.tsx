import React, { useState } from 'react';
import { Search, Filter, UploadCloud, FileText, CheckCircle2, Clock, MoreHorizontal, Download, FolderOpen } from 'lucide-react';
import { useAppContext } from '../components/Layout';

const MOCK_DOCS = [
  { id: 1, ticker: 'NVDA', name: 'NVDA Q4 FY24 Earnings Call Transcript', type: 'Transcript', date: '2024-02-21', status: 'Indexed' },
  { id: 2, ticker: 'NVDA', name: 'NVDA 10-K FY2024', type: '10-K', date: '2024-02-21', status: 'Indexed' },
  { id: 3, ticker: 'AMD', name: 'AMD Q4 2023 Earnings Call Transcript', type: 'Transcript', date: '2024-01-30', status: 'Indexed' },
  { id: 4, ticker: 'AMD', name: 'AMD 10-K 2023', type: '10-K', date: '2024-01-31', status: 'Indexed' },
  { id: 5, ticker: 'INTC', name: 'INTC Q1 2024 Earnings Deck', type: 'Investor Deck', date: '2024-04-25', status: 'Processing' },
  { id: 6, ticker: 'TSM', name: 'TSM Q1 2024 Management Report', type: 'Other', date: '2024-04-18', status: 'Indexed' },
];

export function Library() {
  const { activeProject } = useAppContext();
  const [searchTerm, setSearchTerm] = useState('');

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
          <button className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-md transition">
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
              <button className="inline-flex items-center justify-center gap-2 px-5 py-2.5 bg-zinc-100 hover:bg-white text-zinc-900 text-sm font-semibold rounded-lg transition-colors">
                <UploadCloud className="w-4 h-4" />
                Upload First Document
              </button>
            </div>
          </div>
        </div>
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
        <button className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-md transition">
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
            {MOCK_DOCS.filter(d => d.name.toLowerCase().includes(searchTerm.toLowerCase()) || d.ticker.toLowerCase().includes(searchTerm.toLowerCase())).map((doc) => (
              <tr key={doc.id} className="hover:bg-zinc-800/30 group transition-colors">
                <td className="py-3 px-6 whitespace-nowrap">
                  <input type="checkbox" className="rounded border-zinc-700 bg-zinc-800" />
                </td>
                <td className="py-3 px-6">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded bg-zinc-800 flex items-center justify-center border border-zinc-700 shrink-0">
                      <FileText className="w-4 h-4 text-blue-400" />
                    </div>
                    <span className="text-sm font-medium text-zinc-200 truncate max-w-[300px]">{doc.name}</span>
                  </div>
                </td>
                <td className="py-3 px-6 whitespace-nowrap">
                  <span className="inline-flex items-center px-2 py-1 rounded text-xs font-semibold bg-zinc-800 text-zinc-300 border border-zinc-700">
                    {doc.ticker}
                  </span>
                </td>
                <td className="py-3 px-6 whitespace-nowrap text-sm text-zinc-400">
                  {doc.type}
                </td>
                <td className="py-3 px-6 whitespace-nowrap text-sm text-zinc-400 font-mono">
                  {doc.date}
                </td>
                <td className="py-3 px-6 whitespace-nowrap">
                  {doc.status === 'Indexed' ? (
                    <span className="inline-flex items-center gap-1.5 text-xs text-emerald-400 bg-emerald-400/10 px-2 py-1 rounded border border-emerald-400/20">
                      <CheckCircle2 className="w-3.5 h-3.5" /> Indexed
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 text-xs text-blue-400 bg-blue-400/10 px-2 py-1 rounded border border-blue-400/20">
                      <Clock className="w-3.5 h-3.5 animate-pulse" /> Processing
                    </span>
                  )}
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
    </div>
  );
}
