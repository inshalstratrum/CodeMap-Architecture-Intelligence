import React, { useState, useEffect } from 'react';
import {
  X,
  BookOpen,
  Search,
  FileCode,
  Folder,
  ChevronRight,
  Filter,
} from 'lucide-react';
import { ProjectNode, getVaultItems } from '../lib/apiClient';

interface DiagramLibraryPanelProps {
  isOpen: boolean;
  onClose: () => void;
  nodes: ProjectNode[];
  onSelectItem: (node: ProjectNode) => void;
}

export const DiagramLibraryPanel: React.FC<DiagramLibraryPanelProps> = ({
  isOpen,
  onClose,
  nodes,
  onSelectItem,
}) => {
  const [vaultItems, setVaultItems] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [onlyWithDiagrams, setOnlyWithDiagrams] = useState(false);

  useEffect(() => {
    if (isOpen) {
      getVaultItems().then((items) => setVaultItems(items));
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const vaultSet = new Set(vaultItems);

  const filtered = nodes.filter((n) => {
    if (onlyWithDiagrams && !vaultSet.has(n.rel)) return false;
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return n.name.toLowerCase().includes(q) || n.rel.toLowerCase().includes(q);
  });

  return (
    <aside className="w-72 h-full bg-[#111622] border-r border-[#242d3f] flex flex-col z-10 shrink-0 select-none transition-all duration-200">
      {/* Header */}
      <div className="p-3.5 border-b border-[#242d3f] bg-[#0d121c] flex items-center justify-between">
        <div className="flex items-center gap-2 text-cyan-400">
          <BookOpen className="w-4 h-4" />
          <h3 className="font-mono text-xs font-bold text-slate-100 uppercase tracking-wider">
            Diagram Library ({filtered.length})
          </h3>
        </div>

        <button
          onClick={onClose}
          className="p-1 hover:bg-[#1a2335] text-slate-400 hover:text-slate-100 rounded-md transition-colors"
          title="Close Library Panel"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Filter Controls */}
      <div className="p-3 border-b border-[#242d3f] bg-[#0f141f] space-y-2">
        <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-[#0b0f17] border border-[#242d3f] text-xs font-mono">
          <Search className="w-3.5 h-3.5 text-slate-500 shrink-0" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search items..."
            className="w-full bg-transparent text-slate-200 placeholder-slate-500 outline-none text-xs"
          />
        </div>

        <label className="flex items-center gap-2 text-[11px] font-mono text-slate-400 hover:text-slate-200 cursor-pointer">
          <input
            type="checkbox"
            checked={onlyWithDiagrams}
            onChange={(e) => setOnlyWithDiagrams(e.target.checked)}
            className="rounded bg-slate-900 border-slate-700 text-cyan-500 focus:ring-0 w-3.5 h-3.5"
          />
          <Filter className="w-3 h-3 text-cyan-400" />
          <span>Only show items with diagrams</span>
        </label>
      </div>

      {/* Item List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1 text-xs font-mono">
        {filtered.map((node) => {
          const hasDiagram = vaultSet.has(node.rel);

          return (
            <div
              key={node.id}
              onClick={() => onSelectItem(node)}
              className="flex items-center justify-between p-2 rounded-lg hover:bg-[#182030] cursor-pointer transition-colors border border-transparent hover:border-[#242d3f] text-slate-300 group"
            >
              <div className="flex items-center gap-2 overflow-hidden">
                {node.isDir ? (
                  <Folder className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                ) : (
                  <FileCode className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                )}
                <span className="truncate group-hover:text-cyan-300" title={node.name}>
                  {node.name}
                </span>
              </div>

              <div className="flex items-center gap-1.5 shrink-0">
                {hasDiagram && (
                  <span className="px-1.5 py-0.5 rounded bg-cyan-950 text-cyan-400 text-[10px] border border-cyan-800/50">
                    saved
                  </span>
                )}
                <ChevronRight className="w-3 h-3 text-slate-600 group-hover:text-cyan-400" />
              </div>
            </div>
          );
        })}

        {filtered.length === 0 && (
          <div className="text-center py-8 text-slate-500 text-xs font-mono">
            No matching items found.
          </div>
        )}
      </div>
    </aside>
  );
};
