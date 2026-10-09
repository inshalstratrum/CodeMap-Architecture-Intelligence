import React, { useState, useCallback } from 'react';
import {
  Folder,
  FolderOpen,
  FileCode,
  Copy,
  Download,
  FileText,
  Search,
  Check,
  ChevronsRight,
  ChevronsLeft,
} from 'lucide-react';
import { ProjectData, ProjectNode } from '../lib/apiClient';

interface TreeViewProps {
  project: ProjectData | null;
  selectedRel: string | null;
  onSelectNode: (node: ProjectNode | null) => void;
}

export const TreeView: React.FC<TreeViewProps> = ({
  project,
  selectedRel,
  onSelectNode,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [copied, setCopied] = useState(false);
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set(['']));

  if (!project || !project.nodes) {
    return (
      <div className="flex-1 flex items-center justify-center text-slate-500 text-sm font-mono">
        No project scanned yet. Paste a folder path above and click Scan.
      </div>
    );
  }

  const toggleFolder = (rel: string) => {
    setExpandedFolders((prev) => {
      const next = new Set(prev);
      if (next.has(rel)) next.delete(rel);
      else next.add(rel);
      return next;
    });
  };

  const handleExpandAll = () => {
    const all = new Set<string>(['']);
    project.nodes.forEach((n) => {
      if (n.isDir) all.add(n.rel);
    });
    setExpandedFolders(all);
  };

  const handleCollapseAll = () => {
    setExpandedFolders(new Set(['']));
  };

  // Helper: check if all ancestors of this node are expanded
  const isItemVisible = (n: ProjectNode): boolean => {
    if (searchQuery.trim()) return true; // Show all matches during search
    if (n.rel === '') return true;
    let cur = n.parentRel;
    while (cur !== undefined) {
      if (!expandedFolders.has(cur)) return false;
      if (cur === '') break;
      const parentNode = project.nodes.find((p) => p.rel === cur);
      cur = parentNode ? parentNode.parentRel : '';
    }
    return true;
  };

  const filteredNodes = project.nodes.filter((n) => {
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      return n.name.toLowerCase().includes(q) || n.rel.toLowerCase().includes(q);
    }
    return isItemVisible(n);
  });

  const generateTreeText = (): string => {
    let out = `${project.name}/\n`;
    project.nodes.forEach((n) => {
      if (n.rel === '') return;
      const depth = n.rel.split('/').length;
      const indent = '  '.repeat(depth);
      out += `${indent}${n.isDir ? '📁 ' : '📄 '}${n.name} (${n.isDir ? `${n.childrenCount} items` : `${n.lines} lines`})\n`;
    });
    return out;
  };

  const handleCopyTree = () => {
    navigator.clipboard.writeText(generateTreeText());
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadTxt = () => {
    const text = generateTreeText();
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.download = `${project.name}_tree.txt`;
    link.href = url;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleExportObsidian = () => {
    let md = `# CodeMap Obsidian Vault: ${project.name}\n\n`;
    project.nodes.forEach((n) => {
      md += `## [[${n.name}]]\n`;
      md += `- Path: \`${n.path}\`\n`;
      md += `- Role: ${n.role}\n`;
      if (n.imports?.length) {
        md += `- **Depends on**: ${n.imports.map((imp) => `[[${imp}]]`).join(', ')}\n`;
      }
      if (n.importedBy?.length) {
        md += `- **Used by**: ${n.importedBy.map((by) => `[[${by}]]`).join(', ')}\n`;
      }
      md += `\n---\n\n`;
    });

    const blob = new Blob([md], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.download = `${project.name}_obsidian_vault.md`;
    link.href = url;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="w-full h-full flex flex-col bg-[#0b0f17] text-slate-200 select-none">
      {/* Action Toolbar */}
      <div className="h-11 border-b border-[#242d3f] bg-[#0e141f] px-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 flex-1 max-w-sm">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[#0b0f17] border border-[#242d3f] flex-1">
            <Search className="w-3.5 h-3.5 text-slate-500 shrink-0" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter files & folders..."
              className="w-full bg-transparent text-xs font-mono text-slate-200 placeholder-slate-500 outline-none"
            />
          </div>

          <button
            onClick={handleExpandAll}
            className="px-2 py-1 rounded bg-[#1a2232] hover:bg-[#232c3f] border border-[#2a3449] text-slate-200 text-xs font-mono flex items-center gap-1"
            title="Expand all folders"
          >
            <ChevronsRight className="w-3.5 h-3.5" />
            <span>Expand</span>
          </button>

          <button
            onClick={handleCollapseAll}
            className="px-2 py-1 rounded bg-[#1a2232] hover:bg-[#232c3f] border border-[#2a3449] text-slate-200 text-xs font-mono flex items-center gap-1"
            title="Collapse all to root"
          >
            <ChevronsLeft className="w-3.5 h-3.5" />
            <span>Collapse</span>
          </button>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleCopyTree}
            className="px-2.5 py-1 rounded bg-[#1a2232] hover:bg-[#232c3f] border border-[#2a3449] text-xs font-medium flex items-center gap-1.5 transition-colors"
            title="Copy indented tree text"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5 text-cyan-400" />}
            <span>{copied ? 'Copied!' : 'Copy Tree'}</span>
          </button>

          <button
            onClick={handleDownloadTxt}
            className="px-2.5 py-1 rounded bg-[#1a2232] hover:bg-[#232c3f] border border-[#2a3449] text-slate-300 hover:text-slate-100 text-xs font-medium flex items-center gap-1.5 transition-colors"
            title="Save tree as text file"
          >
            <Download className="w-3.5 h-3.5 text-emerald-400" />
            <span>Save .txt</span>
          </button>

          <button
            onClick={handleExportObsidian}
            className="px-2.5 py-1 rounded bg-[#1a2232] hover:bg-[#232c3f] border border-[#2a3449] text-purple-300 hover:text-purple-200 text-xs font-medium flex items-center gap-1.5 transition-colors"
            title="Export linked markdown notes for Obsidian"
          >
            <FileText className="w-3.5 h-3.5 text-purple-400" />
            <span>Obsidian Notes</span>
          </button>
        </div>
      </div>

      {/* Tree List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-0.5 font-mono text-xs">
        {filteredNodes.map((n) => {
          const depth = n.rel ? n.rel.split('/').length : 0;
          const isSelected = n.rel === selectedRel;
          const isDir = n.isDir;
          const isExpanded = expandedFolders.has(n.rel);

          return (
            <div
              key={n.id}
              onClick={() => {
                onSelectNode(n);
                if (isDir) {
                  toggleFolder(n.rel);
                }
              }}
              style={{ paddingLeft: `${depth * 18}px` }}
              className={`flex items-center justify-between px-2.5 py-1.5 rounded-md cursor-pointer transition-all ${
                isSelected
                  ? 'bg-cyan-950/80 border border-cyan-800/80 text-cyan-300 font-semibold'
                  : 'hover:bg-[#161c28] text-slate-300'
              }`}
            >
              <div className="flex items-center gap-2 overflow-hidden">
                {isDir ? (
                  <span className="p-0.5 rounded text-cyan-400 shrink-0">
                    {isExpanded ? (
                      <FolderOpen className="w-3.5 h-3.5 text-cyan-400" />
                    ) : (
                      <Folder className="w-3.5 h-3.5 text-cyan-400" />
                    )}
                  </span>
                ) : (
                  <FileCode className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                )}

                <span className="truncate">{n.name}</span>
              </div>

              <div className="flex items-center gap-3 text-[11px] text-slate-500 shrink-0">
                <span>{n.lang}</span>
                <span className="w-16 text-right">
                  {isDir ? `${n.childrenCount} items` : `${n.lines} lines`}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
