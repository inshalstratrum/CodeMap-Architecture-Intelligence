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
  NodeChange,
  MarkerType,
  Handle,
  Position,
  NodeProps,
  MiniMap,
} from '@xyflow/react';
import { toPng } from 'html-to-image';
import { CodebaseNodeCard, CodebaseNodeData } from './CodebaseNodeCard';
import { BottomBar, PreferencesState } from './BottomBar';
import { RulerOverlay } from './RulerOverlay';
import { LayoutDirection, applyStaticTreeLayout, globalNodePositionsCache } from '../lib/layoutEngine';
import { ProjectData, ProjectNode } from '../lib/apiClient';
import { Minus, Plus, RotateCcw, ChevronsRight, ChevronsLeft, Network } from 'lucide-react';

interface ArchitectureMapProps {
  project: ProjectData | null;
  selectedRel: string | null;
  onSelectNode: (node: ProjectNode | null) => void;
  showFiles: boolean;
}

// Lightweight badge node for third-party external libraries/packages
const ExternalPackageCard: React.FC<NodeProps> = ({ data }) => {
  return (
    <div className="px-2.5 py-1.5 rounded-lg border border-purple-500/50 bg-[#1e102f]/95 text-purple-200 shadow-lg shadow-purple-950/60 flex items-center gap-1.5 font-mono text-xs select-none">
      <Handle type="target" position={Position.Left} className="!w-2 !h-2 !bg-purple-400 !border-2 !border-[#0b0f17]" />
      <span className="px-1 py-0.2 rounded bg-purple-900/80 text-purple-300 text-[9px] uppercase font-bold tracking-wider">pkg</span>
      <span className="font-semibold text-purple-100">{data.name as string}</span>
    </div>
  );
};

const nodeTypes = {
  codebaseNode: CodebaseNodeCard,
  externalPackageNode: ExternalPackageCard,
};

export const ArchitectureMap: React.FC<ArchitectureMapProps> = ({
  project,
  selectedRel,
  onSelectNode,
  showFiles,
}) => {
  const [direction, setDirection] = useState<LayoutDirection>('LR');
  const [expandedFolderRels, setExpandedFolderRels] = useState<Set<string>>(new Set(['']));
  const [preferences, setPreferences] = useState<PreferencesState>({
    theme: 'obsidian',
    isLightMode: false,
    zoomOnScroll: true,
    showRulers: false,
    showMiniMap: false,
    showGreenUses: true,
    showOrangeUsedBy: true,
    showHierarchyLinks: true,
    showExternalPackages: true,
    connectionCurve: 'smoothstep',
  });

  // Tool mode: pointer (V) or hand (H or Spacebar)
  const [activeTool, setActiveTool] = useState<'pointer' | 'hand'>('pointer');
  const [isSpacePressed, setIsSpacePressed] = useState<boolean>(false);
  const isPanMode = activeTool === 'hand' || isSpacePressed;

  // Toggle to show all dependency links vs focus on selected node
  const [showAllLinks, setShowAllLinks] = useState<boolean>(false);

  const [searchResults, setSearchResults] = useState<string[]>([]);
  const [searchIndex, setSearchIndex] = useState<number>(0);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const flowWrapperRef = useRef<HTMLDivElement>(null);
  const { fitView, zoomIn, zoomOut, setCenter } = useReactFlow();

  // Persistent position cache to guarantee existing nodes never shift on expand/collapse or tab switch
  const nodePositionsRef = useRef<Map<string, { x: number; y: number }>>(globalNodePositionsCache);
  const isInitialLoadRef = useRef<boolean>(true);
  const fullRelayoutRequestedRef = useRef<boolean>(false);
  const lastProjectRootRef = useRef<string | null>(null);

  // Keyboard listeners for Spacebar (temporary hand tool) and H/V shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const targetTag = (e.target as HTMLElement)?.tagName?.toUpperCase();
      if (targetTag === 'INPUT' || targetTag === 'TEXTAREA') return;

      if (e.code === 'Space' && !e.repeat) {
        e.preventDefault();
        setIsSpacePressed(true);
      }
      if (e.key === 'h' || e.key === 'H') {
        setActiveTool('hand');
      }
      if (e.key === 'v' || e.key === 'V') {
        setActiveTool('pointer');
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.code === 'Space') {
        setIsSpacePressed(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, []);

  // Toggle expand for a specific folder
  const handleToggleExpand = useCallback((nodeId: string) => {
    setExpandedFolderRels((prev) => {
      const next = new Set(prev);
      const targetRel = nodeId === '__root__' ? '' : nodeId;
      if (next.has(targetRel)) next.delete(targetRel);
      else next.add(targetRel);
      return next;
    });
  }, []);

  // Expand all folders
  const handleExpandAll = useCallback(() => {
    if (!project?.nodes) return;
    const allDirs = new Set<string>(['']);
    project.nodes.forEach((n) => {
      if (n.isDir) allDirs.add(n.rel);
    });
    fullRelayoutRequestedRef.current = true;
    setExpandedFolderRels(allDirs);
    setTimeout(() => {
      fitView({ padding: 0.2, duration: 400 });
    }, 100);
  }, [project, fitView]);

  // Collapse all folders to root level
  const handleCollapseAll = useCallback(() => {
    fullRelayoutRequestedRef.current = true;
    setExpandedFolderRels(new Set(['']));
    setTimeout(() => {
      fitView({ padding: 0.2, duration: 400 });
    }, 100);
  }, [fitView]);

  const isAllCollapsed = expandedFolderRels.size <= 1;

  // Toggle between Expand All and Collapse All
  const handleToggleCollapseAll = useCallback(() => {
    if (expandedFolderRels.size <= 1) {
      handleExpandAll();
    } else {
      handleCollapseAll();
    }
  }, [expandedFolderRels, handleExpandAll, handleCollapseAll]);


  // Build strictly scoped nodes & hierarchy edges
  useEffect(() => {
    if (!project || !project.nodes) {
      setNodes([]);
      setEdges([]);
      return;
    }

    if (project.rootPath !== lastProjectRootRef.current) {
      lastProjectRootRef.current = project.rootPath;
      nodePositionsRef.current.clear();
      isInitialLoadRef.current = true;
    }

    const selectedItem = project.nodes.find((n) => n.rel === selectedRel);
    const usesSet = new Set(selectedItem?.imports || []);
    const usedBySet = new Set(selectedItem?.importedBy || []);

    const visibleNodes: Node[] = [];
    const visibleEdges: Edge[] = [];

    // Helper: is ancestor chain expanded?
    const isNodeVisible = (item: ProjectNode): boolean => {
      if (item.rel === '') return true;
      let curParent = item.parentRel;
      while (curParent !== undefined) {
        if (!expandedFolderRels.has(curParent)) {
          return false;
        }
        if (curParent === '') break;
        const parentNode = project.nodes.find((p) => p.rel === curParent);
        curParent = parentNode ? parentNode.parentRel : '';
      }
      return true;
    };

    project.nodes.forEach((item) => {
      if (!showFiles && !item.isDir && item.rel !== '') return;

      if (isNodeVisible(item)) {
        const isSelected = item.rel === selectedRel;
        const isUses = usesSet.has(item.rel);
        const isUsedBy = usedBySet.has(item.rel);

        visibleNodes.push({
          id: item.rel || '__root__',
          type: 'codebaseNode',
          position: { x: 0, y: 0 },
          selected: isSelected,
          data: {
            node: item,
            isExpanded: expandedFolderRels.has(item.rel),
            onToggleExpand: handleToggleExpand,
            isDependencyOfSelected: isUses,
            isDependentOfSelected: isUsedBy,
          } as CodebaseNodeData,
        });

        // Add hierarchy edge from immediate direct parent only
        if (item.rel !== '' && preferences.showHierarchyLinks) {
          const parentId = item.parentRel || '__root__';
          visibleEdges.push({
            id: `hierarchy_${parentId}_${item.rel}`,
            source: parentId,
            target: item.rel,
            type: preferences.connectionCurve,
            style: { stroke: '#2e3b52', strokeWidth: 1.5 },
          });
        }
      }
    });

    const visibleIdSet = new Set(visibleNodes.map((vn) => vn.id));

    // Resolve nearest visible representative node (ancestor if target is inside a collapsed folder)
    const getVisibleRep = (targetRel: string): string | null => {
      let cur: string | undefined = targetRel;
      while (cur !== undefined) {
        const id = cur || '__root__';
        if (visibleIdSet.has(id)) {
          return id;
        }
        if (cur === '') break;
        const parentNode = project.nodes.find((p) => p.rel === cur);
        cur = parentNode ? parentNode.parentRel : '';
      }
      return null;
    };

    // 1. If "Show All Links" toggle is ON, render global dependency web across visible nodes
    if (showAllLinks) {
      const seenGlobalEdges = new Set<string>();
      project.nodes.forEach((n) => {
        const sourceRep = getVisibleRep(n.rel);
        if (!sourceRep) return;

        (n.imports || []).forEach((impRel) => {
          const targetRep = getVisibleRep(impRel);
          if (targetRep && targetRep !== sourceRep) {
            const edgeId = `global_dep_${sourceRep}_${targetRep}`;
            if (!seenGlobalEdges.has(edgeId)) {
              seenGlobalEdges.add(edgeId);
              visibleEdges.push({
                id: edgeId,
                source: sourceRep,
                target: targetRep,
                label: 'uses',
                animated: true,
                style: {
                  stroke: '#22c55e',
                  strokeWidth: 2.2,
                  filter: 'drop-shadow(0 0 5px rgba(34, 197, 94, 0.7))',
                },
                markerEnd: {
                  type: MarkerType.ArrowClosed,
                  color: '#22c55e',
                  width: 16,
                  height: 16,
                },
                zIndex: 900,
                labelStyle: { fill: '#86efac', fontSize: 10, fontWeight: 700, fontFamily: 'monospace' },
                labelBgStyle: { fill: '#052e16', fillOpacity: 0.95, stroke: '#22c55e', strokeWidth: 1.2, rx: 5, ry: 5 },
                labelBgPadding: [6, 3],
              });
            }
          }
        });
      });
    }

    // 2. High-priority selected item links (Internal Green & Orange + External Purple)
    if (selectedItem) {
      const selectedId = selectedItem.rel || '__root__';

      // Green links: this item uses (internal outbound)
      if (preferences.showGreenUses) {
        const seenUsesEdges = new Set<string>();
        (selectedItem.imports || []).forEach((impRel) => {
          const repTargetId = getVisibleRep(impRel);
          if (repTargetId && repTargetId !== selectedId) {
            const edgeId = `dep_uses_${selectedId}_${repTargetId}`;
            if (!seenUsesEdges.has(edgeId)) {
              seenUsesEdges.add(edgeId);
              visibleEdges.push({
                id: edgeId,
                source: selectedId,
                target: repTargetId,
                type: preferences.connectionCurve,
                label: 'uses',
                animated: true,
                style: {
                  stroke: '#22c55e',
                  strokeWidth: 3.2,
                  filter: 'drop-shadow(0 0 8px rgba(34, 197, 94, 0.9))',
                },
                markerEnd: {
                  type: MarkerType.ArrowClosed,
                  color: '#22c55e',
                  width: 20,
                  height: 20,
                },
                zIndex: 1000,
                labelStyle: { fill: '#86efac', fontSize: 11, fontWeight: 800, fontFamily: 'monospace' },
                labelBgStyle: { fill: '#052e16', fillOpacity: 0.95, stroke: '#22c55e', strokeWidth: 1.5, rx: 6, ry: 6 },
                labelBgPadding: [8, 4],
              });
            }
          }
        });
      }

      // Orange links: used by this item (internal inbound)
      if (preferences.showOrangeUsedBy) {
        const seenUsedByEdges = new Set<string>();
        (selectedItem.importedBy || []).forEach((byRel) => {
          const repSourceId = getVisibleRep(byRel);
          if (repSourceId && repSourceId !== selectedId) {
            const edgeId = `dep_usedby_${repSourceId}_${selectedId}`;
            if (!seenUsedByEdges.has(edgeId)) {
              seenUsedByEdges.add(edgeId);
              visibleEdges.push({
                id: edgeId,
                source: repSourceId,
                target: selectedId,
                type: preferences.connectionCurve,
                label: 'used by',
                animated: true,
                style: {
                  stroke: '#f97316',
                  strokeWidth: 3.2,
                  filter: 'drop-shadow(0 0 8px rgba(249, 115, 22, 0.9))',
                },
                markerEnd: {
                  type: MarkerType.ArrowClosed,
                  color: '#f97316',
                  width: 20,
                  height: 20,
                },
                zIndex: 1000,
                labelStyle: { fill: '#fdba74', fontSize: 11, fontWeight: 800, fontFamily: 'monospace' },
                labelBgStyle: { fill: '#431407', fillOpacity: 0.95, stroke: '#f97316', strokeWidth: 1.5, rx: 6, ry: 6 },
                labelBgPadding: [8, 4],
              });
            }
          }
        });
      }

      // Purple links: external third-party libraries (npm / pip packages)
      if (preferences.showExternalPackages && selectedItem.external && selectedItem.external.length > 0) {
        const keyPackages = selectedItem.external.slice(0, 6);
        keyPackages.forEach((pkg) => {
          const extNodeId = `ext_pkg_${selectedId}_${pkg}`;
          visibleNodes.push({
            id: extNodeId,
            type: 'externalPackageNode',
            position: { x: 0, y: 0 },
            data: { name: pkg },
            selectable: false,
          });

          visibleEdges.push({
            id: `ext_edge_${selectedId}_${pkg}`,
            source: selectedId,
            target: extNodeId,
            type: preferences.connectionCurve,
            label: 'imports pkg',
            animated: true,
            style: {
              stroke: '#a855f7',
              strokeWidth: 2.5,
              strokeDasharray: '5,5',
              filter: 'drop-shadow(0 0 6px rgba(168, 85, 247, 0.85))',
            },
            markerEnd: {
              type: MarkerType.ArrowClosed,
              color: '#a855f7',
              width: 18,
              height: 18,
            },
            zIndex: 1000,
            labelStyle: { fill: '#e9d5ff', fontSize: 10, fontWeight: 700, fontFamily: 'monospace' },
            labelBgStyle: { fill: '#2e1065', fillOpacity: 0.95, stroke: '#a855f7', strokeWidth: 1.2, rx: 5, ry: 5 },
            labelBgPadding: [6, 3],
          });
        });
      }
    }

    const isFull = isInitialLoadRef.current || fullRelayoutRequestedRef.current;
    fullRelayoutRequestedRef.current = false;

    const layouted = applyStaticTreeLayout(visibleNodes, visibleEdges, {
      direction,
      positionCache: nodePositionsRef.current,
      isFullRelayout: isFull,
    });

    setNodes(layouted.nodes);
    setEdges(layouted.edges);

    if (isInitialLoadRef.current) {
      isInitialLoadRef.current = false;
      setTimeout(() => {
        fitView({ padding: 0.2, duration: 400 });
      }, 80);
    }
  }, [project, selectedRel, showFiles, expandedFolderRels, direction, handleToggleExpand, fitView, setNodes, setEdges]);

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      const item = (node.data as CodebaseNodeData)?.node;
      onSelectNode(item || null);
    },
    [onSelectNode]
  );

  const handleRotateLayout = useCallback(() => {
    const cycle: Record<LayoutDirection, LayoutDirection> = { LR: 'TB', TB: 'RL', RL: 'BT', BT: 'LR' };
    fullRelayoutRequestedRef.current = true;
    setDirection((prev) => cycle[prev]);
    setTimeout(() => {
      fitView({ padding: 0.2, duration: 400 });
    }, 100);
  }, [fitView]);

  const handleNodeDragStop = useCallback((_: MouseEvent | TouchEvent, node: Node) => {
    nodePositionsRef.current.set(node.id, { x: node.position.x, y: node.position.y });
  }, []);

  const handleNodesChange = useCallback(
    (changes: NodeChange[]) => {
      changes.forEach((c) => {
        if (c.type === 'position' && c.position) {
          nodePositionsRef.current.set(c.id, c.position);
        }
      });
      onNodesChange(changes);
    },
    [onNodesChange]
  );


  const handleCenterFirstItem = useCallback(() => {
    if (nodes.length > 0) {
      const root = nodes.find((n) => n.id === '__root__' || n.id === '') || nodes[0];
      setCenter(root.position.x + 120, root.position.y + 40, { zoom: 1.1, duration: 500 });
    }
  }, [nodes, setCenter]);

  const handleSearch = useCallback(
    (query: string) => {
      const q = query.trim().toLowerCase();
      if (!q) {
        setSearchResults([]);
        setSearchIndex(0);
        return;
      }

      const matches = nodes
        .filter((n) => {
          const item = (n.data as CodebaseNodeData)?.node;
          return (item?.name || '').toLowerCase().includes(q) || (item?.rel || '').toLowerCase().includes(q);
        })
        .map((n) => n.id);

      setSearchResults(matches);
      setSearchIndex(0);

      if (matches.length > 0) {
        const matchNode = nodes.find((n) => n.id === matches[0]);
        if (matchNode) {
          setCenter(matchNode.position.x + 120, matchNode.position.y + 40, { zoom: 1.1, duration: 400 });
          const item = (matchNode.data as CodebaseNodeData)?.node;
          onSelectNode(item || null);
        }
      }
    },
    [nodes, setCenter, onSelectNode]
  );

  const handleNextSearchResult = useCallback(() => {
    if (searchResults.length === 0) return;
    const nextIdx = (searchIndex + 1) % searchResults.length;
    setSearchIndex(nextIdx);
    const targetId = searchResults[nextIdx];
    const matchNode = nodes.find((n) => n.id === targetId);
    if (matchNode) {
      setCenter(matchNode.position.x + 120, matchNode.position.y + 40, { zoom: 1.1, duration: 400 });
      const item = (matchNode.data as CodebaseNodeData)?.node;
      onSelectNode(item || null);
    }
  }, [searchResults, searchIndex, nodes, setCenter, onSelectNode]);

  const handlePrevSearchResult = useCallback(() => {
    if (searchResults.length === 0) return;
    const prevIdx = (searchIndex - 1 + searchResults.length) % searchResults.length;
    setSearchIndex(prevIdx);
    const targetId = searchResults[prevIdx];
    const matchNode = nodes.find((n) => n.id === targetId);
    if (matchNode) {
      setCenter(matchNode.position.x + 120, matchNode.position.y + 40, { zoom: 1.1, duration: 400 });
      const item = (matchNode.data as CodebaseNodeData)?.node;
      onSelectNode(item || null);
    }
  }, [searchResults, searchIndex, nodes, setCenter, onSelectNode]);

  const handleExport = useCallback(() => {
    if (!flowWrapperRef.current) return;
    toPng(flowWrapperRef.current, {
      backgroundColor: preferences.isLightMode ? '#f8fafc' : '#0b0f17',
      cacheBust: true,
    })
      .then((dataUrl) => {
        const link = document.createElement('a');
        link.download = `codemap_architecture_${Date.now()}.png`;
        link.href = dataUrl;
        link.click();
      })
      .catch((err) => console.error("Export error:", err));
  }, [preferences.isLightMode]);

  return (
    <div className={`w-full h-full flex flex-col relative overflow-hidden theme-${preferences.theme} ${preferences.isLightMode ? 'light' : ''}`}>
      {/* Top Mind Map Toolbar (Exact matching Tkinter App) */}
      <div className="h-10 bg-[#0e141f] border-b border-[#242d3f] px-3 flex items-center justify-between z-10 shrink-0 text-xs font-mono select-none">
        <div className="flex items-center gap-1.5">
          <button
            onClick={handleExpandAll}
            className="px-2.5 py-1 rounded bg-[#1a2232] hover:bg-[#232c3f] border border-[#2a3449] text-slate-200 hover:text-cyan-300 transition-colors flex items-center gap-1"
            title="Expand all folders"
          >
            <ChevronsRight className="w-3.5 h-3.5" />
            <span>Expand all</span>
          </button>

          <button
            onClick={handleCollapseAll}
            className="px-2.5 py-1 rounded bg-[#1a2232] hover:bg-[#232c3f] border border-[#2a3449] text-slate-200 hover:text-cyan-300 transition-colors flex items-center gap-1"
            title="Collapse all to root"
          >
            <ChevronsLeft className="w-3.5 h-3.5" />
            <span>Collapse all</span>
          </button>

          <div className="w-[1px] h-4 bg-slate-700 mx-1" />

          <button
            onClick={() => zoomOut({ duration: 250 })}
            className="w-7 h-7 flex items-center justify-center rounded bg-[#1a2232] hover:bg-[#232c3f] border border-[#2a3449] text-slate-300"
            title="Zoom out"
          >
            <Minus className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={() => zoomIn({ duration: 250 })}
            className="w-7 h-7 flex items-center justify-center rounded bg-[#1a2232] hover:bg-[#232c3f] border border-[#2a3449] text-slate-300"
            title="Zoom in"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={() => fitView({ padding: 0.2, duration: 400 })}
            className="px-2.5 py-1 rounded bg-[#1a2232] hover:bg-[#232c3f] border border-[#2a3449] text-slate-300 hover:text-slate-100 transition-colors flex items-center gap-1"
            title="Reset zoom to fit view"
          >
            <RotateCcw className="w-3 h-3 text-cyan-400" />
            <span>Reset zoom</span>
          </button>

          <div className="w-[1px] h-4 bg-slate-700 mx-1" />

          {/* Show All Links Toggle */}
          <button
            onClick={() => setShowAllLinks((prev) => !prev)}
            className={`px-2.5 py-1 rounded border text-xs font-mono transition-colors flex items-center gap-1.5 ${
              showAllLinks
                ? 'bg-emerald-950/80 border-emerald-600 text-emerald-300 shadow-sm'
                : 'bg-[#1a2232] hover:bg-[#232c3f] border-[#2a3449] text-slate-300'
            }`}
            title={showAllLinks ? "Showing all dependency links across visible nodes (Click to focus on selected)" : "Showing links for selected item only (Click to show all links)"}
          >
            <Network className="w-3.5 h-3.5 text-emerald-400" />
            <span>{showAllLinks ? "All Links: ON" : "All Links"}</span>
          </button>
        </div>

        {/* Language Badge Legend & Dependency Links Legend */}
        <div className="hidden xl:flex items-center gap-2 text-[11px]">
          <span className="px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 font-semibold">Python</span>
          <span className="px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 font-semibold">JS / TS</span>
          <span className="px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold">JSON</span>
          <span className="px-1.5 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20 font-semibold">HTML / CSS</span>
          <span className="px-1.5 py-0.5 rounded bg-slate-500/10 text-slate-400 border border-slate-500/20">Other</span>
          <span className="text-slate-600">|</span>
          <span className="text-emerald-400 font-bold flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block shadow-[0_0_8px_#4ade80]" />
            🟢 uses
          </span>
          <span className="text-slate-600">|</span>
          <span className="text-amber-400 font-bold flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-amber-400 inline-block shadow-[0_0_8px_#fb923c]" />
            🟠 used by
          </span>
          <span className="text-slate-600">|</span>
          <span className="text-purple-400 font-bold flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-purple-400 inline-block shadow-[0_0_8px_#c084fc]" />
            🟣 external pkg
          </span>
        </div>
      </div>

      {/* Main Flow Canvas */}
      <div
        ref={flowWrapperRef}
        className={`flex-1 w-full h-full relative dot-grid-bg ${
          isPanMode ? 'cursor-grab active:cursor-grabbing select-none' : ''
        }`}
      >
        {preferences.showRulers && <RulerOverlay />}

        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={handleNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={isPanMode ? undefined : handleNodeClick}
          onNodeDragStop={handleNodeDragStop}
          nodeTypes={nodeTypes}
          connectionLineType={ConnectionLineType.SmoothStep}
          minZoom={0.05}
          maxZoom={3.5}
          panOnDrag={true}
          nodesDraggable={!isPanMode}
          elementsSelectable={!isPanMode}
          zoomOnScroll={preferences.zoomOnScroll}
          panOnScroll={!preferences.zoomOnScroll}
          zoomOnPinch={true}
          zoomOnDoubleClick={false}
          proOptions={{ hideAttribution: true }}
        >
          <Background
            variant={BackgroundVariant.Dots}
            gap={24}
            size={1.2}
            color={preferences.isLightMode ? '#cbd5e1' : '#334155'}
          />

          {preferences.showMiniMap && (
            <MiniMap
              zoomable
              pannable
              nodeColor={(n) => {
                if (n.id === selectedRel || (n.id === '__root__' && selectedRel === '')) return '#38bdf8';
                if (n.type === 'externalPackageNode') return '#a855f7';
                return '#1e293b';
              }}
              maskColor="rgba(11, 15, 23, 0.75)"
              className="!bg-[#0e141f] !border !border-[#242d3f] !rounded-xl !bottom-24 !right-4 !shadow-2xl"
            />
          )}
        </ReactFlow>

        {/* Floating Toolbar with 10 controls */}
        <BottomBar
          onFitView={() => fitView({ padding: 0.2, duration: 400 })}
          onZoomIn={() => zoomIn({ duration: 300 })}
          onZoomOut={() => zoomOut({ duration: 300 })}
          onCollapseAll={handleCollapseAll}
          onToggleCollapseAll={handleToggleCollapseAll}
          isAllCollapsed={isAllCollapsed}
          onRotateLayout={handleRotateLayout}
          currentDirection={direction}
          onCenterFirstItem={handleCenterFirstItem}
          onExport={handleExport}
          preferences={preferences}
          onUpdatePreferences={(p) => setPreferences((prev) => ({ ...prev, ...p }))}
          onSearch={handleSearch}
          searchResultCount={searchResults.length}
          currentSearchIndex={searchIndex}
          onNextSearchResult={handleNextSearchResult}
          onPrevSearchResult={handlePrevSearchResult}
          activeTool={activeTool}
          onToggleTool={setActiveTool}
        />
      </div>
    </div>
  );
};
