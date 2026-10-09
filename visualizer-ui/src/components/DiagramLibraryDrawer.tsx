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

interface DiagramLibraryDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  nodes: ProjectNode[];
  onSelectItem: (node: ProjectNode) => void;
}

export const DiagramLibraryDrawer: React.FC<DiagramLibraryDrawerProps> = ({
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
    <div className="fixed top-14 left-0 bottom-0 w-80 bg-[#121722]/95 border-r border-[#242d3f] shadow-2xl backdrop-blur-xl z-20 flex flex-col overflow-hidden animate-in slide-in-from-left-4 duration-200 select-none">
      {/* Drawer Header */}
      <div className="p-4 border-b border-[#242d3f] bg-[#0e131d]/90 flex items-center justify-between">
        <div className="flex items-center gap-2 text-cyan-400">
          <BookOpen className="w-4 h-4" />
          <h3 className="font-mono text-sm font-semibold text-slate-100">
            Diagram Library
          </h3>
        </div>

        <button
          onClick={onClose}
          className="p-1 hover:bg-slate-800 text-slate-400 hover:text-slate-200 rounded-lg transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Search & Filter Controls */}
      <div className="p-3 border-b border-[#242d3f] bg-[#0f141f] space-y-2.5">
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

        <label className="flex items-center gap-2 text-xs text-slate-400 hover:text-slate-200 cursor-pointer">
          <input
            type="checkbox"
            checked={onlyWithDiagrams}
            onChange={(e) => setOnlyWithDiagrams(e.target.checked)}
            className="rounded bg-slate-900 border-slate-700 text-cyan-500 focus:ring-0"
          />
          <Filter className="w-3 h-3 text-cyan-400" />
          <span>Only show items with diagrams</span>
        </label>
      </div>

      {/* Item List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-1 text-xs font-mono">
        {filtered.map((node) => {
          const hasDiagram = vaultSet.has(node.rel);

          return (
            <div
              key={node.id}
              onClick={() => onSelectItem(node)}
              className="flex items-center justify-between p-2 rounded-lg hover:bg-[#182030] cursor-pointer transition-colors border border-transparent hover:border-[#242d3f] text-slate-300"
            >
              <div className="flex items-center gap-2 overflow-hidden">
                {node.isDir ? (
                  <Folder className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                ) : (
                  <FileCode className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                )}
                <span className="truncate" title={node.name}>
                  {node.name}
                </span>
              </div>

              <div className="flex items-center gap-1.5 shrink-0">
                {hasDiagram && (
                  <span className="px-1.5 py-0.5 rounded bg-cyan-950 text-cyan-400 text-[10px] border border-cyan-800/50">
                    diagram saved
                  </span>
                )}
                <ChevronRight className="w-3 h-3 text-slate-600" />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
