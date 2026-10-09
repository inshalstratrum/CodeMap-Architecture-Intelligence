import { memo } from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import { Folder, FolderOpen, FileCode, Code, FileJson, Globe, Layers, ArrowUpRight, ArrowDownLeft } from 'lucide-react';
import { ProjectNode } from '../lib/apiClient';

export interface CodebaseNodeData {
  node: ProjectNode;
  isExpanded?: boolean;
  onToggleExpand?: (id: string) => void;
  isDependencyOfSelected?: boolean; // uses (green)
  isDependentOfSelected?: boolean;  // used by (orange)
  [key: string]: unknown;
}

const getLanguageBadge = (lang: string) => {
  const l = lang.toLowerCase();
  if (l.includes('python')) return { bg: 'bg-blue-500/10 text-blue-400 border-blue-500/20', icon: Code };
  if (l.includes('typescript') || l.includes('ts')) return { bg: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20', icon: Code };
  if (l.includes('javascript') || l.includes('js')) return { bg: 'bg-amber-500/10 text-amber-400 border-amber-500/20', icon: Code };
  if (l.includes('json')) return { bg: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20', icon: FileJson };
  if (l.includes('html') || l.includes('css')) return { bg: 'bg-rose-500/10 text-rose-400 border-rose-500/20', icon: Globe };
  return { bg: 'bg-slate-500/10 text-slate-400 border-slate-500/20', icon: FileCode };
};

export const CodebaseNodeCard = memo(({ id, data, selected, targetPosition, sourcePosition }: NodeProps) => {
  const nodeData = data as CodebaseNodeData;
  const item = nodeData.node;
  const isDir = item?.isDir ?? false;
  const isExpanded = nodeData.isExpanded ?? false;
  const hasChildren = isDir && (item?.childrenCount ?? 0) > 0;

  const tPos = targetPosition || Position.Left;
  const sPos = sourcePosition || Position.Right;

  const badge = getLanguageBadge(item?.lang || '');
  const BadgeIcon = badge.icon;

  const isUses = nodeData.isDependencyOfSelected;
  const isUsedBy = nodeData.isDependentOfSelected;

  return (
    <div
      className={`relative min-w-[200px] max-w-[280px] rounded-xl border transition-all duration-200 shadow-xl select-none ${
        selected
          ? 'border-cyan-400 ring-2 ring-cyan-400/40 bg-[#1e2638]'
          : isUses
          ? 'border-emerald-400 ring-2 ring-emerald-400/30 bg-[#162520]'
          : isUsedBy
          ? 'border-amber-400 ring-2 ring-amber-400/30 bg-[#252016]'
          : isDir
          ? 'border-[#2d374d] bg-[#141a27] hover:border-slate-500 hover:bg-[#182030]'
          : 'border-[#222b3d] bg-[#121620] hover:border-slate-500 hover:bg-[#161c28]'
      }`}
    >
      <Handle type="target" position={tPos} className="!w-2.5 !h-2.5 !bg-cyan-400 !border-2 !border-[#0b0f17]" />
      <Handle type="source" position={sPos} className="!w-2.5 !h-2.5 !bg-cyan-400 !border-2 !border-[#0b0f17]" />

      {/* Top Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-[#232c3f] bg-[#0e131d]/60 rounded-t-xl">
        <div className="flex items-center gap-2 overflow-hidden">
          {isDir ? (
            <button
              onClick={(e) => {
                e.stopPropagation();
                nodeData.onToggleExpand?.(id);
              }}
              className="p-1 rounded bg-[#1e2638] hover:bg-cyan-600/30 text-cyan-400 transition-colors"
              title={isExpanded ? "Collapse folder" : "Expand folder"}
            >
              {isExpanded ? (
                <FolderOpen className="w-3.5 h-3.5 text-cyan-400" />
              ) : (
                <Folder className="w-3.5 h-3.5 text-cyan-400" />
              )}
            </button>
          ) : (
            <BadgeIcon className="w-3.5 h-3.5 text-slate-400 shrink-0" />
          )}

          <span className="font-mono text-xs font-semibold text-slate-200 truncate" title={item?.name}>
            {item?.name || id}
          </span>
        </div>

        {/* Expand indicator for folders */}
        {hasChildren && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              nodeData.onToggleExpand?.(id);
            }}
            className="w-4 h-4 rounded bg-[#1f283a] hover:bg-[#2a354c] text-slate-300 text-[10px] font-mono flex items-center justify-center font-bold"
          >
            {isExpanded ? '−' : '+'}
          </button>
        )}
      </div>

      {/* Node Body Details */}
      <div className="p-2.5 space-y-1.5 text-xs font-mono">
        <div className="flex items-center justify-between text-[11px]">
          <span className={`px-1.5 py-0.5 rounded border text-[10px] font-semibold ${badge.bg}`}>
            {item?.lang || (isDir ? 'Folder' : 'File')}
          </span>

          <span className="text-slate-400 text-[10px]">
            {isDir ? `${item?.childrenCount || 0} items` : `${item?.lines || 0} lines`}
          </span>
        </div>

        {/* Connections overview */}
        <div className="flex items-center justify-between text-[10px] text-slate-400 pt-1 border-t border-[#1f2738]">
          <div className="flex items-center gap-1 text-emerald-400/90" title="Outbound imports (this file uses)">
            <ArrowUpRight className="w-3 h-3" />
            <span>{item?.imports?.length || 0} uses</span>
          </div>

          <div className="flex items-center gap-1 text-amber-400/90" title="Inbound dependents (files using this)">
            <ArrowDownLeft className="w-3 h-3" />
            <span>{item?.importedBy?.length || 0} used by</span>
          </div>
        </div>
      </div>
    </div>
  );
});

CodebaseNodeCard.displayName = 'CodebaseNodeCard';
