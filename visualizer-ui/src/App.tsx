import { useState, useEffect, useCallback } from 'react';
import { ReactFlowProvider } from '@xyflow/react';
import { TopBar } from './components/TopBar';
import { ArchitectureMap } from './components/ArchitectureMap';
import { TreeView } from './components/TreeView';
import { DiagramStudio } from './components/DiagramStudio';
import { JsonVisualizer } from './components/JsonVisualizer';
import { InspectorPanel } from './components/InspectorPanel';
import { DiagramLibraryPanel } from './components/DiagramLibraryPanel';
import { SettingsModal } from './components/SettingsModal';
import {
  ProjectData,
  ProjectNode,
  getProject,
  scanProject,
} from './lib/apiClient';
import { Map, Network, Sparkles, FileJson } from 'lucide-react';

type TabMode = 'mindmap' | 'tree' | 'diagrams' | 'json';

export default function App() {
  const [currentPath, setCurrentPath] = useState(
    'C:\\Users\\ROC STORE\\Desktop\\sematic text-virtulizer'
  );
  const [project, setProject] = useState<ProjectData | null>(null);
  const [selectedNode, setSelectedNode] = useState<ProjectNode | null>(null);
  const [activeTab, setActiveTab] = useState<TabMode>('mindmap');

  // Scanner options
  const [isScanning, setIsScanning] = useState(false);
  const [showHidden, setShowHidden] = useState(false);
  const [skipJunk, setSkipJunk] = useState(true);
  const [showFiles, setShowFiles] = useState(true);

  // Docked side panels (Left Library, Right Details)
  const [isLibraryOpen, setIsLibraryOpen] = useState(false);
  const [isInspectorOpen, setIsInspectorOpen] = useState(true);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  // On mount, load existing project or scan default
  useEffect(() => {
    getProject().then((p) => {
      if (p) {
        setProject(p);
        setCurrentPath(p.rootPath);
        if (p.nodes?.length > 0) {
          setSelectedNode(p.nodes[0]);
        }
      } else if (currentPath) {
        handleScan(currentPath, showHidden, skipJunk);
      }
    });
  }, []);

  const handleScan = async (path: string, hidden: boolean, junk: boolean) => {
    if (!path.trim()) return;
    setIsScanning(true);
    try {
      const proj = await scanProject(path.trim(), hidden, junk);
      setProject(proj);
      setCurrentPath(proj.rootPath);
      if (proj.nodes?.length > 0) {
        setSelectedNode(proj.nodes[0]);
      }
    } catch (err) {
      alert(`Scan failed: ${err}`);
    } finally {
      setIsScanning(false);
    }
  };

  const handleSelectNode = useCallback((node: ProjectNode | null) => {
    setSelectedNode(node);
    if (node) {
      setIsInspectorOpen(true);
    }
  }, []);

  const handleSelectFromLibrary = useCallback((node: ProjectNode) => {
    setSelectedNode(node);
    setActiveTab('diagrams');
  }, []);

  return (
    <div className="w-full h-full flex flex-col bg-[#0b0f17] text-slate-100 font-sans overflow-hidden select-none">
      {/* Top Navigation & Scan Bar */}
      <TopBar
        currentPath={currentPath}
        onPathChange={setCurrentPath}
        onScan={handleScan}
        isScanning={isScanning}
        showHidden={showHidden}
        onToggleShowHidden={setShowHidden}
        skipJunk={skipJunk}
        onToggleSkipJunk={setSkipJunk}
        showFiles={showFiles}
        onToggleShowFiles={setShowFiles}
        onToggleLibrary={() => setIsLibraryOpen(!isLibraryOpen)}
        isLibraryOpen={isLibraryOpen}
        onToggleInspector={() => setIsInspectorOpen(!isInspectorOpen)}
        isInspectorOpen={isInspectorOpen}
        onOpenSettings={() => setIsSettingsOpen(true)}
      />

      {/* Sub-Header Tab Switcher */}
      <div className="h-10 bg-[#0d121c] border-b border-[#242d3f] px-3 flex items-center justify-between z-10 shrink-0 text-xs">
        <div className="flex items-center gap-1">
          <button
            onClick={() => setActiveTab('mindmap')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition-all ${
              activeTab === 'mindmap'
                ? 'bg-cyan-950 text-cyan-300 border border-cyan-800/80 shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-[#151c2a]'
            }`}
          >
            <Map className="w-3.5 h-3.5" />
            <span>🗺️ Architecture Mind Map</span>
          </button>

          <button
            onClick={() => setActiveTab('tree')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition-all ${
              activeTab === 'tree'
                ? 'bg-cyan-950 text-cyan-300 border border-cyan-800/80 shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-[#151c2a]'
            }`}
          >
            <Network className="w-3.5 h-3.5" />
            <span>🌲 Dense Tree</span>
          </button>

          <button
            onClick={() => setActiveTab('diagrams')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition-all ${
              activeTab === 'diagrams'
                ? 'bg-cyan-950 text-cyan-300 border border-cyan-800/80 shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-[#151c2a]'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>✨ Diagram Studio (9 Types)</span>
          </button>

          <button
            onClick={() => setActiveTab('json')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition-all ${
              activeTab === 'json'
                ? 'bg-cyan-950 text-cyan-300 border border-cyan-800/80 shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-[#151c2a]'
            }`}
          >
            <FileJson className="w-3.5 h-3.5" />
            <span>📦 JSON Structure Visualizer</span>
          </button>
        </div>

        {/* Project quick statistics pill */}
        {project && (
          <div className="hidden sm:flex items-center gap-3 text-[11px] font-mono text-slate-400">
            <span className="text-slate-300 font-semibold">{project.name}</span>
            <span>•</span>
            <span>{project.totalFiles} files</span>
            <span>•</span>
            <span>{project.edgesCount} links</span>
          </div>
        )}
      </div>

      {/* Main Content Workspace with Docked Split Panels (Paned-style) */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Left: Docked Diagram Library Panel */}
        <DiagramLibraryPanel
          isOpen={isLibraryOpen}
          onClose={() => setIsLibraryOpen(false)}
          nodes={project?.nodes || []}
          onSelectItem={handleSelectFromLibrary}
        />

        {/* Center: Main Visual Canvas / Content */}
        <main className="flex-1 flex flex-col h-full overflow-hidden relative">
          {/* Tab 1: Architecture Mind Map */}
          {activeTab === 'mindmap' && (
            <ReactFlowProvider>
              <ArchitectureMap
                project={project}
                selectedRel={selectedNode?.rel || null}
                onSelectNode={handleSelectNode}
                showFiles={showFiles}
              />
            </ReactFlowProvider>
          )}

          {/* Tab 2: Dense Tree View */}
          {activeTab === 'tree' && (
            <TreeView
              project={project}
              selectedRel={selectedNode?.rel || null}
              onSelectNode={handleSelectNode}
            />
          )}

          {/* Tab 3: Diagram Studio with Direct Target Selector */}
          {activeTab === 'diagrams' && (
            <DiagramStudio
              selectedNode={selectedNode}
              projectName={project?.name || 'CodeMap Project'}
              allNodes={project?.nodes || []}
              onSelectNode={handleSelectNode}
            />
          )}

          {/* Tab 4: JSON & Code Types Explorer */}
          {activeTab === 'json' && (
            <ReactFlowProvider>
              <JsonVisualizer
                project={project}
                onOpenInDiagramStudio={(fileRel) => {
                  const found = project?.nodes?.find((n) => n.rel === fileRel);
                  if (found) {
                    setSelectedNode(found);
                  }
                  setActiveTab('diagrams');
                }}
              />
            </ReactFlowProvider>
          )}
        </main>

        {/* Right: Docked Inspector Panel */}
        <InspectorPanel
          selectedNode={selectedNode}
          isOpen={isInspectorOpen}
          onClose={() => setIsInspectorOpen(false)}
          languagesDistribution={project?.languages || []}
          totalProjectFiles={project?.totalFiles || 1}
          onSelectRel={(rel) => {
            const found = project?.nodes?.find((x) => x.rel === rel);
            if (found) setSelectedNode(found);
          }}
          onNavigateToDiagram={(rel) => {
            const found = project?.nodes?.find((x) => x.rel === rel);
            if (found) setSelectedNode(found);
            setActiveTab('diagrams');
          }}
          onNavigateToJson={(_rel) => {
            setActiveTab('json');
          }}
        />
      </div>

      {/* AI Settings Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
      />
    </div>
  );
}
