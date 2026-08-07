import React, { createContext, useState, useContext } from 'react';
import { NavLink, Outlet } from 'react-router';
import { 
  MessageSquare, Library, ArrowLeftRight, Activity, Database, Settings,
  ChevronDown, Search, FolderPlus, X, Tag, Globe, CheckCircle2, Clock
} from 'lucide-react';

// --- Types & Mock Data ---

export type Citation = {
  id: string;
  source: string;
  type: string;
  page: number;
  snippet: string;
  date: string;
};

export type Project = {
  id: string;
  name: string;
  tickers: string[];
  color: string;
  lastActive: string;
  isEmpty: boolean;
};

const MOCK_PROJECTS: Project[] = [
  { id: 'p1', name: 'Nvidia Q4 Earnings Analysis', tickers: ['NVDA'], color: 'bg-emerald-500', lastActive: '10m ago', isEmpty: false },
  { id: 'p2', name: 'Semiconductor Sector Comparison', tickers: ['NVDA', 'AMD', 'INTC', 'TSM'], color: 'bg-blue-500', lastActive: '2h ago', isEmpty: false },
  { id: 'p3', name: 'New Client Deliverable', tickers: [], color: 'bg-purple-500', lastActive: 'Just now', isEmpty: true },
];

const COLORS = ['bg-emerald-500', 'bg-blue-500', 'bg-purple-500', 'bg-rose-500', 'bg-amber-500', 'bg-cyan-500'];

// --- Contexts ---

interface AppContextType {
  activeCitation: Citation | null;
  setActiveCitation: (c: Citation | null) => void;
  activeProject: Project;
  setActiveProject: (p: Project) => void;
}

export const AppContext = createContext<AppContextType>({
  activeCitation: null,
  setActiveCitation: () => {},
  activeProject: MOCK_PROJECTS[0],
  setActiveProject: () => {},
});

export const useAppContext = () => useContext(AppContext);

// --- Layout Component ---

export function Layout() {
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);
  const [activeProject, setActiveProject] = useState<Project>(MOCK_PROJECTS[0]);
  const [projects, setProjects] = useState<Project[]>(MOCK_PROJECTS);
  
  // UI States
  const [isProjectListOpen, setIsProjectListOpen] = useState(false);
  const [isNewProjectModalOpen, setIsNewProjectModalOpen] = useState(false);
  const [projectSearch, setProjectSearch] = useState('');

  // Nav definitions
  const projectNavItems = [
    { name: 'Research', path: '/', icon: MessageSquare },
    { name: 'Compare', path: '/compare', icon: ArrowLeftRight },
    { name: 'Library', path: '/library', icon: Library },
  ];

  const globalNavItems = [
    { name: 'Admin', path: '/admin', icon: Activity },
  ];

  const filteredProjects = projects.filter(p => p.name.toLowerCase().includes(projectSearch.toLowerCase()));

  const handleCreateProject = (e: React.FormEvent) => {
    e.preventDefault();
    const formData = new FormData(e.target as HTMLFormElement);
    const newProj: Project = {
      id: `p${Date.now()}`,
      name: formData.get('name') as string || 'Untitled Project',
      tickers: (formData.get('tickers') as string).split(',').map(t => t.trim()).filter(Boolean),
      color: formData.get('color') as string || COLORS[0],
      lastActive: 'Just now',
      isEmpty: true
    };
    setProjects([newProj, ...projects]);
    setActiveProject(newProj);
    setIsNewProjectModalOpen(false);
    setIsProjectListOpen(false);
  };

  return (
    <AppContext.Provider value={{ activeCitation, setActiveCitation, activeProject, setActiveProject }}>
      <div className="flex h-screen w-full bg-[#0a0a0a] text-gray-200 font-sans overflow-hidden">
        
        {/* Left Sidebar */}
        <div className="w-64 border-r border-zinc-800 bg-[#0f0f11] flex flex-col relative z-40">
          
          {/* Project Switcher Header */}
          <div className="p-4 border-b border-zinc-800 relative">
            <div className="flex items-center gap-2 text-zinc-400 mb-2">
              <Database className="w-4 h-4 text-zinc-500" />
              <span className="text-xs font-semibold tracking-wide uppercase">Aegis Intelligence</span>
            </div>
            
            <button 
              onClick={() => setIsProjectListOpen(!isProjectListOpen)}
              className="w-full flex items-center justify-between p-2 -mx-2 rounded-md hover:bg-zinc-800/50 transition-colors group"
            >
              <div className="flex items-center gap-3 overflow-hidden">
                <div className={`w-3 h-3 rounded-full ${activeProject.color} shadow-[0_0_8px_rgba(0,0,0,0.5)]`} />
                <span className="font-medium text-sm text-zinc-100 truncate">{activeProject.name}</span>
              </div>
              <ChevronDown className="w-4 h-4 text-zinc-500 group-hover:text-zinc-300" />
            </button>

            {/* Project List Dropdown Panel */}
            {isProjectListOpen && (
              <div className="absolute top-[calc(100%+4px)] left-2 w-72 bg-[#111113] border border-zinc-700 rounded-lg shadow-2xl overflow-hidden flex flex-col z-50">
                <div className="p-2 border-b border-zinc-800">
                  <button 
                    onClick={() => { setIsProjectListOpen(false); setIsNewProjectModalOpen(true); }}
                    className="w-full flex items-center gap-2 px-3 py-2 bg-blue-600/10 hover:bg-blue-600/20 text-blue-400 text-sm font-medium rounded-md transition-colors border border-blue-500/20"
                  >
                    <FolderPlus className="w-4 h-4" />
                    New Project
                  </button>
                </div>
                <div className="p-2 border-b border-zinc-800">
                  <div className="relative">
                    <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-500" />
                    <input 
                      type="text" 
                      placeholder="Find project..."
                      className="w-full bg-[#0a0a0a] border border-zinc-700 rounded py-1.5 pl-8 pr-2 text-xs text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:border-blue-500"
                      value={projectSearch}
                      onChange={(e) => setProjectSearch(e.target.value)}
                    />
                  </div>
                </div>
                <div className="max-h-64 overflow-y-auto p-1">
                  {filteredProjects.map(proj => (
                    <button
                      key={proj.id}
                      onClick={() => { setActiveProject(proj); setIsProjectListOpen(false); }}
                      className={`w-full flex items-center justify-between p-2.5 rounded-md transition-colors ${
                        activeProject.id === proj.id ? 'bg-zinc-800' : 'hover:bg-zinc-800/50'
                      }`}
                    >
                      <div className="flex items-center gap-3 overflow-hidden">
                        <div className={`w-2.5 h-2.5 rounded-full ${proj.color} shrink-0`} />
                        <div className="flex flex-col items-start truncate">
                          <span className={`text-sm truncate ${activeProject.id === proj.id ? 'text-zinc-100 font-medium' : 'text-zinc-300'}`}>
                            {proj.name}
                          </span>
                          <span className="text-[10px] text-zinc-500 flex items-center gap-1">
                            <Clock className="w-2.5 h-2.5" />
                            {proj.lastActive}
                          </span>
                        </div>
                      </div>
                      {activeProject.id === proj.id && <CheckCircle2 className="w-4 h-4 text-zinc-400 shrink-0" />}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
          
          <div className="flex-1 overflow-y-auto py-4">
            
            {/* Project Scoped Nav */}
            <div className="px-4 mb-2 flex items-center gap-2">
              <div className="h-px bg-zinc-800 flex-1" />
              <span className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">Active Project</span>
              <div className="h-px bg-zinc-800 flex-1" />
            </div>
            
            <nav className="space-y-0.5 px-2 mb-6">
              {projectNavItems.map((item) => (
                <NavLink
                  key={item.name}
                  to={item.path}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                      isActive
                        ? 'bg-zinc-800/80 text-white'
                        : 'text-zinc-400 hover:bg-zinc-800/40 hover:text-zinc-200'
                    }`
                  }
                >
                  <item.icon className="w-4 h-4" />
                  {item.name}
                </NavLink>
              ))}
            </nav>

            {/* Global Nav */}
            <div className="px-4 mb-2 flex items-center gap-2">
              <div className="h-px bg-zinc-800 flex-1" />
              <span className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider flex items-center gap-1">
                <Globe className="w-3 h-3" /> Global
              </span>
              <div className="h-px bg-zinc-800 flex-1" />
            </div>

            <nav className="space-y-0.5 px-2">
              {globalNavItems.map((item) => (
                <NavLink
                  key={item.name}
                  to={item.path}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                      isActive
                        ? 'bg-zinc-800/80 text-white'
                        : 'text-zinc-400 hover:bg-zinc-800/40 hover:text-zinc-200'
                    }`
                  }
                >
                  <item.icon className="w-4 h-4" />
                  {item.name}
                </NavLink>
              ))}
            </nav>
          </div>

          <div className="p-4 border-t border-zinc-800 text-sm text-zinc-500 flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white text-xs font-bold shrink-0">
              JD
            </div>
            <span className="truncate">John Doe</span>
            <Settings className="w-4 h-4 ml-auto hover:text-zinc-300 cursor-pointer shrink-0" />
          </div>
        </div>

        {/* Main Content Area */}
        <div className="flex-1 flex overflow-hidden relative z-10">
          <Outlet />
          
          {/* Source Citation Expanded View (Global sliding panel) */}
          {activeCitation && (
            <div className="w-96 border-l border-zinc-800 bg-[#0f0f11] flex flex-col shadow-[0_0_40px_rgba(0,0,0,0.5)] absolute right-0 top-0 bottom-0 z-50 transition-transform transform translate-x-0">
              <div className="p-4 border-b border-zinc-800 flex items-center justify-between">
                <h3 className="font-semibold text-zinc-100 text-sm flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                  Source Citation
                </h3>
                <button 
                  onClick={() => setActiveCitation(null)}
                  className="text-zinc-500 hover:text-zinc-300 transition"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="p-4 flex-1 overflow-y-auto">
                <div className="mb-4">
                  <div className="text-xs text-zinc-500 uppercase tracking-wider mb-1">Document</div>
                  <div className="text-sm font-medium text-blue-400">{activeCitation.source}</div>
                  <div className="text-xs text-zinc-400 mt-1">{activeCitation.type} &middot; {activeCitation.date} &middot; Page {activeCitation.page}</div>
                </div>

                <div className="mb-4">
                  <div className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Original Extract</div>
                  <div className="bg-[#1a1a1e] border border-zinc-800 rounded p-3 text-sm text-zinc-300 leading-relaxed font-serif">
                    {activeCitation.snippet.split('**').map((part, i) => 
                      i % 2 === 1 ? <mark key={i} className="bg-emerald-500/20 text-emerald-200 rounded px-1">{part}</mark> : part
                    )}
                  </div>
                </div>

                <button className="w-full py-2 bg-zinc-800 hover:bg-zinc-700 text-sm font-medium rounded transition">
                  Open Full Document
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Create New Project Modal */}
        {isNewProjectModalOpen && (
          <div className="fixed inset-0 z-[100] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="bg-[#0f0f11] border border-zinc-800 rounded-xl w-full max-w-md shadow-2xl flex flex-col overflow-hidden">
              <div className="px-6 py-4 border-b border-zinc-800 flex items-center justify-between">
                <h2 className="text-lg font-semibold text-zinc-100">Create New Project</h2>
                <button onClick={() => setIsNewProjectModalOpen(false)} className="text-zinc-500 hover:text-zinc-300">
                  <X className="w-5 h-5" />
                </button>
              </div>
              <form onSubmit={handleCreateProject} className="p-6 flex flex-col gap-5">
                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1.5 uppercase tracking-wide">Project Name</label>
                  <input 
                    name="name"
                    autoFocus
                    required
                    placeholder="e.g., AAPL Margins Review"
                    className="w-full bg-[#111113] border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                  />
                </div>
                
                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1.5 uppercase tracking-wide">Scope Tickers (Optional)</label>
                  <div className="relative">
                    <Tag className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
                    <input 
                      name="tickers"
                      placeholder="NVDA, AMD, INTC..."
                      className="w-full bg-[#111113] border border-zinc-700 rounded-md pl-9 pr-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-2 uppercase tracking-wide">Project Color</label>
                  <div className="flex items-center gap-3">
                    {COLORS.map((c, i) => (
                      <label key={c} className="relative flex items-center justify-center cursor-pointer">
                        <input type="radio" name="color" value={c} defaultChecked={i === 0} className="peer sr-only" />
                        <div className={`w-6 h-6 rounded-full ${c} peer-checked:ring-2 peer-checked:ring-offset-2 peer-checked:ring-offset-[#0f0f11] peer-checked:ring-zinc-300 transition-all`} />
                      </label>
                    ))}
                  </div>
                </div>

                <div className="mt-4 flex gap-3 justify-end">
                  <button 
                    type="button" 
                    onClick={() => setIsNewProjectModalOpen(false)}
                    className="px-4 py-2 rounded-md text-sm font-medium text-zinc-400 hover:text-zinc-200 transition-colors"
                  >
                    Cancel
                  </button>
                  <button 
                    type="submit"
                    className="px-4 py-2 rounded-md text-sm font-medium bg-blue-600 hover:bg-blue-500 text-white transition-colors"
                  >
                    Create Project
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

      </div>
    </AppContext.Provider>
  );
}
