import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  ReactFlow,
  useNodesState,
  useEdgesState,
  useReactFlow,
  Node,
  Edge,
  Background,
  BackgroundVariant,
  ConnectionLineType,
} from '@xyflow/react';
import { toPng } from 'html-to-image';
import { NodeCard, NodeCardData, FieldItem } from './NodeCard';
import { BottomBar, PreferencesState } from './BottomBar';
import { DetailsDrawer } from './DetailsDrawer';
import { RulerOverlay } from './RulerOverlay';
import { LayoutDirection, getLayoutedElements } from '../lib/layoutEngine';
import { parseJsonToGraph } from '../lib/jsonToNodes';
import {
  ProjectData,
  CategorizedFileItem,
  fetchFileContent,
} from '../lib/apiClient';
import {
  FileJson,
  Code2,
  FileCode,
  Table as TableIcon,
  Search,
  Folder,
  Layers,
  Sparkles,
} from 'lucide-react';

interface JsonVisualizerProps {
  project: ProjectData | null;
  onOpenInDiagramStudio?: (rel: string) => void;
}

type CategoryType = 'json' | 'typescript' | 'html_css' | 'python';
type ViewMode = 'graph' | 'table' | 'code';

const nodeTypes = {
  jsonNode: NodeCard,
};

export const JsonVisualizer: React.FC<JsonVisualizerProps> = ({ project, onOpenInDiagramStudio }) => {
  const [activeCategory, setActiveCategory] = useState<CategoryType>('json');
  const [selectedFile, setSelectedFile] = useState<CategorizedFileItem | null>(null);
  const [fileContent, setFileContent] = useState<string>('');
  const [viewMode, setViewMode] = useState<ViewMode>('graph');
  const [searchQuery, setSearchQuery] = useState('');

  const [direction, setDirection] = useState<LayoutDirection>('LR');
  const [collapsedIds, setCollapsedIds] = useState<Set<string>>(new Set());
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [selectedField, setSelectedField] = useState<{ nodeId: string; field: FieldItem } | null>(null);
  const [searchResults, setSearchResults] = useState<string[]>([]);
  const [searchIndex, setSearchIndex] = useState<number>(0);
  const [jsonValid, setJsonValid] = useState(true);

  const [preferences, setPreferences] = useState<PreferencesState>({
    theme: 'obsidian',
    isLightMode: false,
    zoomOnScroll: true,
    showRulers: false,
    showMiniMap: true,
    showGreenUses: true,
    showOrangeUsedBy: true,
    showHierarchyLinks: true,
    showExternalPackages: true,
    connectionCurve: 'smoothstep',
  });

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const flowWrapperRef = useRef<HTMLDivElement>(null);
  const { fitView, zoomIn, zoomOut, setCenter } = useReactFlow();

  const isInitialLoadRef = useRef<boolean>(true);
  const positionCacheRef = useRef<Map<string, { x: number; y: number }>>(new Map());

  // Reset layout cache when file changes
  useEffect(() => {
    isInitialLoadRef.current = true;
    positionCacheRef.current.clear();
  }, [selectedFile]);

  // Get categorized files list
  const categoryFiles = project?.categoryFiles || {
    json: project?.jsonFiles || [],
    typescript: [],
    html_css: [],
    python: [],
    markdown: [],
  };

  const currentFilesList: CategorizedFileItem[] = categoryFiles[activeCategory] || [];

  // Group files by folder
  const groupedFiles = React.useMemo(() => {
    const map = new Map<string, CategorizedFileItem[]>();
    currentFilesList.forEach((file) => {
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        if (!file.name.toLowerCase().includes(q) && !file.rel.toLowerCase().includes(q)) {
          return;
        }
      }
      const folder = file.folder || 'Root';
      if (!map.has(folder)) map.set(folder, []);
      map.get(folder)!.push(file);
    });
    return map;
  }, [currentFilesList, searchQuery]);

  // Auto-select first JSON file if none selected
  useEffect(() => {
    if (!selectedFile && currentFilesList.length > 0) {
      handleSelectFile(currentFilesList[0]);
    }
  }, [currentFilesList, selectedFile]);

  const handleSelectFile = async (file: CategorizedFileItem) => {
    setSelectedFile(file);
    try {
      const content = await fetchFileContent(file.path);
      setFileContent(content);
    } catch {
      setFileContent('// Could not read file content');
    }
  };

  const handleToggleCollapse = useCallback((nodeId: string) => {
    setCollapsedIds((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) next.delete(nodeId);
      else next.add(nodeId);
      return next;
    });
  }, []);

  const handleCollapseAll = useCallback(() => {
    setCollapsedIds((prev) => {
      if (prev.size > 0) return new Set();
      const allCollapsible = new Set<string>();
      nodes.forEach((n) => {
        if ((n.data as NodeCardData)?.hasChildren) allCollapsible.add(n.id);
      });
      return allCollapsible;
    });
  }, [nodes]);

  // Parse JSON and build graph when fileContent or layout changes
  useEffect(() => {
    try {
      const parsed = JSON.parse(fileContent);
      const { nodes: rawNodes, edges: rawEdges } = parseJsonToGraph(parsed, collapsedIds);
      const withHandler = rawNodes.map((n) => ({
        ...n,
        data: {
          ...n.data,
          onToggleCollapse: handleToggleCollapse,
          onSelectField: (nodeId: string, field: FieldItem) => {
            const foundNode = rawNodes.find((x) => x.id === nodeId) || n;
            setSelectedNode(foundNode);
            setSelectedField({ nodeId, field });
          },
        },
      }));
      const layouted = getLayoutedElements(withHandler, rawEdges, {
        direction,
        positionCache: positionCacheRef.current,
        isFullRelayout: isInitialLoadRef.current,
      });
      setNodes(layouted.nodes);
      setEdges(layouted.edges);
      setJsonValid(true);

      if (isInitialLoadRef.current) {
        isInitialLoadRef.current = false;
        setTimeout(() => fitView({ padding: 0.2, duration: 400 }), 60);
      }
    } catch {
      setJsonValid(false);
      // If it's not JSON (e.g. TS/Python), default to code view
      if (activeCategory !== 'json') {
        setViewMode('code');
      }
    }
  }, [fileContent, direction, collapsedIds, handleToggleCollapse, fitView, setNodes, setEdges, activeCategory]);

  const handleRotateLayout = useCallback(() => {
    const cycle: Record<LayoutDirection, LayoutDirection> = { LR: 'TB', TB: 'RL', RL: 'BT', BT: 'LR' };
    isInitialLoadRef.current = true;
    setDirection((prev) => cycle[prev]);
    setTimeout(() => fitView({ padding: 0.2, duration: 400 }), 100);
  }, [fitView]);

  const handleCenterFirstItem = useCallback(() => {
    if (nodes.length > 0) {
      const root = nodes.find((n) => (n.data as NodeCardData)?.isRoot) || nodes[0];
      setCenter(root.position.x + 120, root.position.y + 40, { zoom: 1.2, duration: 500 });
    }
  }, [nodes, setCenter]);

  const handleSearch = useCallback((query: string) => {
    const q = query.trim().toLowerCase();
    if (!q) {
      setSearchResults([]);
      setSearchIndex(0);
      return;
    }
    const matches: string[] = [];
    nodes.forEach((n) => {
      const d = n.data as NodeCardData;
      const titleMatch = (d.title || '').toLowerCase().includes(q);
      const fieldMatch = (d.fields || []).some(
        (f) => f.key.toLowerCase().includes(q) || String(f.value || '').toLowerCase().includes(q)
      );
      if (titleMatch || fieldMatch) matches.push(n.id);
    });
    setSearchResults(matches);
    setSearchIndex(0);
    if (matches.length > 0) {
      const matchNode = nodes.find((n) => n.id === matches[0]);
      if (matchNode) setCenter(matchNode.position.x + 120, matchNode.position.y + 40, { zoom: 1.1, duration: 400 });
    }
  }, [nodes, setCenter]);

  const handleExport = useCallback(() => {
    if (!flowWrapperRef.current) return;
    toPng(flowWrapperRef.current, {
      backgroundColor: preferences.isLightMode ? '#f8fafc' : '#0b0f17',
      cacheBust: true,
    }).then((dataUrl) => {
      const link = document.createElement('a');
      link.download = `${selectedFile?.name || 'json_model'}_${Date.now()}.png`;
      link.href = dataUrl;
      link.click();
    });
  }, [preferences.isLightMode, selectedFile]);

  // Flatten JSON for Table view
  const tableRows = React.useMemo(() => {
    try {
      const parsed = JSON.parse(fileContent);
      const rows: { key: string; value: string; type: string }[] = [];
      const flatten = (obj: any, prefix = '') => {
        if (typeof obj === 'object' && obj !== null) {
          Object.entries(obj).forEach(([k, v]) => {
            const fullKey = prefix ? `${prefix}.${k}` : k;
            if (typeof v === 'object' && v !== null) {
              flatten(v, fullKey);
            } else {
              rows.push({ key: fullKey, value: String(v), type: typeof v });
            }
          });
        } else {
          rows.push({ key: prefix || 'value', value: String(obj), type: typeof obj });
        }
      };
      flatten(parsed);
      return rows;
    } catch {
      return [];
    }
  }, [fileContent]);

  return (
    <div className="w-full h-full flex overflow-hidden bg-[#0b0f17] text-slate-200 select-none">
      {/* Left Sidebar: Scanned Project Files Categorized by Folder */}
      <aside className="w-72 h-full bg-[#111622] border-r border-[#242d3f] flex flex-col shrink-0">
        {/* Category Selector Tabs */}
        <div className="grid grid-cols-4 border-b border-[#242d3f] bg-[#0d121c] p-1 gap-1 text-[11px] font-mono">
          <button
            onClick={() => setActiveCategory('json')}
            className={`py-1.5 rounded flex items-center justify-center gap-1 font-semibold ${
              activeCategory === 'json'
                ? 'bg-cyan-950 text-cyan-300 border border-cyan-800'
                : 'text-slate-400 hover:text-slate-200'
            }`}
            title="All JSON Files"
          >
            <FileJson className="w-3.5 h-3.5" />
            <span>JSON</span>
          </button>

          <button
            onClick={() => setActiveCategory('typescript')}
            className={`py-1.5 rounded flex items-center justify-center gap-1 font-semibold ${
              activeCategory === 'typescript'
                ? 'bg-cyan-950 text-cyan-300 border border-cyan-800'
                : 'text-slate-400 hover:text-slate-200'
            }`}
            title="TypeScript / JavaScript"
          >
            <Code2 className="w-3.5 h-3.5" />
            <span>TS/JS</span>
          </button>

          <button
            onClick={() => setActiveCategory('html_css')}
            className={`py-1.5 rounded flex items-center justify-center gap-1 font-semibold ${
              activeCategory === 'html_css'
                ? 'bg-cyan-950 text-cyan-300 border border-cyan-800'
                : 'text-slate-400 hover:text-slate-200'
            }`}
            title="HTML & CSS Stylesheets"
          >
            <FileCode className="w-3.5 h-3.5" />
            <span>UI</span>
          </button>

          <button
            onClick={() => setActiveCategory('python')}
            className={`py-1.5 rounded flex items-center justify-center gap-1 font-semibold ${
              activeCategory === 'python'
                ? 'bg-cyan-950 text-cyan-300 border border-cyan-800'
                : 'text-slate-400 hover:text-slate-200'
            }`}
            title="Python Scripts"
          >
            <Layers className="w-3.5 h-3.5" />
            <span>Py</span>
          </button>
        </div>

        {/* Search Files Input */}
        <div className="p-2 border-b border-[#242d3f] bg-[#0f141f]">
          <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-[#0b0f17] border border-[#242d3f] text-xs font-mono">
            <Search className="w-3.5 h-3.5 text-slate-500 shrink-0" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={`Filter ${activeCategory} files…`}
              className="w-full bg-transparent text-slate-200 placeholder-slate-500 outline-none text-xs"
            />
          </div>
        </div>

        {/* Grouped Files List */}
        <div className="flex-1 overflow-y-auto p-2 space-y-3 text-xs font-mono">
          {Array.from(groupedFiles.entries()).map(([folder, files]) => (
            <div key={folder} className="space-y-1">
              <div className="flex items-center gap-1.5 px-1 text-[10px] uppercase font-bold text-slate-400 tracking-wider">
                <Folder className="w-3 h-3 text-cyan-400" />
                <span className="truncate">{folder}</span>
                <span className="text-slate-600">({files.length})</span>
              </div>

              <div className="space-y-0.5 pl-1">
                {files.map((f) => (
                  <div
                    key={f.path}
                    onClick={() => handleSelectFile(f)}
                    className={`flex items-center gap-2 p-1.5 rounded-md cursor-pointer transition-colors ${
                      selectedFile?.path === f.path
                        ? 'bg-cyan-950/80 border border-cyan-800 text-cyan-300 font-semibold'
                        : 'hover:bg-[#182030] text-slate-300'
                    }`}
                  >
                    <FileJson className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                    <span className="truncate" title={f.rel}>{f.name}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}

          {groupedFiles.size === 0 && (
            <div className="text-center py-8 text-slate-500 text-xs font-mono">
              No {activeCategory} files found in scanned codebase.
            </div>
          )}
        </div>
      </aside>

      {/* Main Workspace for Selected File */}
      <div className="flex-1 flex flex-col h-full overflow-hidden relative">
        {/* Top Control Bar for View Modes */}
        <div className="h-10 border-b border-[#242d3f] bg-[#0e141f] px-3 flex items-center justify-between text-xs font-mono shrink-0">
          <div className="flex items-center gap-2">
            <span className="text-slate-400">File:</span>
            <span className="font-semibold text-cyan-300 px-2 py-0.5 rounded bg-[#141a27] border border-[#242d3f]">
              {selectedFile?.rel || 'No file selected'}
            </span>
          </div>

          <div className="flex items-center gap-1">
            {selectedFile && onOpenInDiagramStudio && (
              <button
                onClick={() => onOpenInDiagramStudio(selectedFile.rel)}
                className="flex items-center gap-1.5 px-3 py-1 rounded bg-cyan-600 hover:bg-cyan-500 text-white font-semibold text-xs transition-colors shadow-sm mr-2"
                title="Generate Architecture / Schema Diagram for this file in Diagram Studio"
              >
                <Sparkles className="w-3.5 h-3.5 fill-current" />
                <span>Generate Architecture Diagram</span>
              </button>
            )}

            {jsonValid && (
              <>
                <button
                  onClick={() => setViewMode('graph')}
                  className={`flex items-center gap-1 px-2.5 py-1 rounded transition-colors ${
                    viewMode === 'graph'
                      ? 'bg-cyan-950 text-cyan-300 border border-cyan-800'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Node Graph</span>
                </button>

                <button
                  onClick={() => setViewMode('table')}
                  className={`flex items-center gap-1 px-2.5 py-1 rounded transition-colors ${
                    viewMode === 'table'
                      ? 'bg-cyan-950 text-cyan-300 border border-cyan-800'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <TableIcon className="w-3.5 h-3.5" />
                  <span>Table View</span>
                </button>
              </>
            )}

            <button
              onClick={() => setViewMode('code')}
              className={`flex items-center gap-1 px-2.5 py-1 rounded transition-colors ${
                viewMode === 'code'
                  ? 'bg-cyan-950 text-cyan-300 border border-cyan-800'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Code2 className="w-3.5 h-3.5" />
              <span>Raw Code</span>
            </button>
          </div>
        </div>

        {/* View Mode 1: Node Graph */}
        {viewMode === 'graph' && jsonValid && (
          <div ref={flowWrapperRef} className="flex-1 w-full h-full relative dot-grid-bg">
            {preferences.showRulers && <RulerOverlay />}

            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onNodeClick={(_, node) => {
                setSelectedNode(node);
                setSelectedField(null);
              }}
              nodeTypes={nodeTypes}
              connectionLineType={ConnectionLineType.SmoothStep}
              fitView
              minZoom={0.08}
              maxZoom={3.5}
              zoomOnScroll={preferences.zoomOnScroll}
              panOnScroll={!preferences.zoomOnScroll}
              proOptions={{ hideAttribution: true }}
            >
              <Background
                variant={BackgroundVariant.Dots}
                gap={24}
                size={1.2}
                color={preferences.isLightMode ? '#cbd5e1' : '#334155'}
              />
            </ReactFlow>

            <BottomBar
              onFitView={() => fitView({ padding: 0.2, duration: 400 })}
              onZoomIn={() => zoomIn({ duration: 300 })}
              onZoomOut={() => zoomOut({ duration: 300 })}
              onCollapseAll={handleCollapseAll}
              onRotateLayout={handleRotateLayout}
              currentDirection={direction}
              onCenterFirstItem={handleCenterFirstItem}
              onExport={handleExport}
              preferences={preferences}
              onUpdatePreferences={(p) => setPreferences((prev) => ({ ...prev, ...p }))}
              onSearch={handleSearch}
              searchResultCount={searchResults.length}
              currentSearchIndex={searchIndex}
              onNextSearchResult={() => {}}
              onPrevSearchResult={() => {}}
            />

            <DetailsDrawer
              selectedNode={selectedNode}
              selectedField={selectedField}
              onClose={() => {
                setSelectedNode(null);
                setSelectedField(null);
              }}
              onClearField={() => setSelectedField(null)}
            />
          </div>
        )}

        {/* View Mode 2: Table View */}
        {viewMode === 'table' && (
          <div className="flex-1 p-4 overflow-y-auto">
            <div className="rounded-xl border border-[#242d3f] overflow-hidden bg-[#111622]">
              <table className="w-full text-xs font-mono text-left">
                <thead className="bg-[#171e2c] border-b border-[#242d3f] text-slate-400 uppercase text-[10px]">
                  <tr>
                    <th className="px-4 py-2.5">Key / Property</th>
                    <th className="px-4 py-2.5">Type</th>
                    <th className="px-4 py-2.5">Value</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1e2637]">
                  {tableRows.map((r, i) => (
                    <tr key={i} className="hover:bg-[#172030] transition-colors">
                      <td className="px-4 py-2 text-cyan-300 font-medium">{r.key}</td>
                      <td className="px-4 py-2">
                        <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 text-[10px]">
                          {r.type}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-slate-200 truncate max-w-md">{r.value}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* View Mode 3: Raw Code View */}
        {viewMode === 'code' && (
          <div className="flex-1 p-4 overflow-hidden flex flex-col">
            <textarea
              value={fileContent}
              onChange={(e) => setFileContent(e.target.value)}
              spellCheck={false}
              className="flex-1 w-full p-4 bg-[#090d14] border border-[#242d3f] rounded-xl text-slate-200 font-mono text-xs leading-relaxed outline-none resize-none overflow-auto selection:bg-cyan-900/60"
            />
          </div>
        )}
      </div>
    </div>
  );
};
