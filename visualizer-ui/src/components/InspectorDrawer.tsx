import React, { useState, useEffect } from 'react';
import {
  X,
  Sparkles,
  BarChart3,
  Network,
  ListTree,
  Loader2,
  ExternalLink,
  Code,
  FileCode,
  Folder,
} from 'lucide-react';
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from 'recharts';
import { ProjectNode, explainNode } from '../lib/apiClient';

interface InspectorDrawerProps {
  selectedNode: ProjectNode | null;
  isOpen: boolean;
  onClose: () => void;
  languagesDistribution?: { name: string; value: number }[];
}

const PIE_COLORS = ['#38bdf8', '#4ade80', '#facc15', '#f87171', '#c084fc', '#fb923c', '#94a3b8'];

export const InspectorDrawer: React.FC<InspectorDrawerProps> = ({
  selectedNode,
  isOpen,
  onClose,
  languagesDistribution = [],
}) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'deps' | 'defs'>('overview');
  const [explanation, setExplanation] = useState<string | null>(null);
  const [isExplaining, setIsExplaining] = useState(false);

  // Clear explanation when selected node changes
  useEffect(() => {
    setExplanation(selectedNode?.summary || null);
  }, [selectedNode]);

  if (!isOpen || !selectedNode) return null;

  const isDir = selectedNode.isDir;

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

  return (
    <div className="fixed top-14 right-0 bottom-0 w-96 bg-[#121722]/95 border-l border-[#242d3f] shadow-2xl backdrop-blur-xl z-20 flex flex-col overflow-hidden animate-in slide-in-from-right-4 duration-200">
      {/* Header */}
      <div className="p-4 border-b border-[#242d3f] bg-[#0e131d]/90 flex items-center justify-between">
        <div className="flex items-center gap-2 overflow-hidden">
          {isDir ? (
            <Folder className="w-4 h-4 text-cyan-400 shrink-0" />
          ) : (
            <FileCode className="w-4 h-4 text-cyan-400 shrink-0" />
          )}
          <div className="overflow-hidden">
            <h3 className="font-mono text-sm font-semibold text-slate-100 truncate" title={selectedNode.name}>
              {selectedNode.name}
            </h3>
            <p className="text-[10px] text-slate-500 font-mono truncate" title={selectedNode.rel || 'Project Root'}>
              {selectedNode.rel || 'Project Root'}
            </p>
          </div>
        </div>

        <button
          onClick={onClose}
          className="p-1 hover:bg-slate-800 text-slate-400 hover:text-slate-200 rounded-lg transition-colors"
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
            {/* Quick Metrics Cards */}
            <div className="grid grid-cols-2 gap-2">
              <div className="p-2.5 rounded-xl bg-[#171d2b] border border-[#242d3f]">
                <span className="text-[10px] text-slate-400 uppercase tracking-wider block">
                  Language / Type
                </span>
                <span className="text-sm font-semibold text-cyan-300 block mt-0.5">
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

            {/* Language Donut Chart for Directories */}
            {isDir && languagesDistribution.length > 0 && (
              <div className="p-3 bg-[#171d2b] border border-[#242d3f] rounded-xl space-y-2">
                <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
                  Codebase Languages Distribution
                </span>
                <div className="h-40">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={languagesDistribution}
                        innerRadius={32}
                        outerRadius={52}
                        paddingAngle={3}
                        dataKey="value"
                      >
                        {languagesDistribution.map((_, index) => (
                          <Cell key={`cell-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#0f172a',
                          border: '1px solid #334155',
                          borderRadius: '8px',
                          fontSize: '11px',
                        }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {/* Explain with AI Button */}
            <div className="space-y-2">
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
                <div className="p-3 bg-[#0d121c] border border-[#242d3f] rounded-xl text-slate-200 text-xs leading-relaxed whitespace-pre-wrap selection:bg-cyan-900/60">
                  {explanation}
                </div>
              ) : (
                <div className="text-[11px] text-slate-500 text-center py-4 italic">
                  Click the button above for a plain English breakdown of what this file does, how it connects, and key instructions.
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'deps' && (
          <div className="space-y-4">
            {/* Outbound Imports */}
            <div>
              <div className="text-[10px] font-semibold text-emerald-400 uppercase tracking-wider mb-1.5 flex items-center gap-1">
                <span>Outbound Imports (This file uses):</span>
              </div>
              {selectedNode.imports.length > 0 ? (
                <div className="space-y-1">
                  {selectedNode.imports.map((imp, idx) => (
                    <div key={idx} className="p-2 rounded-lg bg-[#161c28] border border-[#242d3f] text-slate-300 text-xs truncate">
                      {imp}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-slate-500 text-[11px] italic">No local imports found.</div>
              )}
            </div>

            {/* Inbound Dependents */}
            <div>
              <div className="text-[10px] font-semibold text-amber-400 uppercase tracking-wider mb-1.5 flex items-center gap-1">
                <span>Inbound Dependents (Files using this):</span>
              </div>
              {selectedNode.importedBy.length > 0 ? (
                <div className="space-y-1">
                  {selectedNode.importedBy.map((by, idx) => (
                    <div key={idx} className="p-2 rounded-lg bg-[#161c28] border border-[#242d3f] text-slate-300 text-xs truncate">
                      {by}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-slate-500 text-[11px] italic">No inbound dependents recorded.</div>
              )}
            </div>

            {/* External Libraries */}
            {selectedNode.external.length > 0 && (
              <div>
                <div className="text-[10px] font-semibold text-purple-400 uppercase tracking-wider mb-1.5">
                  External Packages Used:
                </div>
                <div className="flex flex-wrap gap-1">
                  {selectedNode.external.map((ext, idx) => (
                    <span key={idx} className="px-2 py-1 rounded bg-purple-950/60 border border-purple-800/40 text-purple-300 text-[10px]">
                      {ext}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'defs' && (
          <div className="space-y-4">
            {/* Functions / Classes */}
            <div>
              <div className="text-[10px] font-semibold text-cyan-400 uppercase tracking-wider mb-1.5">
                Defined Functions & Classes:
              </div>
              {selectedNode.defines.length > 0 ? (
                <div className="space-y-1">
                  {selectedNode.defines.map((def, idx) => (
                    <div key={idx} className="p-2 rounded-lg bg-[#161c28] border border-[#242d3f] text-cyan-300 text-xs truncate">
                      {def}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-slate-500 text-[11px] italic">No function or class definitions extracted.</div>
              )}
            </div>

            {/* REST Endpoints */}
            {selectedNode.endpoints.length > 0 && (
              <div>
                <div className="text-[10px] font-semibold text-amber-400 uppercase tracking-wider mb-1.5">
                  Exposed Endpoints / Routes:
                </div>
                <div className="space-y-1">
                  {selectedNode.endpoints.map((ep, idx) => (
                    <div key={idx} className="p-2 rounded-lg bg-[#161c28] border border-[#242d3f] text-amber-300 text-xs truncate">
                      {ep}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
