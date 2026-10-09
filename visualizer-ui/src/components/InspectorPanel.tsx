import React, { useState, useEffect } from 'react';
import {
  X,
  Sparkles,
  BarChart3,
  Network,
  ListTree,
  Loader2,
  FileCode,
  Folder,
  ExternalLink,
  Copy,
  Check,
  FolderOpen,
  ArrowUpRight,
  ArrowDownLeft,
  FileJson,
  Package,
} from 'lucide-react';
import { ProjectNode, explainNode, openInSystem } from '../lib/apiClient';

interface InspectorPanelProps {
  selectedNode: ProjectNode | null;
  isOpen: boolean;
  onClose: () => void;
  languagesDistribution?: { name: string; value: number }[];
  totalProjectFiles?: number;
  onSelectRel?: (rel: string) => void;
  onNavigateToDiagram?: (rel: string) => void;
  onNavigateToJson?: (rel: string) => void;
}

const LANG_COLORS: Record<string, string> = {
  python: '#38bdf8',
  typescript: '#38bdf8',
  javascript: '#facc15',
  json: '#4ade80',
  'html/css': '#f472b6',
  markdown: '#a78bfa',
  other: '#94a3b8',
};

export const InspectorPanel: React.FC<InspectorPanelProps> = ({
  selectedNode,
  isOpen,
  onClose,
  languagesDistribution = [],
  totalProjectFiles = 1,
  onSelectRel,
  onNavigateToDiagram,
  onNavigateToJson,
}) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'deps' | 'defs'>('overview');
  const [explanation, setExplanation] = useState<string | null>(null);
  const [isExplaining, setIsExplaining] = useState(false);
  const [copiedRel, setCopiedRel] = useState(false);
  const [openedExplorer, setOpenedExplorer] = useState(false);

  useEffect(() => {
    setExplanation(selectedNode?.summary || null);
  }, [selectedNode]);

  if (!isOpen || !selectedNode) return null;

  const isDir = selectedNode.isDir;
  const isJson = selectedNode.name.toLowerCase().endsWith('.json');

  const handleRunExplain = async () => {
    setIsExplaining(true);
    try {
      const res = await explainNode(selectedNode.rel, !isDir);
      setExplanation(res);
    } catch (err) {
      setExplanation(`⚠️ Failed to generate AI explanation: ${err}`);
    } finally {
      setIsExplaining(false);
    }
  };

  const handleCopyPath = () => {
    navigator.clipboard.writeText(selectedNode.rel || selectedNode.path);
    setCopiedRel(true);
    setTimeout(() => setCopiedRel(false), 2000);
  };

  const handleOpenExplorer = async () => {
    const success = await openInSystem('', selectedNode.rel);
    if (success) {
      setOpenedExplorer(true);
      setTimeout(() => setOpenedExplorer(false), 2500);
    } else {
      alert('Could not open file in Windows Explorer.');
    }
  };

  const totalFilesCount = Math.max(1, totalProjectFiles);

  return (
    <aside className="w-96 h-full bg-[#111622] border-l border-[#242d3f] flex flex-col z-10 shrink-0 select-none transition-all duration-200">
      {/* Header */}
      <div className="p-3.5 border-b border-[#242d3f] bg-[#0d121c] flex items-center justify-between">
        <div className="flex items-center gap-2.5 overflow-hidden">
          {isDir ? (
            <Folder className="w-4 h-4 text-cyan-400 shrink-0" />
          ) : (
            <FileCode className="w-4 h-4 text-cyan-400 shrink-0" />
          )}
          <div className="overflow-hidden">
            <h3 className="font-mono text-xs font-bold text-slate-100 truncate" title={selectedNode.name}>
              {selectedNode.name}
            </h3>
            <p className="text-[10px] text-slate-500 font-mono truncate" title={selectedNode.rel || 'Project Root'}>
              {selectedNode.rel || 'Project Root'}
            </p>
          </div>
        </div>

        <button
          onClick={onClose}
          className="p-1 hover:bg-[#1a2335] text-slate-400 hover:text-slate-100 rounded-md transition-colors"
          title="Close Inspector Panel"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex items-center border-b border-[#242d3f] bg-[#0f141f] px-3 gap-1 text-xs">
        <button
          onClick={() => setActiveTab('overview')}
          className={`flex items-center gap-1.5 px-3 py-2 border-b-2 font-medium transition-colors ${
            activeTab === 'overview'
              ? 'border-cyan-400 text-cyan-300'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <BarChart3 className="w-3.5 h-3.5" />
          <span>Overview</span>
        </button>

        <button
          onClick={() => setActiveTab('deps')}
          className={`flex items-center gap-1.5 px-3 py-2 border-b-2 font-medium transition-colors ${
            activeTab === 'deps'
              ? 'border-cyan-400 text-cyan-300'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Network className="w-3.5 h-3.5" />
          <span>Dependencies ({selectedNode.imports.length + selectedNode.importedBy.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('defs')}
          className={`flex items-center gap-1.5 px-3 py-2 border-b-2 font-medium transition-colors ${
            activeTab === 'defs'
              ? 'border-cyan-400 text-cyan-300'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <ListTree className="w-3.5 h-3.5" />
          <span>Definitions ({selectedNode.defines.length + selectedNode.endpoints.length})</span>
        </button>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs font-mono text-slate-300">
        {activeTab === 'overview' && (
          <div className="space-y-4">
            {/* Master Quick Actions Toolbar */}
            <div className="p-2.5 rounded-xl bg-[#0e131d] border border-[#242d3f] space-y-2">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                Master Quick Actions:
              </span>
              <div className="grid grid-cols-2 gap-1.5">
                {onNavigateToDiagram && (
                  <button
                    onClick={() => onNavigateToDiagram(selectedNode.rel)}
                    className="px-2.5 py-1.5 rounded-lg bg-[#1a2335] hover:bg-cyan-950/80 border border-[#2a3449] hover:border-cyan-600/80 text-cyan-300 text-[11px] font-medium flex items-center gap-1.5 transition-all text-left"
                    title="Generate architecture diagram for this item in Diagram Studio"
                  >
                    <Sparkles className="w-3 h-3 text-cyan-400 shrink-0" />
                    <span className="truncate">AI Diagram</span>
                  </button>
                )}

                {isJson && onNavigateToJson && (
                  <button
                    onClick={() => onNavigateToJson(selectedNode.rel)}
                    className="px-2.5 py-1.5 rounded-lg bg-[#1a2335] hover:bg-emerald-950/80 border border-[#2a3449] hover:border-emerald-600/80 text-emerald-300 text-[11px] font-medium flex items-center gap-1.5 transition-all text-left"
                    title="View in JSON Graph & Object visualizer"
                  >
                    <FileJson className="w-3 h-3 text-emerald-400 shrink-0" />
                    <span className="truncate">JSON Graph</span>
                  </button>
                )}

                <button
                  onClick={handleOpenExplorer}
                  className="px-2.5 py-1.5 rounded-lg bg-[#1a2335] hover:bg-[#25324d] border border-[#2a3449] text-slate-200 text-[11px] font-medium flex items-center gap-1.5 transition-all text-left"
                  title="Open file in Windows Explorer"
                >
                  {openedExplorer ? (
                    <Check className="w-3 h-3 text-emerald-400 shrink-0" />
                  ) : (
                    <FolderOpen className="w-3 h-3 text-amber-400 shrink-0" />
                  )}
                  <span className="truncate">{openedExplorer ? 'Opened!' : 'In Explorer'}</span>
                </button>

                <button
                  onClick={handleCopyPath}
                  className="px-2.5 py-1.5 rounded-lg bg-[#1a2335] hover:bg-[#25324d] border border-[#2a3449] text-slate-200 text-[11px] font-medium flex items-center gap-1.5 transition-all text-left"
                  title="Copy relative path to clipboard"
                >
                  {copiedRel ? (
                    <Check className="w-3 h-3 text-emerald-400 shrink-0" />
                  ) : (
                    <Copy className="w-3 h-3 text-slate-400 shrink-0" />
                  )}
                  <span className="truncate">{copiedRel ? 'Copied!' : 'Copy Path'}</span>
                </button>
              </div>
            </div>

            {/* Quick Metrics Cards */}
            <div className="grid grid-cols-2 gap-2">
              <div className="p-2.5 rounded-xl bg-[#171d2b] border border-[#242d3f]">
                <span className="text-[10px] text-slate-400 uppercase tracking-wider block">
                  Language / Type
                </span>
                <span className="text-sm font-semibold text-cyan-300 block mt-0.5 truncate">
                  {selectedNode.lang}
                </span>
              </div>

              <div className="p-2.5 rounded-xl bg-[#171d2b] border border-[#242d3f]">
                <span className="text-[10px] text-slate-400 uppercase tracking-wider block">
                  {isDir ? 'Sub-Items' : 'Lines of Code'}
                </span>
                <span className="text-sm font-semibold text-emerald-300 block mt-0.5">
                  {isDir ? `${selectedNode.childrenCount} items` : `${selectedNode.lines} lines`}
                </span>
              </div>
            </div>

            {/* Role & Summary */}
            <div className="p-3 bg-[#171d2b] border border-[#242d3f] rounded-xl space-y-1.5">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                Role in Architecture:
              </span>
              <p className="text-xs text-slate-200 leading-relaxed font-sans">
                {selectedNode.role || 'General codebase module'}
              </p>
            </div>

            {/* Language Breakdown Progress Bars (Replaces unzoomable tiny donut) */}
            {isDir && languagesDistribution.length > 0 && (
              <div className="p-3 bg-[#171d2b] border border-[#242d3f] rounded-xl space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold text-slate-300 uppercase tracking-wider">
                    Codebase Languages Breakdown
                  </span>
                  <span className="text-[10px] text-slate-400">
                    {totalProjectFiles} total files
                  </span>
                </div>

                <div className="space-y-2">
                  {languagesDistribution.map((lang, idx) => {
                    const pct = Math.round((lang.value / totalFilesCount) * 100);
                    const color = LANG_COLORS[lang.name.toLowerCase()] || '#38bdf8';

                    return (
                      <div key={idx} className="space-y-1">
                        <div className="flex items-center justify-between text-[11px]">
                          <span className="font-semibold text-slate-200">{lang.name}</span>
                          <span className="text-slate-400">
                            {lang.value} files ({pct}%)
                          </span>
                        </div>
                        <div className="w-full h-2 rounded-full bg-[#0b0f17] overflow-hidden border border-[#242d3f]">
                          <div
                            className="h-full rounded-full transition-all duration-300"
                            style={{ width: `${Math.max(4, pct)}%`, backgroundColor: color }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Explain with AI Button */}
            <div className="space-y-2 pt-1">
              <button
                onClick={handleRunExplain}
                disabled={isExplaining}
                className={`w-full py-2.5 rounded-xl font-semibold text-xs flex items-center justify-center gap-1.5 transition-all ${
                  isExplaining
                    ? 'bg-cyan-950 text-cyan-400 border border-cyan-800'
                    : 'bg-cyan-500 hover:bg-cyan-400 text-black shadow-lg shadow-cyan-500/20 active:scale-95'
                }`}
              >
                {isExplaining ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Analyzing with AI…</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3.5 h-3.5 fill-current" />
                    <span>Explain in Plain English (AI)</span>
                  </>
                )}
              </button>

              {explanation ? (
                <div className="p-3 bg-[#0d121c] border border-[#242d3f] rounded-xl text-slate-200 text-xs leading-relaxed whitespace-pre-wrap selection:bg-cyan-900/60 max-h-96 overflow-y-auto">
                  {explanation}
                </div>
              ) : (
                <div className="text-[11px] text-slate-500 text-center py-3 italic">
                  Click the button above for an AI breakdown of this component's role and connections.
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'deps' && (
          <div className="space-y-4">
            <div>
              <div className="text-[10px] font-semibold text-emerald-400 uppercase tracking-wider mb-1.5 flex items-center justify-between">
                <span>🟢 Outbound Imports (This file uses):</span>
                <span>{selectedNode.imports.length}</span>
              </div>
              {selectedNode.imports.length > 0 ? (
                <div className="space-y-1">
                  {selectedNode.imports.map((imp, idx) => (
                    <button
                      key={idx}
                      onClick={() => onSelectRel?.(imp)}
                      className="w-full text-left p-2 rounded-lg bg-[#161c28] hover:bg-[#1e2738] border border-[#242d3f] hover:border-emerald-500/50 text-slate-300 hover:text-emerald-300 text-xs flex items-center justify-between group transition-colors"
                      title={`Click to jump to: ${imp}`}
                    >
                      <span className="truncate pr-2">{imp}</span>
                      <ArrowUpRight className="w-3 h-3 text-slate-500 group-hover:text-emerald-400 shrink-0" />
                    </button>
                  ))}
                </div>
              ) : (
                <div className="text-slate-500 text-[11px] italic">No local imports found.</div>
              )}
            </div>

            <div>
              <div className="text-[10px] font-semibold text-amber-400 uppercase tracking-wider mb-1.5 flex items-center justify-between">
                <span>🟠 Inbound Dependents (Files using this):</span>
                <span>{selectedNode.importedBy.length}</span>
              </div>
              {selectedNode.importedBy.length > 0 ? (
                <div className="space-y-1">
                  {selectedNode.importedBy.map((by, idx) => (
                    <button
                      key={idx}
                      onClick={() => onSelectRel?.(by)}
                      className="w-full text-left p-2 rounded-lg bg-[#161c28] hover:bg-[#1e2738] border border-[#242d3f] hover:border-amber-500/50 text-slate-300 hover:text-amber-300 text-xs flex items-center justify-between group transition-colors"
                      title={`Click to jump to: ${by}`}
                    >
                      <span className="truncate pr-2">{by}</span>
                      <ArrowDownLeft className="w-3 h-3 text-slate-500 group-hover:text-amber-400 shrink-0" />
                    </button>
                  ))}
                </div>
              ) : (
                <div className="text-slate-500 text-[11px] italic">No inbound dependents recorded.</div>
              )}
            </div>

            {selectedNode.external.length > 0 && (
              <div>
                <div className="text-[10px] font-semibold text-purple-400 uppercase tracking-wider mb-1.5 flex items-center justify-between">
                  <span>🟣 External Packages Used:</span>
                  <span>{selectedNode.external.length}</span>
                </div>
                <div className="flex flex-wrap gap-1">
                  {selectedNode.external.map((ext, idx) => (
                    <span key={idx} className="px-2 py-1 rounded bg-purple-950/60 border border-purple-800/40 text-purple-300 text-[10px] flex items-center gap-1">
                      <Package className="w-2.5 h-2.5" />
                      <span>{ext}</span>
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'defs' && (
          <div className="space-y-4">
            <div>
              <div className="text-[10px] font-semibold text-cyan-400 uppercase tracking-wider mb-1.5 flex items-center justify-between">
                <span>Defined Functions & Classes:</span>
                <span>{selectedNode.defines.length}</span>
              </div>
              {selectedNode.defines.length > 0 ? (
                <div className="space-y-1">
                  {selectedNode.defines.map((def, idx) => (
                    <div key={idx} className="p-2 rounded-lg bg-[#161c28] border border-[#242d3f] text-cyan-300 text-xs truncate" title={def}>
                      {def}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-slate-500 text-[11px] italic">No definitions extracted.</div>
              )}
            </div>

            {selectedNode.endpoints.length > 0 && (
              <div>
                <div className="text-[10px] font-semibold text-amber-400 uppercase tracking-wider mb-1.5 flex items-center justify-between">
                  <span>Exposed Endpoints / Routes:</span>
                  <span>{selectedNode.endpoints.length}</span>
                </div>
                <div className="space-y-1">
                  {selectedNode.endpoints.map((ep, idx) => (
                    <div key={idx} className="p-2 rounded-lg bg-[#161c28] border border-[#242d3f] text-amber-300 text-xs truncate" title={ep}>
                      {ep}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </aside>
  );
};
