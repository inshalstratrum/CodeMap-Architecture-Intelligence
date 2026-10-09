import { useState, useEffect, useRef } from 'react';
import {
  Maximize,
  Minimize2,
  Minus,
  Plus,
  RotateCw,
  Download,
  Focus,
  FolderMinus,
  FolderPlus,
  Search,
  Settings,
  Sun,
  Moon,
  Ruler,
  MousePointer,
  Hand,
  ChevronUp,
  ChevronDown,
  X,
  Map as MapIcon,
  Palette,
  Sliders,
  Check,
  Spline,
} from 'lucide-react';
import { LayoutDirection } from '../lib/layoutEngine';

export type ThemeMode = 'obsidian' | 'cyberpunk' | 'midnight' | 'light';
export type ConnectionCurve = 'smoothstep' | 'straight' | 'bezier';

export interface PreferencesState {
  theme: ThemeMode;
  isLightMode: boolean;
  zoomOnScroll: boolean;
  showRulers: boolean;
  showMiniMap: boolean;
  showGreenUses: boolean;
  showOrangeUsedBy: boolean;
  showHierarchyLinks: boolean;
  showExternalPackages: boolean;
  connectionCurve: ConnectionCurve;
}

interface BottomBarProps {
  onFitView: () => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onCollapseAll: () => void;
  onToggleCollapseAll?: () => void;
  isAllCollapsed?: boolean;
  onRotateLayout: () => void;
  currentDirection: LayoutDirection;
  onCenterFirstItem: () => void;
  onExport: () => void;
  preferences: PreferencesState;
  onUpdatePreferences: (pref: Partial<PreferencesState>) => void;
  onSearch: (query: string) => void;
  searchResultCount: number;
  currentSearchIndex: number;
  onNextSearchResult: () => void;
  onPrevSearchResult: () => void;
  activeTool?: 'pointer' | 'hand';
  onToggleTool?: (tool: 'pointer' | 'hand') => void;
}

export function BottomBar({
  onFitView,
  onZoomIn,
  onZoomOut,
  onCollapseAll,
  onToggleCollapseAll,
  isAllCollapsed = false,
  onRotateLayout,
  currentDirection,
  onCenterFirstItem,
  onExport,
  preferences,
  onUpdatePreferences,
  onSearch,
  searchResultCount,
  currentSearchIndex,
  onNextSearchResult,
  onPrevSearchResult,
  activeTool = 'pointer',
  onToggleTool,
}: BottomBarProps) {
  const [showPreferences, setShowPreferences] = useState(false);
  const [showSearchBox, setShowSearchBox] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [isFullscreen, setIsFullscreen] = useState(false);

  const searchInputRef = useRef<HTMLInputElement>(null);
  const preferencesRef = useRef<HTMLDivElement>(null);

  // Global hotkeys (Ctrl+F for search, Ctrl+1 for center)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'f') {
        e.preventDefault();
        setShowSearchBox(true);
        setTimeout(() => searchInputRef.current?.focus(), 50);
      }
      if ((e.ctrlKey || e.metaKey) && e.key === '1') {
        e.preventDefault();
        onCenterFirstItem();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onCenterFirstItem]);

  // Click outside preferences menu to close
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (preferencesRef.current && !preferencesRef.current.contains(e.target as Node)) {
        setShowPreferences(false);
      }
    };
    if (showPreferences) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [showPreferences]);

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {});
      setIsFullscreen(true);
    } else {
      document.exitFullscreen().catch(() => {});
      setIsFullscreen(false);
    }
  };

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setSearchQuery(val);
    onSearch(val);
  };

  const themes: { id: ThemeMode; name: string; color: string }[] = [
    { id: 'obsidian', name: 'Obsidian Dark', color: '#38bdf8' },
    { id: 'cyberpunk', name: 'Cyberpunk Neon', color: '#ec4899' },
    { id: 'midnight', name: 'Midnight Navy', color: '#60a5fa' },
    { id: 'light', name: 'Clean Light', color: '#0284c7' },
  ];

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 z-30 select-none">
      {/* Search Bar Popover (Ctrl+F) */}
      {showSearchBox && (
        <div className="flex items-center gap-2 px-3 py-1.5 bg-[#141923]/95 border border-[#2a3449] rounded-xl shadow-2xl backdrop-blur-md animate-in fade-in slide-in-from-bottom-2 duration-150">
          <Search className="w-4 h-4 text-cyan-400" />
          <input
            ref={searchInputRef}
            type="text"
            placeholder="Search nodes or functions..."
            value={searchQuery}
            onChange={handleSearchChange}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                if (e.shiftKey) onPrevSearchResult();
                else onNextSearchResult();
              }
              if (e.key === 'Escape') {
                setShowSearchBox(false);
              }
            }}
            className="w-52 bg-transparent text-sm text-slate-100 placeholder-slate-500 outline-none font-mono"
          />

          {searchResultCount > 0 && (
            <span className="text-xs font-mono text-cyan-400 px-1.5 py-0.5 bg-cyan-950/60 rounded border border-cyan-800/40">
              {currentSearchIndex + 1}/{searchResultCount}
            </span>
          )}

          {searchQuery && searchResultCount === 0 && (
            <span className="text-xs font-mono text-rose-400">0 results</span>
          )}

          <div className="flex items-center border-l border-slate-700 pl-1.5 gap-0.5">
            <button
              onClick={onPrevSearchResult}
              className="p-1 hover:bg-slate-800 text-slate-400 hover:text-slate-200 rounded"
              title="Previous (Shift+Enter)"
            >
              <ChevronUp className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={onNextSearchResult}
              className="p-1 hover:bg-slate-800 text-slate-400 hover:text-slate-200 rounded"
              title="Next (Enter)"
            >
              <ChevronDown className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => {
                setShowSearchBox(false);
                setSearchQuery('');
                onSearch('');
              }}
              className="p-1 hover:bg-slate-800 text-slate-400 hover:text-slate-200 rounded"
              title="Close (Esc)"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Main Bottom Toolbar */}
      <div className="relative flex items-center gap-1 px-3 py-1.5 bg-[#141923]/90 border border-[#2a3449] rounded-2xl shadow-2xl backdrop-blur-md">
        {/* Pointer / Select Tool */}
        <button
          onClick={() => onToggleTool?.('pointer')}
          className={`p-2 rounded-xl transition-all ${
            activeTool === 'pointer'
              ? 'bg-cyan-950 text-cyan-300 border border-cyan-800/80 shadow-sm'
              : 'hover:bg-[#232c3f] text-slate-400 hover:text-slate-200'
          }`}
          title="Pointer / Select Tool (V) - Click to select and inspect cards"
        >
          <MousePointer className="w-4 h-4" />
        </button>

        {/* Hand / Pan Tool */}
        <button
          onClick={() => onToggleTool?.('hand')}
          className={`p-2 rounded-xl transition-all ${
            activeTool === 'hand'
              ? 'bg-cyan-950 text-cyan-300 border border-cyan-800/80 shadow-sm ring-1 ring-cyan-400/40'
              : 'hover:bg-[#232c3f] text-slate-400 hover:text-slate-200'
          }`}
          title="Hand / Pan Tool (H or hold Spacebar) - Drag anywhere to pan canvas"
        >
          <Hand className="w-4 h-4" />
        </button>

        <div className="w-[1px] h-4 bg-slate-700 mx-1" />

        {/* Center Root Node */}
        <button
          onClick={onCenterFirstItem}
          className="p-2 hover:bg-[#232c3f] text-slate-300 hover:text-cyan-300 rounded-xl transition-colors group relative"
          title="Center first item (Ctrl+1)"
        >
          <Focus className="w-4 h-4" />
        </button>

        {/* Fit to Screen */}
        <button
          onClick={onFitView}
          className="p-2 hover:bg-[#232c3f] text-slate-300 hover:text-cyan-300 rounded-xl transition-colors"
          title="Fit view to screen"
        >
          <Minimize2 className="w-4 h-4" />
        </button>

        {/* Collapse / Expand Toggle */}
        <button
          onClick={onToggleCollapseAll || onCollapseAll}
          className="p-2 hover:bg-[#232c3f] text-slate-300 hover:text-cyan-300 rounded-xl transition-colors"
          title={isAllCollapsed ? 'Expand all branches' : 'Collapse all branches'}
        >
          {isAllCollapsed ? (
            <FolderPlus className="w-4 h-4 text-cyan-400" />
          ) : (
            <FolderMinus className="w-4 h-4 text-slate-300" />
          )}
        </button>

        <div className="w-[1px] h-4 bg-slate-700 mx-1" />

        {/* Zoom Out */}
        <button
          onClick={onZoomOut}
          className="p-2 hover:bg-[#232c3f] text-slate-300 hover:text-cyan-300 rounded-xl transition-colors"
          title="Zoom out"
        >
          <Minus className="w-4 h-4" />
        </button>

        {/* Zoom In */}
        <button
          onClick={onZoomIn}
          className="p-2 hover:bg-[#232c3f] text-slate-300 hover:text-cyan-300 rounded-xl transition-colors"
          title="Zoom in"
        >
          <Plus className="w-4 h-4" />
        </button>

        <div className="w-[1px] h-4 bg-slate-700 mx-1" />

        {/* Rotate Layout */}
        <button
          onClick={onRotateLayout}
          className="p-2 hover:bg-[#232c3f] text-slate-300 hover:text-cyan-300 rounded-xl transition-colors flex items-center gap-1"
          title={`Rotate layout (Current: ${currentDirection})`}
        >
          <RotateCw className="w-4 h-4" />
          <span className="text-[10px] font-mono text-cyan-400 font-semibold">{currentDirection}</span>
        </button>

        {/* Search Toggle */}
        <button
          onClick={() => {
            setShowSearchBox(!showSearchBox);
            if (!showSearchBox) {
              setTimeout(() => searchInputRef.current?.focus(), 50);
            }
          }}
          className={`p-2 rounded-xl transition-colors ${
            showSearchBox
              ? 'bg-cyan-950 text-cyan-300 border border-cyan-800'
              : 'hover:bg-[#232c3f] text-slate-300 hover:text-cyan-300'
          }`}
          title="Search nodes (Ctrl+F)"
        >
          <Search className="w-4 h-4" />
        </button>

        {/* Export Image */}
        <button
          onClick={onExport}
          className="p-2 hover:bg-[#232c3f] text-slate-300 hover:text-cyan-300 rounded-xl transition-colors"
          title="Export diagram image (PNG)"
        >
          <Download className="w-4 h-4" />
        </button>

        {/* Fullscreen */}
        <button
          onClick={toggleFullscreen}
          className="p-2 hover:bg-[#232c3f] text-slate-300 hover:text-cyan-300 rounded-xl transition-colors"
          title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
        >
          <Maximize className="w-4 h-4" />
        </button>

        <div className="w-[1px] h-4 bg-slate-700 mx-1" />

        {/* Master Controls & Preferences Dropdown */}
        <div className="relative" ref={preferencesRef}>
          <button
            onClick={() => setShowPreferences(!showPreferences)}
            className={`p-2 rounded-xl transition-colors ${
              showPreferences
                ? 'bg-cyan-950 text-cyan-300 border border-cyan-800'
                : 'hover:bg-[#232c3f] text-slate-300 hover:text-cyan-300'
            }`}
            title="Master Controls & Visual Layers"
          >
            <Sliders className="w-4 h-4" />
          </button>

          {/* Master Controls Popover */}
          {showPreferences && (
            <div className="absolute bottom-full right-0 mb-3 w-64 p-3 bg-[#141924]/95 border border-[#2a3449] rounded-2xl shadow-2xl backdrop-blur-xl space-y-3 text-xs select-none">
              <div className="flex items-center justify-between pb-1 border-b border-[#242d3f]">
                <span className="font-bold text-slate-300 uppercase tracking-wider text-[10px] flex items-center gap-1.5">
                  <Palette className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Master Theme & Styling</span>
                </span>
              </div>

              {/* Theme Picker */}
              <div className="grid grid-cols-2 gap-1.5">
                {themes.map((t) => {
                  const active = preferences.theme === t.id;
                  return (
                    <button
                      key={t.id}
                      onClick={() =>
                        onUpdatePreferences({
                          theme: t.id,
                          isLightMode: t.id === 'light',
                        })
                      }
                      className={`px-2 py-1.5 rounded-lg border text-[11px] font-medium flex items-center justify-between transition-all ${
                        active
                          ? 'bg-cyan-950 text-cyan-300 border-cyan-600 shadow-sm'
                          : 'bg-[#182030] text-slate-300 border-[#242d3f] hover:border-slate-500'
                      }`}
                    >
                      <span>{t.name}</span>
                      {active && <Check className="w-3 h-3 text-cyan-400" />}
                    </button>
                  );
                })}
              </div>

              {/* Link Curve Style */}
              <div className="space-y-1.5 pt-1">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block flex items-center gap-1">
                  <Spline className="w-3 h-3 text-cyan-400" />
                  <span>Link Connection Curves:</span>
                </span>
                <div className="grid grid-cols-3 gap-1">
                  {(['smoothstep', 'straight', 'bezier'] as ConnectionCurve[]).map((curve) => (
                    <button
                      key={curve}
                      onClick={() => onUpdatePreferences({ connectionCurve: curve })}
                      className={`py-1 rounded text-[10px] font-mono capitalize border ${
                        preferences.connectionCurve === curve
                          ? 'bg-cyan-950 text-cyan-300 border-cyan-500'
                          : 'bg-[#182030] text-slate-400 border-[#242d3f] hover:text-slate-200'
                      }`}
                    >
                      {curve}
                    </button>
                  ))}
                </div>
              </div>

              {/* Master Visual Layer Toggles */}
              <div className="space-y-1.5 pt-1 border-t border-[#242d3f]">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                  Link Visibility Layers:
                </span>

                {/* Green Uses Links */}
                <label className="flex items-center justify-between px-2 py-1 rounded bg-[#182030] hover:bg-[#202a3d] cursor-pointer">
                  <span className="text-emerald-300 flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-emerald-400" />
                    <span>🟢 Green Uses Links</span>
                  </span>
                  <input
                    type="checkbox"
                    checked={preferences.showGreenUses}
                    onChange={(e) => onUpdatePreferences({ showGreenUses: e.target.checked })}
                    className="rounded bg-slate-900 border-slate-700 text-emerald-500 focus:ring-0"
                  />
                </label>

                {/* Orange Used By Links */}
                <label className="flex items-center justify-between px-2 py-1 rounded bg-[#182030] hover:bg-[#202a3d] cursor-pointer">
                  <span className="text-amber-300 flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-amber-400" />
                    <span>🟠 Orange Used-By Links</span>
                  </span>
                  <input
                    type="checkbox"
                    checked={preferences.showOrangeUsedBy}
                    onChange={(e) => onUpdatePreferences({ showOrangeUsedBy: e.target.checked })}
                    className="rounded bg-slate-900 border-slate-700 text-amber-500 focus:ring-0"
                  />
                </label>

                {/* Hierarchy Tree Links */}
                <label className="flex items-center justify-between px-2 py-1 rounded bg-[#182030] hover:bg-[#202a3d] cursor-pointer">
                  <span className="text-slate-300">⚪ Tree Structure Lines</span>
                  <input
                    type="checkbox"
                    checked={preferences.showHierarchyLinks}
                    onChange={(e) => onUpdatePreferences({ showHierarchyLinks: e.target.checked })}
                    className="rounded bg-slate-900 border-slate-700 text-cyan-500 focus:ring-0"
                  />
                </label>

                {/* External Packages Badges */}
                <label className="flex items-center justify-between px-2 py-1 rounded bg-[#182030] hover:bg-[#202a3d] cursor-pointer">
                  <span className="text-purple-300 flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-purple-400" />
                    <span>🟣 External Packages</span>
                  </span>
                  <input
                    type="checkbox"
                    checked={preferences.showExternalPackages}
                    onChange={(e) => onUpdatePreferences({ showExternalPackages: e.target.checked })}
                    className="rounded bg-slate-900 border-slate-700 text-purple-500 focus:ring-0"
                  />
                </label>
              </div>

              {/* Spatial Overlays */}
              <div className="space-y-1.5 pt-1 border-t border-[#242d3f]">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                  Spatial Overlays:
                </span>

                {/* MiniMap Toggle */}
                <label className="flex items-center justify-between px-2 py-1 rounded bg-[#182030] hover:bg-[#202a3d] cursor-pointer">
                  <span className="text-slate-200 flex items-center gap-1.5">
                    <MapIcon className="w-3 h-3 text-cyan-400" />
                    <span>MiniMap Overview</span>
                  </span>
                  <input
                    type="checkbox"
                    checked={preferences.showMiniMap}
                    onChange={(e) => onUpdatePreferences({ showMiniMap: e.target.checked })}
                    className="rounded bg-slate-900 border-slate-700 text-cyan-500 focus:ring-0"
                  />
                </label>

                {/* Rulers Toggle */}
                <label className="flex items-center justify-between px-2 py-1 rounded bg-[#182030] hover:bg-[#202a3d] cursor-pointer">
                  <span className="text-slate-200 flex items-center gap-1.5">
                    <Ruler className="w-3 h-3 text-emerald-400" />
                    <span>Rulers Grid Overlay</span>
                  </span>
                  <input
                    type="checkbox"
                    checked={preferences.showRulers}
                    onChange={(e) => onUpdatePreferences({ showRulers: e.target.checked })}
                    className="rounded bg-slate-900 border-slate-700 text-cyan-500 focus:ring-0"
                  />
                </label>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
