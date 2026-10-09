import { memo } from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';

export interface FieldItem {
  key: string;
  value: string | number | boolean | null;
  type: 'string' | 'number' | 'boolean' | 'null' | 'object' | 'array' | 'color';
  colorHex?: string;
  childCount?: number;
  childNodeId?: string;
}

export interface NodeCardData {
  title?: string;
  isRoot?: boolean;
  fields?: FieldItem[];
  collapsed?: boolean;
  hasChildren?: boolean;
  onToggleCollapse?: (nodeId: string) => void;
  onSelectField?: (nodeId: string, field: FieldItem) => void;
  width?: number;
  [key: string]: unknown;
}

const HEX_COLOR_REGEX = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i;

export const NodeCard = memo(({ id, data, selected, targetPosition, sourcePosition }: NodeProps) => {
  const nodeData = data as NodeCardData;
  const fields = nodeData.fields || [];
  const hasChildren = nodeData.hasChildren || false;
  const isCollapsed = nodeData.collapsed || false;

  const tPos = targetPosition || Position.Left;
  const sPos = sourcePosition || Position.Right;

  return (
    <div
      className={`relative min-w-[220px] max-w-[340px] rounded-xl border transition-all duration-200 shadow-xl ${
        selected
          ? 'border-cyan-400 ring-2 ring-cyan-400/40 bg-[#1e2638]'
          : 'border-[#2a3449] bg-[#161c28] hover:border-slate-500 hover:bg-[#1a2232]'
      }`}
    >
      {/* Target & Source Handles with seamless styling */}
      <Handle
        type="target"
        position={tPos}
        className="!w-2.5 !h-2.5 !bg-cyan-400 !border-2 !border-[#0b0f17]"
      />
      <Handle
        type="source"
        position={sPos}
        className="!w-2.5 !h-2.5 !bg-cyan-400 !border-2 !border-[#0b0f17]"
      />

      {/* Header bar */}
      <div className="flex items-center justify-between px-3.5 py-2.5 border-b border-[#242d3f] bg-[#121722]/70 rounded-t-xl">
        <div className="flex items-center gap-2 overflow-hidden">
          {hasChildren && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                nodeData.onToggleCollapse?.(id);
              }}
              className="w-5 h-5 flex items-center justify-center rounded bg-[#232c3f] hover:bg-cyan-600/30 text-slate-300 hover:text-cyan-300 transition-colors font-mono text-xs font-bold shrink-0"
              title={isCollapsed ? 'Expand child nodes' : 'Collapse child nodes'}
            >
              {isCollapsed ? '+' : '−'}
            </button>
          )}
          <span className="font-mono text-xs font-semibold text-cyan-300 truncate">
            {nodeData.title || id}
          </span>
        </div>

        {hasChildren && isCollapsed && (
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-800/50 shrink-0">
            hidden
          </span>
        )}
      </div>

      {/* Fields List */}
      {!isCollapsed && fields.length > 0 && (
        <div className="p-2.5 space-y-1 text-xs font-mono">
          {fields.map((field, idx) => {
            const isHexColor = typeof field.value === 'string' && HEX_COLOR_REGEX.test(field.value.trim());

            return (
              <div
                key={idx}
                onClick={(e) => {
                  e.stopPropagation();
                  nodeData.onSelectField?.(id, field);
                }}
                className="flex items-center justify-between gap-3 text-slate-300 hover:text-white px-1.5 py-1 rounded hover:bg-[#1f293d]/80 cursor-pointer transition-colors group"
                title={`Click to inspect '${field.key}'`}
              >
                <span className="text-cyan-400/90 font-medium truncate shrink-0 group-hover:text-cyan-300">
                  {field.key}:
                </span>

                <div className="flex items-center gap-1.5 overflow-hidden justify-end">
                  {/* Inline Color Swatch */}
                  {isHexColor && (
                    <span
                      className="w-3.5 h-3.5 rounded-sm border border-black/40 inline-block shrink-0 shadow-sm"
                      style={{ backgroundColor: String(field.value).trim() }}
                      title={`Color: ${field.value}`}
                    />
                  )}

                  {field.type === 'object' ? (
                    <span className="text-slate-400 text-[11px] bg-slate-800/80 px-1.5 py-0.5 rounded group-hover:border group-hover:border-cyan-500/40">
                      {`{ ${field.childCount ?? 0} keys }`}
                    </span>
                  ) : field.type === 'array' ? (
                    <span className="text-slate-400 text-[11px] bg-slate-800/80 px-1.5 py-0.5 rounded group-hover:border group-hover:border-cyan-500/40">
                      {`[ ${field.childCount ?? 0} items ]`}
                    </span>
                  ) : (
                    <span
                      className={`truncate ${
                        field.type === 'number'
                          ? 'text-amber-300'
                          : field.type === 'boolean'
                          ? 'text-purple-300'
                          : field.type === 'null'
                          ? 'text-rose-300 italic'
                          : isHexColor
                          ? 'text-slate-200 font-semibold'
                          : 'text-emerald-300'
                      }`}
                    >
                      {String(field.value)}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
});

NodeCard.displayName = 'NodeCard';
