import React, { useState } from 'react';
import {
  X,
  BarChart3,
  Table as TableIcon,
  FileJson,
  Info,
  Copy,
  Check,
  Tag,
  Hash,
  Layers,
} from 'lucide-react';
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  createColumnHelper,
} from '@tanstack/react-table';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
} from 'recharts';
import { FieldItem, NodeCardData } from './NodeCard';
import { Node } from '@xyflow/react';

interface DetailsDrawerProps {
  selectedNode: Node | null;
  selectedField?: { nodeId: string; field: FieldItem } | null;
  onClose: () => void;
  onClearField?: () => void;
}

const columnHelper = createColumnHelper<FieldItem>();

const columns = [
  columnHelper.accessor('key', {
    header: 'Key / Field',
    cell: (info) => (
      <span className="font-mono text-cyan-300 font-medium">
        {info.getValue()}
      </span>
    ),
  }),
  columnHelper.accessor('type', {
    header: 'Type',
    cell: (info) => (
      <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
        {info.getValue()}
      </span>
    ),
  }),
  columnHelper.accessor('value', {
    header: 'Value',
    cell: (info) => {
      const row = info.row.original;
      if (row.type === 'object') {
        return <span className="text-slate-400">{`{ ${row.childCount || 0} keys }`}</span>;
      }
      if (row.type === 'array') {
        return <span className="text-slate-400">{`[ ${row.childCount || 0} items ]`}</span>;
      }
      return (
        <span className="font-mono text-emerald-300">
          {String(info.getValue() ?? 'null')}
        </span>
      );
    },
  }),
];

export const DetailsDrawer: React.FC<DetailsDrawerProps> = ({
  selectedNode,
  selectedField,
  onClose,
  onClearField,
}) => {
  const [activeTab, setActiveTab] = useState<'table' | 'metrics' | 'json'>('table');
  const [copiedKey, setCopiedKey] = useState(false);
  const [copiedVal, setCopiedVal] = useState(false);

  if (!selectedNode && !selectedField) return null;

  const nodeData = (selectedNode?.data as NodeCardData) || {};
  const fields = nodeData.fields || [];

  // Prepare numeric data for Recharts
  const numericMetrics = fields
    .filter((f) => {
      if (typeof f.value === 'number') return true;
      if (typeof f.value === 'string') {
        const num = parseFloat(f.value);
        return !isNaN(num) && isFinite(num);
      }
      return false;
    })
    .map((f) => ({
      name: f.key,
      value: typeof f.value === 'number' ? f.value : parseFloat(f.value as string),
    }));

  const table = useReactTable({
    data: fields,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  const chartColors = ['#38bdf8', '#4ade80', '#facc15', '#f87171', '#c084fc', '#fb923c'];

  const handleCopy = (text: string, isKey: boolean) => {
    navigator.clipboard.writeText(text);
    if (isKey) {
      setCopiedKey(true);
      setTimeout(() => setCopiedKey(false), 2000);
    } else {
      setCopiedVal(true);
      setTimeout(() => setCopiedVal(false), 2000);
    }
  };

  return (
    <div className="fixed top-14 right-4 bottom-20 w-96 bg-[#141923]/95 border border-[#2a3449] rounded-2xl shadow-2xl backdrop-blur-xl z-20 flex flex-col overflow-hidden animate-in slide-in-from-right-4 duration-200">
      {/* Drawer Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#242d3f] bg-[#0f141d]/80">
        <div className="flex items-center gap-2 overflow-hidden">
          <Info className="w-4 h-4 text-cyan-400 shrink-0" />
          <h3 className="font-mono text-sm font-semibold text-slate-100 truncate">
            {nodeData.title || selectedNode?.id || 'Node Details'}
          </h3>
        </div>

        <button
          onClick={onClose}
          className="p-1 hover:bg-slate-800 text-slate-400 hover:text-slate-200 rounded-lg transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Selected Field Inspector Banner (if user clicked a specific field) */}
      {selectedField && (
        <div className="p-3 bg-[#0b0f17] border-b border-[#242d3f] space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold text-cyan-400 uppercase tracking-wider flex items-center gap-1">
              <Tag className="w-3 h-3" />
              <span>Selected Property:</span>
            </span>
            {onClearField && (
              <button
                onClick={onClearField}
                className="text-[10px] text-slate-400 hover:text-slate-200 underline"
              >
                Clear
              </button>
            )}
          </div>

          <div className="p-2.5 rounded-lg bg-[#141a27] border border-[#242d3f] space-y-1.5 text-xs font-mono">
            <div className="flex items-center justify-between gap-2">
              <span className="text-slate-400 text-[11px]">Key:</span>
              <div className="flex items-center gap-1.5">
                <span className="font-semibold text-cyan-300">{selectedField.field.key}</span>
                <button
                  onClick={() => handleCopy(selectedField.field.key, true)}
                  className="p-1 hover:bg-slate-700 rounded text-slate-400 hover:text-cyan-300"
                  title="Copy Key"
                >
                  {copiedKey ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between gap-2">
              <span className="text-slate-400 text-[11px]">Type:</span>
              <span className="px-1.5 py-0.5 rounded bg-slate-800 text-purple-300 text-[10px] uppercase font-bold">
                {selectedField.field.type}
              </span>
            </div>

            <div className="flex items-center justify-between gap-2">
              <span className="text-slate-400 text-[11px]">Value:</span>
              <div className="flex items-center gap-1.5 max-w-[200px] overflow-hidden">
                <span className="text-emerald-300 truncate">
                  {selectedField.field.type === 'object'
                    ? `{ ${selectedField.field.childCount || 0} keys }`
                    : selectedField.field.type === 'array'
                    ? `[ ${selectedField.field.childCount || 0} items ]`
                    : String(selectedField.field.value)}
                </span>
                <button
                  onClick={() => handleCopy(String(selectedField.field.value ?? ''), false)}
                  className="p-1 hover:bg-slate-700 rounded text-slate-400 hover:text-emerald-300 shrink-0"
                  title="Copy Value"
                >
                  {copiedVal ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center border-b border-[#242d3f] bg-[#111622] px-3 gap-1">
        <button
          onClick={() => setActiveTab('table')}
          className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 transition-colors ${
            activeTab === 'table'
              ? 'border-cyan-400 text-cyan-300'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <TableIcon className="w-3.5 h-3.5" />
          <span>Fields Table</span>
        </button>

        <button
          onClick={() => setActiveTab('metrics')}
          className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 transition-colors ${
            activeTab === 'metrics'
              ? 'border-cyan-400 text-cyan-300'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <BarChart3 className="w-3.5 h-3.5" />
          <span>Metrics ({numericMetrics.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('json')}
          className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 transition-colors ${
            activeTab === 'json'
              ? 'border-cyan-400 text-cyan-300'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <FileJson className="w-3.5 h-3.5" />
          <span>Raw Data</span>
        </button>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {activeTab === 'table' && (
          <div className="rounded-xl border border-[#2a3449] overflow-hidden">
            <table className="w-full text-xs text-left">
              <thead className="bg-[#1a2232] text-slate-400 uppercase text-[10px] tracking-wider border-b border-[#2a3449]">
                {table.getHeaderGroups().map((headerGroup) => (
                  <tr key={headerGroup.id}>
                    {headerGroup.headers.map((header) => (
                      <th key={header.id} className="px-3 py-2 font-semibold">
                        {flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody className="divide-y divide-[#222b3d] bg-[#141924]">
                {table.getRowModel().rows.map((row) => (
                  <tr key={row.id} className="hover:bg-[#1a2334] transition-colors">
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id} className="px-3 py-2.5">
                        {flexRender(
                          cell.column.columnDef.cell,
                          cell.getContext()
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === 'metrics' && (
          <div className="space-y-4">
            {numericMetrics.length > 0 ? (
              <div>
                <div className="text-xs font-semibold text-slate-300 mb-2">
                  Numeric Metrics Visualization
                </div>
                <div className="h-56 bg-[#161c28] border border-[#2a3449] rounded-xl p-3">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={numericMetrics}>
                      <XAxis dataKey="name" stroke="#64748b" fontSize={10} />
                      <YAxis stroke="#64748b" fontSize={10} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#0f172a',
                          border: '1px solid #334155',
                          borderRadius: '8px',
                          fontSize: '12px',
                        }}
                      />
                      <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                        {numericMetrics.map((_, index) => (
                          <Cell
                            key={`cell-${index}`}
                            fill={chartColors[index % chartColors.length]}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            ) : (
              <div className="text-center py-12 text-slate-500 text-xs">
                No numeric values found in this node to display charts.
              </div>
            )}
          </div>
        )}

        {activeTab === 'json' && (
          <pre className="p-3 bg-[#0b0f17] border border-[#242d3f] rounded-xl text-xs font-mono text-cyan-300/90 overflow-x-auto select-text">
            {JSON.stringify(nodeData, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
};
