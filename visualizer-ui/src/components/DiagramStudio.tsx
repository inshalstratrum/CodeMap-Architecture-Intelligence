import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  Download,
  Code,
  FileText,
  Loader2,
  FolderTree,
  Eye,
  ZoomIn,
  ZoomOut,
  FileCode,
  PenTool,
  Terminal,
  Save,
  Check,
  RotateCcw,
  BookOpen,
  Copy,
  Globe,
  Palette,
} from 'lucide-react';
import {
  ProjectNode,
  DiagramEntry,
  generateDiagram,
  generateDiagramFromText,
  saveDiagramToVault,
  getVaultHistory,
  exportDiagramHtml,
} from '../lib/apiClient';

declare global {
  interface Window {
    mermaid?: {
      initialize: (config: any) => void;
      render: (id: string, text: string) => Promise<{ svg: string }>;
    };
  }
}

interface DiagramStudioProps {
  selectedNode: ProjectNode | null;
  projectName: string;
  allNodes?: ProjectNode[];
  onSelectNode?: (node: ProjectNode | null) => void;
}

const DIAGRAM_TYPES = [
  { id: 'system', label: '1. System Architecture', desc: 'High-level subsystem boundaries, entry points & external dependencies' },
  { id: 'densetree', label: '2. Dense Tree Hierarchy', desc: 'Compact structural tree showing folder nesting, file groupings, and module relationships' },
  { id: 'sequence', label: '3. Sequence & Interaction', desc: 'Call flows between components and request lifecycles' },
  { id: 'dependency', label: '4. Folder & Module Dependency', desc: 'Strict layer hierarchy and import chains' },
  { id: 'dataflow', label: '5. Data Flow & State Pipeline', desc: 'Data inputs, transformations and stores' },
  { id: 'security', label: '6. Security & Trust Boundaries', desc: 'Authentication, authorization & external attack surfaces' },
  { id: 'statemachine', label: '7. State Machine & Lifecycle', desc: 'Entity states and legal transitions' },
  { id: 'class', label: '8. Class & Entity Models', desc: 'Object-oriented models, methods and interfaces' },
  { id: 'component', label: '9. Component Hierarchy', desc: 'UI component trees and prop chains' },
];

export type DiagramTheme = 'dark' | 'forest' | 'neutral' | 'light';

export const DIAGRAM_THEMES: { id: DiagramTheme; label: string; bg: string; border: string }[] = [
  { id: 'dark', label: 'Dark Obsidian', bg: '#090d14', border: '#38bdf8' },
  { id: 'forest', label: 'Forest Mint', bg: '#051811', border: '#34d399' },
  { id: 'neutral', label: 'Neutral Slate', bg: '#18181b', border: '#a1a1aa' },
  { id: 'light', label: 'Clean Light', bg: '#ffffff', border: '#0284c7' },
];

const THEME_MERMAID_CONFIG: Record<DiagramTheme, any> = {
  dark: {
    darkMode: true,
    background: '#090d14',
    primaryColor: '#1e293b',
    primaryTextColor: '#f8fafc',
    primaryBorderColor: '#38bdf8',
    lineColor: '#64748b',
    secondaryColor: '#0f172a',
    tertiaryColor: '#1e293b',
  },
  forest: {
    darkMode: true,
    background: '#051811',
    primaryColor: '#064e3b',
    primaryTextColor: '#ecfdf5',
    primaryBorderColor: '#34d399',
    lineColor: '#10b981',
    secondaryColor: '#022c22',
    tertiaryColor: '#064e3b',
  },
  neutral: {
    darkMode: true,
    background: '#18181b',
    primaryColor: '#27272a',
    primaryTextColor: '#fafafa',
    primaryBorderColor: '#a1a1aa',
    lineColor: '#71717a',
    secondaryColor: '#141416',
    tertiaryColor: '#27272a',
  },
  light: {
    darkMode: false,
    background: '#ffffff',
    primaryColor: '#f1f5f9',
    primaryTextColor: '#0f172a',
    primaryBorderColor: '#0284c7',
    lineColor: '#475569',
    secondaryColor: '#e2e8f0',
    tertiaryColor: '#cbd5e1',
  },
};

const STARTER_TEMPLATES = [
  {
    name: '3D Pipeline Flow',
    type: 'system',
    code: `flowchart TD
  subgraph Input ["1. Input Pipeline"]
    User[User Control Center]
    Config[JSON Configuration & Metadata]
  end

  subgraph Engine ["2. Core Visualizer Engine"]
    StateMgr[State & Node Manager]
    MathKernel[Coordinate & Transform Math]
    Renderer[Three.js / WebGL 3D Canvas]
  end

  subgraph Output ["3. Interactive Viewports"]
    View3D[(3D Spatial Graph)]
    Inspector[Live Property Inspector]
  end

  User --> StateMgr
  Config --> StateMgr
  StateMgr --> MathKernel
  MathKernel --> Renderer
  Renderer --> View3D
  Renderer --> Inspector`,
  },
  {
    name: 'AI Org Workflow',
    type: 'sequence',
    code: `sequenceDiagram
  autonumber
  actor User as User / Operator
  participant Master as Master AI Coordinator
  participant Specialist as Architecture Subagent
  participant Visualizer as 3D Graph Visualizer

  User->>Master: Request Architecture Breakdown
  Master->>Specialist: Task: Parse Codebase & Schemas
  Specialist-->>Master: Extracted AST Nodes & Links
  Master->>Visualizer: Stream Interactive Graph Data
  Visualizer-->>User: Render Multi-level Mind Map & Diagrams`,
  },
  {
    name: 'Dense Tree Hierarchy',
    type: 'densetree',
    code: `flowchart TD
  Root[Project Root]
  
  Root --> Src[src/]
  Root --> Config[Configs & Schemas]
  Root --> Docs[docs/]

  Src --> Components[components/]
  Src --> Lib[lib/]
  Src --> Styles[styles/]

  Components --> UI3D[Visualizer3D.tsx]
  Components --> Center[ControlCenter.tsx]
  Lib --> GraphEngine[layoutEngine.ts]
  Config --> SchemaJSON[settings.json]`,
  },
  {
    name: 'State Machine Lifecycle',
    type: 'statemachine',
    code: `stateDiagram-v2
  [*] --> Idle: System Initialized
  Idle --> Scanning: User Selects Target File / Project
  Scanning --> Analyzing: AST & Dependency Parsing
  Analyzing --> Generating: AI Mermaid Prompt
  Generating --> Rendered: Visual SVG Rendered
  Rendered --> Idle: Diagram Saved to Vault`,
  },
];

type StudioMode = 'project' | 'custom' | 'manual';

export const DiagramStudio: React.FC<DiagramStudioProps> = ({
  selectedNode,
  projectName,
  allNodes = [],
  onSelectNode,
}) => {
  const [studioMode, setStudioMode] = useState<StudioMode>('project');
  const [selectedType, setSelectedType] = useState('system');
  const [isGenerating, setIsGenerating] = useState(false);
  const [activeDiagram, setActiveDiagram] = useState<DiagramEntry | null>(null);
  const [history, setHistory] = useState<DiagramEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showRawMermaid, setShowRawMermaid] = useState(false);

  // Editable Mermaid code for in-place tweaks
  const [editedMermaid, setEditedMermaid] = useState('');
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Custom text mode state
  const [customTitle, setCustomTitle] = useState('3D Visualizer Architecture & AI Workflow');
  const [customText, setCustomText] = useState(
    'Architecture for 3D visualizer control center: Non-programmers inspect JSON nodes, TypeScript components, and AI organizational structures. Inputs flow through a parser into an interactive canvas with real-time hand-tool panning, fixed node positioning, and visual color-coded links.'
  );

  // Manual live mermaid editor state
  const [manualCode, setManualCode] = useState(STARTER_TEMPLATES[0].code);

  // Visual SVG rendering state
  const [renderedSvg, setRenderedSvg] = useState<string>('');
  const [renderError, setRenderError] = useState<string | null>(null);
  const [isRendering, setIsRendering] = useState(false);
  const [zoom, setZoom] = useState(1.0);

  const targetRel = selectedNode?.rel || '';
  const isFile = selectedNode ? !selectedNode.isDir : false;
  const targetLabel = selectedNode ? selectedNode.name : `${projectName} (Entire Project)`;

  // Fetch saved diagrams for this target from vault
  useEffect(() => {
    if (studioMode === 'project') {
      getVaultHistory(targetRel, isFile).then((items) => {
        setHistory(items);
        if (items.length > 0) {
          setActiveDiagram(items[0]);
          setEditedMermaid(items[0].mermaid);
        } else {
          setActiveDiagram(null);
          setEditedMermaid('');
        }
      });
    } else {
      getVaultHistory('@custom', false).then((items) => {
        setHistory(items);
        if (items.length > 0 && !activeDiagram) {
          setActiveDiagram(items[0]);
          setEditedMermaid(items[0].mermaid);
        }
      });
    }
  }, [targetRel, isFile, studioMode]);

  // Theme selection for diagram styling
  const [diagramTheme, setDiagramTheme] = useState<DiagramTheme>('dark');
  const [copiedSvg, setCopiedSvg] = useState(false);
  const [copiedMermaid, setCopiedMermaid] = useState(false);
  const [isExportingHtml, setIsExportingHtml] = useState(false);
  const [exportedHtmlPath, setExportedHtmlPath] = useState<string | null>(null);

  // Keep editedMermaid in sync when activeDiagram changes
  useEffect(() => {
    if (activeDiagram?.mermaid) {
      setEditedMermaid(activeDiagram.mermaid);
    }
  }, [activeDiagram]);

  // Render Mermaid code into SVG whenever activeDiagram changes, in manual mode, or theme changes
  const currentMermaidCodeToRender =
    studioMode === 'manual' ? manualCode : (activeDiagram?.mermaid || '');

  useEffect(() => {
    if (!currentMermaidCodeToRender.trim()) {
      setRenderedSvg('');
      setRenderError(null);
      return;
    }

    let isMounted = true;
    const renderDiagram = async () => {
      setIsRendering(true);
      setRenderError(null);

      // Wait if window.mermaid script is still loading
      let attempts = 0;
      while (typeof window !== 'undefined' && !window.mermaid && attempts < 20) {
        await new Promise((r) => setTimeout(r, 100));
        attempts++;
      }

      if (typeof window !== 'undefined' && window.mermaid) {
        try {
          const cfg = THEME_MERMAID_CONFIG[diagramTheme] || THEME_MERMAID_CONFIG.dark;
          window.mermaid.initialize({
            startOnLoad: false,
            theme: diagramTheme === 'light' ? 'default' : 'dark',
            securityLevel: 'loose',
            fontFamily: 'Segoe UI, sans-serif',
            themeVariables: cfg,
          });

          let code = currentMermaidCodeToRender.trim();
          code = code.replace(/^```(?:mermaid)?\s*\n?/i, '').replace(/\n?```\s*$/i, '').trim();

          const renderId = `mermaid_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
          const { svg } = await window.mermaid.render(renderId, code);
          if (isMounted) {
            setRenderedSvg(svg);
            setRenderError(null);
            setIsRendering(false);
          }
        } catch (err: any) {
          if (isMounted) {
            setRenderError(String(err?.message || err || 'Syntax notice'));
            setIsRendering(false);
          }
        }
      } else {
        if (isMounted) {
          setIsRendering(false);
          setRenderError('Mermaid engine loading or unavailable offline.');
        }
      }
    };

    renderDiagram();
    return () => {
      isMounted = false;
    };
  }, [currentMermaidCodeToRender, diagramTheme]);

  // Generate for selected file/folder
  const handleGenerate = async () => {
    setIsGenerating(true);
    setError(null);
    try {
      const entry = await generateDiagram(targetRel, isFile, selectedType);
      setActiveDiagram(entry);
      setEditedMermaid(entry.mermaid);
      setHistory((prev) => [entry, ...prev]);
    } catch (err) {
      setError(String(err));
    } finally {
      setIsGenerating(false);
    }
  };

  // Generate from custom text/requirements
  const handleGenerateCustom = async () => {
    if (!customText.trim()) return;
    setIsGenerating(true);
    setError(null);
    try {
      const entry = await generateDiagramFromText(customText.trim(), selectedType, customTitle.trim());
      setActiveDiagram(entry);
      setEditedMermaid(entry.mermaid);
      setHistory((prev) => [entry, ...prev]);
    } catch (err) {
      setError(String(err));
    } finally {
      setIsGenerating(false);
    }
  };

  // Apply in-place edits made in Code view
  const handleApplyCodeEdit = async () => {
    if (!editedMermaid.trim()) return;
    try {
      const entry = await saveDiagramToVault(
        editedMermaid.trim(),
        activeDiagram?.explanation || 'User edited Mermaid diagram.',
        activeDiagram?.title || 'Custom Diagram',
        studioMode === 'project' ? targetRel : '@custom',
        studioMode === 'project' ? isFile : false,
        activeDiagram?.type || 'custom'
      );
      setActiveDiagram(entry);
      setHistory((prev) => [entry, ...prev.filter((h) => h.id !== entry.id)]);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2500);
    } catch (err) {
      alert(`Could not save changes: ${err}`);
    }
  };

  // Save manual diagram to vault
  const handleSaveManual = async () => {
    if (!manualCode.trim()) return;
    try {
      const entry = await saveDiagramToVault(
        manualCode.trim(),
        'Manually authored or imported Mermaid diagram.',
        'Manual Mermaid Model',
        '@custom',
        false,
        'manual'
      );
      setActiveDiagram(entry);
      setHistory((prev) => [entry, ...prev]);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2500);
    } catch (err) {
      alert(`Could not save to vault: ${err}`);
    }
  };

  const handleDownloadSVG = () => {
    const content = renderedSvg || currentMermaidCodeToRender;
    const isSvg = Boolean(renderedSvg && !showRawMermaid);
    const blob = new Blob([content], { type: isSvg ? 'image/svg+xml' : 'text/plain' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    const safeName = (activeDiagram?.title || targetLabel || 'diagram').replace(/[^a-zA-Z0-9_\-]+/g, '_');
    link.download = `${safeName}_${activeDiagram?.type || 'visual'}.${isSvg ? 'svg' : 'mmd'}`;
    link.href = url;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleDownloadMMD = () => {
    const code = editedMermaid || currentMermaidCodeToRender;
    const blob = new Blob([code], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    const safeName = (activeDiagram?.title || targetLabel || 'diagram').replace(/[^a-zA-Z0-9_\-]+/g, '_');
    link.download = `${safeName}.mmd`;
    link.href = url;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleCopySvg = async () => {
    if (!renderedSvg) return;
    try {
      await navigator.clipboard.writeText(renderedSvg);
      setCopiedSvg(true);
      setTimeout(() => setCopiedSvg(false), 2000);
    } catch (err) {
      console.error('Copy SVG failed:', err);
    }
  };

  const handleCopyMermaid = async () => {
    const code = editedMermaid || currentMermaidCodeToRender;
    if (!code) return;
    try {
      await navigator.clipboard.writeText(code);
      setCopiedMermaid(true);
      setTimeout(() => setCopiedMermaid(false), 2000);
    } catch (err) {
      console.error('Copy Mermaid failed:', err);
    }
  };

  const handleExportHtml = async () => {
    const code = editedMermaid || currentMermaidCodeToRender;
    if (!code) return;
    setIsExportingHtml(true);
    try {
      const savedPath = await exportDiagramHtml(
        studioMode === 'project' ? targetRel : '@custom',
        studioMode === 'project' ? isFile : false,
        activeDiagram?.title || (studioMode === 'custom' ? customTitle : 'Direct Architecture Diagram'),
        code,
        activeDiagram?.explanation || 'Exported standalone HTML architecture diagram.',
        activeDiagram?.type || selectedType,
        true
      );
      setExportedHtmlPath(savedPath);
      setTimeout(() => setExportedHtmlPath(null), 5000);
    } catch (err) {
      alert(`HTML Export failed: ${err}`);
    } finally {
      setIsExportingHtml(false);
    }
  };

  const handleTargetChange = (rel: string) => {
    if (rel === '__root__' || rel === '') {
      onSelectNode?.(null);
    } else {
      const found = allNodes.find((n) => n.rel === rel);
      if (found) onSelectNode?.(found);
    }
  };

  return (
    <div className="w-full h-full flex flex-col bg-[#0b0f17] text-slate-200 select-none overflow-hidden">
      {/* Studio Header Toolbar */}
      <div className="p-3 border-b border-[#242d3f] bg-[#0e141f] flex flex-wrap items-center justify-between gap-3 shrink-0">
        <div className="flex flex-wrap items-center gap-3">
          {/* Mode Switcher Tabs */}
          <div className="flex items-center bg-[#151c2a] border border-[#2a3449] rounded-lg p-0.5">
            <button
              onClick={() => setStudioMode('project')}
              className={`px-3 py-1.5 rounded-md text-xs font-medium flex items-center gap-1.5 transition-all ${
                studioMode === 'project'
                  ? 'bg-cyan-950 text-cyan-300 border border-cyan-800 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <FolderTree className="w-3.5 h-3.5" />
              <span>📁 Project Targets</span>
            </button>

            <button
              onClick={() => setStudioMode('custom')}
              className={`px-3 py-1.5 rounded-md text-xs font-medium flex items-center gap-1.5 transition-all ${
                studioMode === 'custom'
                  ? 'bg-cyan-950 text-cyan-300 border border-cyan-800 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <PenTool className="w-3.5 h-3.5" />
              <span>✍️ Custom Text & AI Spec</span>
            </button>

            <button
              onClick={() => setStudioMode('manual')}
              className={`px-3 py-1.5 rounded-md text-xs font-medium flex items-center gap-1.5 transition-all ${
                studioMode === 'manual'
                  ? 'bg-cyan-950 text-cyan-300 border border-cyan-800 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Terminal className="w-3.5 h-3.5" />
              <span>⚡ Live Mermaid Studio</span>
            </button>
          </div>

          {/* Mode 1: Project Target Controls */}
          {studioMode === 'project' && (
            <>
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-semibold text-slate-400">Target:</span>
                <select
                  value={selectedNode?.rel || ''}
                  onChange={(e) => handleTargetChange(e.target.value)}
                  className="h-8 max-w-xs px-2.5 rounded-lg bg-[#141a27] border border-[#2a3449] text-xs font-mono text-cyan-300 outline-none focus:border-cyan-400"
                >
                  <option value="">{projectName} (Entire Project)</option>
                  <optgroup label="Files & Folders">
                    {allNodes
                      .filter((n) => n.rel !== '')
                      .map((n) => (
                        <option key={n.id} value={n.rel}>
                          {n.isDir ? '📁 ' : '📄 '}
                          {n.rel}
                        </option>
                      ))}
                  </optgroup>
                </select>
              </div>

              <div className="flex items-center gap-1.5">
                <span className="text-xs font-semibold text-slate-400">Type:</span>
                <select
                  value={selectedType}
                  onChange={(e) => setSelectedType(e.target.value)}
                  className="h-8 px-2.5 rounded-lg bg-[#141a27] border border-[#2a3449] text-xs font-mono text-slate-200 outline-none focus:border-cyan-400"
                >
                  {DIAGRAM_TYPES.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </div>

              {history.length > 0 && (
                <select
                  value={activeDiagram?.id || ''}
                  onChange={(e) => {
                    const found = history.find((h) => h.id === e.target.value);
                    if (found) {
                      setActiveDiagram(found);
                      setEditedMermaid(found.mermaid);
                    }
                  }}
                  className="h-8 px-2 rounded-lg bg-[#141a27] border border-[#2a3449] text-xs text-slate-300 outline-none"
                >
                  {history.map((h) => (
                    <option key={h.id} value={h.id}>
                      {h.title} ({h.timestamp || 'Saved'})
                    </option>
                  ))}
                </select>
              )}

              <button
                onClick={handleGenerate}
                disabled={isGenerating}
                className={`h-8 px-3.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
                  isGenerating
                    ? 'bg-cyan-950 text-cyan-400 border border-cyan-800'
                    : 'bg-cyan-500 hover:bg-cyan-400 text-black shadow-lg shadow-cyan-500/20 active:scale-95'
                }`}
              >
                {isGenerating ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Analyzing Target…</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3.5 h-3.5 fill-current" />
                    <span>Generate AI Diagram</span>
                  </>
                )}
              </button>
            </>
          )}

          {/* Mode 2: Custom Text AI Spec Controls */}
          {studioMode === 'custom' && (
            <>
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-semibold text-slate-400">Diagram Type:</span>
                <select
                  value={selectedType}
                  onChange={(e) => setSelectedType(e.target.value)}
                  className="h-8 px-2.5 rounded-lg bg-[#141a27] border border-[#2a3449] text-xs font-mono text-slate-200 outline-none focus:border-cyan-400"
                >
                  {DIAGRAM_TYPES.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </div>

              <button
                onClick={handleGenerateCustom}
                disabled={isGenerating || !customText.trim()}
                className={`h-8 px-3.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
                  isGenerating
                    ? 'bg-cyan-950 text-cyan-400 border border-cyan-800'
                    : 'bg-emerald-500 hover:bg-emerald-400 text-black shadow-lg shadow-emerald-500/20 active:scale-95'
                }`}
              >
                {isGenerating ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Generating from Spec…</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3.5 h-3.5 fill-current" />
                    <span>Generate Diagram from Text</span>
                  </>
                )}
              </button>
            </>
          )}

          {/* Mode 3: Live Mermaid Studio Controls */}
          {studioMode === 'manual' && (
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-slate-400">Templates:</span>
              <div className="flex items-center gap-1">
                {STARTER_TEMPLATES.map((tmpl) => (
                  <button
                    key={tmpl.name}
                    onClick={() => setManualCode(tmpl.code)}
                    className="h-7 px-2.5 rounded bg-[#172030] hover:bg-[#202c42] border border-[#2a3449] text-[11px] text-cyan-300 font-mono transition-colors"
                  >
                    {tmpl.name}
                  </button>
                ))}
              </div>

              <button
                onClick={handleSaveManual}
                className="h-7 px-3 rounded bg-cyan-600 hover:bg-cyan-500 text-white font-semibold text-xs flex items-center gap-1 transition-all ml-2"
              >
                {saveSuccess ? (
                  <>
                    <Check className="w-3 h-3 text-emerald-300" />
                    <span>Saved to Vault!</span>
                  </>
                ) : (
                  <>
                    <Save className="w-3 h-3" />
                    <span>Save to Project Vault</span>
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      </div>

      {error && (
        <div className="p-3 bg-rose-950/90 border-b border-rose-800 text-rose-300 text-xs font-mono shrink-0">
          Generation Error: {error}
        </div>
      )}

      {/* Main Workspace */}
      <div className="flex-1 flex flex-col lg:flex-row overflow-hidden">
        {/* Left Column / Input Area (When in Custom or Manual mode) */}
        {studioMode === 'custom' && (
          <div className="w-full lg:w-96 p-4 border-r border-[#242d3f] bg-[#0e131d] flex flex-col space-y-3 shrink-0 overflow-y-auto">
            <div className="flex items-center gap-2 text-xs font-semibold text-cyan-300 pb-2 border-b border-[#242d3f]">
              <PenTool className="w-4 h-4 text-cyan-400" />
              <span>Specification & Requirements</span>
            </div>

            <div>
              <label className="text-[11px] font-semibold text-slate-400 block mb-1">
                Diagram Title:
              </label>
              <input
                type="text"
                value={customTitle}
                onChange={(e) => setCustomTitle(e.target.value)}
                placeholder="e.g. 3D Visualizer Architecture & AI Pipeline"
                className="w-full h-8 px-2.5 rounded-lg bg-[#141a27] border border-[#2a3449] text-xs font-mono text-cyan-200 outline-none focus:border-cyan-400"
              />
            </div>

            <div className="flex-1 flex flex-col">
              <label className="text-[11px] font-semibold text-slate-400 block mb-1">
                Description / Workflow / System Notes:
              </label>
              <textarea
                value={customText}
                onChange={(e) => setCustomText(e.target.value)}
                placeholder="Type or paste system descriptions, workflows, 3D visualizer pipelines, AI agent roles, or requirements..."
                className="flex-1 min-h-[220px] p-3 rounded-xl bg-[#090d14] border border-[#2a3449] text-xs font-mono text-slate-200 leading-relaxed outline-none resize-none focus:border-cyan-400 selection:bg-cyan-900/60"
              />
            </div>

            <div className="space-y-1.5 pt-1">
              <div className="text-[10px] text-slate-400 uppercase font-bold tracking-wider">
                Quick Presets:
              </div>
              <div className="flex flex-wrap gap-1.5">
                <button
                  onClick={() => {
                    setCustomTitle('3D Visualizer Spatial Pipeline');
                    setCustomText(
                      '3D Visualizer control center: Input files (.json, .ts, .py) are scanned into AST nodes. Nodes are mapped onto a 3D WebGL spatial canvas. Users pan with a hand tool, zoom smoothly, and toggle internal (green) and external (orange) relationship links. Color themes can be adjusted live on the unified control panel.'
                    );
                  }}
                  className="px-2 py-1 rounded bg-[#161d2b] hover:bg-[#202a3d] border border-[#2a3449] text-[10px] text-cyan-300 font-mono"
                >
                  3D Visualizer Pipeline
                </button>
                <button
                  onClick={() => {
                    setCustomTitle('Autonomous AI Organization');
                    setCustomText(
                      'AI Organization workflow: A master coordinator assigns tasks to specialized agents (Architecture Scanner, JSON Validator, UI Builder). Subagents interact asynchronously with shared memory snapshots and report back to the user on completion.'
                    );
                  }}
                  className="px-2 py-1 rounded bg-[#161d2b] hover:bg-[#202a3d] border border-[#2a3449] text-[10px] text-cyan-300 font-mono"
                >
                  AI Organization Workflow
                </button>
              </div>
            </div>
          </div>
        )}

        {studioMode === 'manual' && (
          <div className="w-full lg:w-96 p-4 border-r border-[#242d3f] bg-[#0e131d] flex flex-col space-y-3 shrink-0 overflow-y-auto">
            <div className="flex items-center gap-2 text-xs font-semibold text-cyan-300 pb-2 border-b border-[#242d3f]">
              <Terminal className="w-4 h-4 text-cyan-400" />
              <span>Direct Mermaid Code Input</span>
            </div>

            <div className="flex-1 flex flex-col">
              <label className="text-[11px] font-semibold text-slate-400 block mb-1">
                Mermaid Syntax (Real-time Preview):
              </label>
              <textarea
                value={manualCode}
                onChange={(e) => setManualCode(e.target.value)}
                spellCheck={false}
                placeholder="flowchart TD\n  A[Start] --> B[Finish]"
                className="flex-1 min-h-[340px] p-3 rounded-xl bg-[#090d14] border border-[#2a3449] text-xs font-mono text-cyan-300 leading-relaxed outline-none resize-none focus:border-cyan-400 selection:bg-cyan-900/60"
              />
            </div>

            <p className="text-[11px] text-slate-400 leading-relaxed">
              Type or paste any valid Mermaid diagram syntax above. The live SVG view on the right
              updates instantaneously. Click <strong>Save to Project Vault</strong> to permanently store it.
            </p>
          </div>
        )}

        {/* Center: Visual Canvas / Interactive Diagram Container */}
        <div className="flex-1 flex flex-col p-4 overflow-hidden border-r border-[#242d3f] bg-[#0b0f17] relative">
          {(activeDiagram || studioMode === 'manual') ? (
            <div className="w-full h-full flex flex-col rounded-2xl border border-[#242d3f] bg-[#111622] overflow-hidden shadow-2xl">
              {/* Header inside Diagram Card */}
              <div className="px-4 py-2.5 border-b border-[#242d3f] bg-[#0e131d] flex flex-wrap items-center justify-between gap-2 shrink-0">
                <div className="flex items-center gap-2 overflow-hidden">
                  <span className="font-mono text-xs font-bold text-cyan-300 truncate">
                    {studioMode === 'manual' ? 'Live Mermaid Preview' : (activeDiagram?.title || 'Architecture Model')}
                  </span>
                  <span className="text-[11px] text-slate-400 font-mono truncate">
                    ({studioMode === 'project' ? targetLabel : studioMode === 'custom' ? customTitle : 'Direct Mode'})
                  </span>
                </div>

                <div className="flex items-center gap-1.5">
                  {/* Visual vs Code Toggle */}
                  <div className="flex items-center bg-[#171e2c] border border-[#2a3449] rounded-lg p-0.5">
                    <button
                      onClick={() => setShowRawMermaid(false)}
                      className={`px-2 py-1 rounded text-xs font-medium flex items-center gap-1 transition-colors ${
                        !showRawMermaid
                          ? 'bg-cyan-950 text-cyan-300 shadow-sm border border-cyan-800/80'
                          : 'text-slate-400 hover:text-slate-200'
                      }`}
                      title="Visual SVG diagram"
                    >
                      <Eye className="w-3.5 h-3.5" />
                      <span>Diagram</span>
                    </button>
                    <button
                      onClick={() => setShowRawMermaid(true)}
                      className={`px-2 py-1 rounded text-xs font-medium flex items-center gap-1 transition-colors ${
                        showRawMermaid
                          ? 'bg-cyan-950 text-cyan-300 shadow-sm border border-cyan-800/80'
                          : 'text-slate-400 hover:text-slate-200'
                      }`}
                      title="Raw Mermaid syntax"
                    >
                      <Code className="w-3.5 h-3.5" />
                      <span>Code</span>
                    </button>
                  </div>

                  {!showRawMermaid && (
                    <div className="flex items-center gap-1 ml-1">
                      <button
                        onClick={() => setZoom((z) => Math.max(0.4, Number((z - 0.15).toFixed(2))))}
                        className="w-7 h-7 flex items-center justify-center rounded bg-[#1a2232] hover:bg-[#232c3f] border border-[#2a3449] text-slate-300"
                        title="Zoom out"
                      >
                        <ZoomOut className="w-3 h-3" />
                      </button>
                      <span className="text-[10px] font-mono text-slate-400 w-9 text-center">
                        {Math.round(zoom * 100)}%
                      </span>
                      <button
                        onClick={() => setZoom((z) => Math.min(2.5, Number((z + 0.15).toFixed(2))))}
                        className="w-7 h-7 flex items-center justify-center rounded bg-[#1a2232] hover:bg-[#232c3f] border border-[#2a3449] text-slate-300"
                        title="Zoom in"
                      >
                        <ZoomIn className="w-3 h-3" />
                      </button>
                      <button
                        onClick={() => setZoom(1.0)}
                        className="h-7 px-2 flex items-center justify-center rounded bg-[#1a2232] hover:bg-[#232c3f] border border-[#2a3449] text-slate-300 text-[10px] font-mono"
                        title="Reset zoom"
                      >
                        Reset
                      </button>
                    </div>
                  )}

                  <div className="w-[1px] h-4 bg-slate-700 mx-1" />

                  {/* Diagram Theme Selector */}
                  <div className="flex items-center gap-1 bg-[#141a27] border border-[#2a3449] rounded-lg px-1.5 h-7">
                    <Palette className="w-3 h-3 text-cyan-400 shrink-0" />
                    <select
                      value={diagramTheme}
                      onChange={(e) => setDiagramTheme(e.target.value as DiagramTheme)}
                      className="bg-transparent text-[11px] font-mono text-slate-300 outline-none cursor-pointer"
                      title="Select visual diagram theme"
                    >
                      {DIAGRAM_THEMES.map((th) => (
                        <option key={th.id} value={th.id} className="bg-[#141a27] text-slate-200">
                          {th.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="w-[1px] h-4 bg-slate-700 mx-0.5" />

                  {/* Copy buttons */}
                  <button
                    onClick={handleCopySvg}
                    disabled={!renderedSvg}
                    className="h-7 px-2 rounded bg-[#1a2232] hover:bg-[#232c3f] border border-[#2a3449] text-slate-300 text-xs flex items-center gap-1 transition-colors disabled:opacity-40"
                    title="Copy rendered SVG markup to clipboard"
                  >
                    {copiedSvg ? (
                      <>
                        <Check className="w-3 h-3 text-emerald-400" />
                        <span className="text-[11px] text-emerald-400 font-semibold">Copied!</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3 h-3 text-cyan-400" />
                        <span className="text-[11px]">Copy SVG</span>
                      </>
                    )}
                  </button>

                  <button
                    onClick={handleCopyMermaid}
                    disabled={!currentMermaidCodeToRender}
                    className="h-7 px-2 rounded bg-[#1a2232] hover:bg-[#232c3f] border border-[#2a3449] text-slate-300 text-xs flex items-center gap-1 transition-colors disabled:opacity-40"
                    title="Copy Mermaid code to clipboard"
                  >
                    {copiedMermaid ? (
                      <>
                        <Check className="w-3 h-3 text-emerald-400" />
                        <span className="text-[11px] text-emerald-400 font-semibold">Copied!</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3 h-3 text-slate-400" />
                        <span className="text-[11px]">Copy Code</span>
                      </>
                    )}
                  </button>

                  {/* Export HTML */}
                  <button
                    onClick={handleExportHtml}
                    disabled={isExportingHtml || !currentMermaidCodeToRender}
                    className="h-7 px-2.5 rounded bg-emerald-700 hover:bg-emerald-600 text-white font-semibold text-xs flex items-center gap-1.5 transition-colors disabled:opacity-50 shadow-sm"
                    title="Export standalone interactive HTML diagram and reveal in Explorer"
                  >
                    {isExportingHtml ? (
                      <>
                        <Loader2 className="w-3 h-3 animate-spin" />
                        <span className="text-[11px]">Exporting…</span>
                      </>
                    ) : (
                      <>
                        <Globe className="w-3 h-3 text-emerald-200" />
                        <span className="text-[11px]">Export HTML</span>
                      </>
                    )}
                  </button>

                  <div className="w-[1px] h-4 bg-slate-700 mx-0.5" />

                  <button
                    onClick={handleDownloadSVG}
                    className="h-7 px-2.5 rounded bg-cyan-600 hover:bg-cyan-500 text-white font-semibold text-xs flex items-center gap-1 transition-colors"
                    title="Export visual SVG diagram"
                  >
                    <Download className="w-3 h-3" />
                    <span>SVG</span>
                  </button>

                  <button
                    onClick={handleDownloadMMD}
                    className="h-7 px-2.5 rounded bg-[#1a2232] hover:bg-[#232c3f] border border-[#2a3449] text-slate-300 text-xs flex items-center gap-1 transition-colors"
                    title="Download raw .mmd Mermaid source"
                  >
                    <FileCode className="w-3 h-3 text-cyan-400" />
                    <span>.mmd</span>
                  </button>
                </div>
              </div>

              {/* HTML Export Success Feedback Banner */}
              {exportedHtmlPath && (
                <div className="px-4 py-2 bg-emerald-950/90 border-b border-emerald-800 text-emerald-300 text-xs font-mono flex items-center justify-between shrink-0 animate-fade-in">
                  <div className="flex items-center gap-2 truncate">
                    <Check className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span className="truncate">
                      Interactive HTML exported & revealed in Explorer: <strong>{exportedHtmlPath}</strong>
                    </span>
                  </div>
                  <button
                    onClick={() => setExportedHtmlPath(null)}
                    className="text-emerald-400 hover:text-emerald-200 text-xs ml-2 underline"
                  >
                    Dismiss
                  </button>
                </div>
              )}

              {/* Diagram Body */}
              <div
                className={`flex-1 overflow-auto p-4 flex items-center justify-center relative transition-colors duration-200 ${
                  diagramTheme === 'light'
                    ? 'bg-white'
                    : diagramTheme === 'forest'
                    ? 'bg-[#051811]'
                    : diagramTheme === 'neutral'
                    ? 'bg-[#18181b]'
                    : 'bg-[#090d14]'
                }`}
              >
                {showRawMermaid ? (
                  <div className="w-full h-full flex flex-col p-2 space-y-2">
                    <div className="flex items-center justify-between text-xs text-slate-400 px-1">
                      <span>Editable Mermaid Code:</span>
                      <button
                        onClick={handleApplyCodeEdit}
                        className="h-6 px-2.5 rounded bg-cyan-600 hover:bg-cyan-500 text-white font-semibold text-[11px] flex items-center gap-1"
                      >
                        {saveSuccess ? (
                          <>
                            <Check className="w-3 h-3 text-emerald-300" />
                            <span>Saved!</span>
                          </>
                        ) : (
                          <>
                            <RotateCcw className="w-3 h-3" />
                            <span>Apply & Save Changes</span>
                          </>
                        )}
                      </button>
                    </div>
                    <textarea
                      value={editedMermaid}
                      onChange={(e) => setEditedMermaid(e.target.value)}
                      spellCheck={false}
                      className="flex-1 w-full p-4 bg-[#090d14] rounded-xl text-xs font-mono text-cyan-300 overflow-auto border border-[#1f283a] select-text resize-none outline-none focus:border-cyan-400"
                    />
                  </div>
                ) : isRendering ? (
                  <div className="flex flex-col items-center justify-center gap-2 text-slate-400">
                    <Loader2 className="w-6 h-6 animate-spin text-cyan-400" />
                    <span className="text-xs font-mono">Rendering visual architecture diagram…</span>
                  </div>
                ) : renderError ? (
                  <div className="w-full h-full flex flex-col p-4 space-y-3">
                    <div className="p-3 rounded-lg bg-amber-950/40 border border-amber-800/60 text-amber-300 text-xs font-mono">
                      Visual diagram notice: {renderError}. Showing Mermaid code below.
                    </div>
                    <textarea
                      value={editedMermaid || currentMermaidCodeToRender}
                      onChange={(e) => setEditedMermaid(e.target.value)}
                      className="flex-1 p-4 bg-[#090d14] rounded-xl text-xs font-mono text-slate-300 overflow-auto border border-[#1f283a] select-text outline-none resize-none"
                    />
                  </div>
                ) : renderedSvg ? (
                  <div
                    style={{
                      transform: `scale(${zoom})`,
                      transformOrigin: 'center center',
                      transition: 'transform 0.15s ease-out',
                    }}
                    className="w-full h-full flex items-center justify-center overflow-auto mermaid-svg-container"
                    dangerouslySetInnerHTML={{ __html: renderedSvg }}
                  />
                ) : (
                  <div className="text-xs text-slate-500 font-mono">
                    Generating diagram view…
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="w-full h-full flex flex-col items-center justify-center text-center space-y-3 max-w-md mx-auto p-4">
              <div className="w-12 h-12 rounded-2xl bg-cyan-950/60 border border-cyan-800/40 text-cyan-400 flex items-center justify-center mx-auto shadow-xl">
                <FolderTree className="w-6 h-6" />
              </div>
              <h3 className="text-sm font-semibold text-slate-200">
                No Diagram Generated Yet
              </h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Choose a target file (.json, .md, .ts, .py) or folder from the dropdown above and click{' '}
                <strong className="text-cyan-400">Generate AI Diagram</strong>, or switch to{' '}
                <strong className="text-cyan-400">Custom Text</strong> / <strong className="text-cyan-400">Live Mermaid</strong> mode.
              </p>
            </div>
          )}
        </div>

        {/* Right: AI Explanation & Notes */}
        <div className="w-full lg:w-96 p-4 overflow-y-auto bg-[#0f141f] space-y-3 shrink-0">
          <div className="flex items-center gap-2 pb-2 border-b border-[#242d3f] text-xs font-semibold text-slate-300">
            <FileText className="w-4 h-4 text-cyan-400" />
            <span>Architectural Explanation</span>
          </div>

          {activeDiagram?.explanation ? (
            <div className="text-xs font-mono text-slate-300 leading-relaxed whitespace-pre-wrap select-text">
              {activeDiagram.explanation}
            </div>
          ) : (
            <div className="text-xs text-slate-500 italic">
              When an AI diagram is generated, beginner-friendly explanations, key flow boundaries,
              and recommendations will appear here.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
