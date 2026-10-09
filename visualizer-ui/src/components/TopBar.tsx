import React, { useState } from 'react';
import {
  FolderOpen,
  Play,
  RotateCcw,
  BookOpen,
  SlidersHorizontal,
  PanelRightClose,
  PanelRightOpen,
  Loader2,
  Sparkles,
} from 'lucide-react';
import { browseFolder } from '../lib/apiClient';

interface TopBarProps {
  currentPath: string;
  onPathChange: (path: string) => void;
  onScan: (path: string, showHidden: boolean, skipJunk: boolean) => void;
  isScanning: boolean;
  showHidden: boolean;
  onToggleShowHidden: (val: boolean) => void;
  skipJunk: boolean;
  onToggleSkipJunk: (val: boolean) => void;
  showFiles: boolean;
  onToggleShowFiles: (val: boolean) => void;
  onToggleLibrary: () => void;
  isLibraryOpen: boolean;
  onToggleInspector: () => void;
  isInspectorOpen: boolean;
  onOpenSettings: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({
  currentPath,
  onPathChange,
  onScan,
  isScanning,
  showHidden,
  onToggleShowHidden,
  skipJunk,
  onToggleSkipJunk,
  showFiles,
  onToggleShowFiles,
  onToggleLibrary,
  isLibraryOpen,
  onToggleInspector,
  isInspectorOpen,
  onOpenSettings,
}) => {
  const [inputVal, setInputVal] = useState(currentPath);

  const handleBrowse = async () => {
    const chosen = await browseFolder();
    if (chosen) {
      setInputVal(chosen);
      onPathChange(chosen);
    }
  };

  const handleScanSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputVal.trim()) {
      onScan(inputVal.trim(), showHidden, skipJunk);
    }
  };

  return (
    <header className="h-14 bg-[#111622] border-b border-[#242d3f] px-4 flex items-center justify-between gap-3 select-none z-20 shrink-0">
      {/* Brand & Folder Input Form */}
      <div className="flex items-center gap-3 flex-1 max-w-4xl">
        <div className="flex items-center gap-2 font-mono font-bold text-sm tracking-wide text-slate-100 shrink-0">
          <span className="p-1 rounded-lg bg-gradient-to-tr from-cyan-500 to-blue-600 text-black">
            <Sparkles className="w-4 h-4" />
          </span>
          <span>CodeMap <span className="text-cyan-400 font-normal">React</span></span>
        </div>

        <form onSubmit={handleScanSubmit} className="flex items-center gap-2 flex-1">
          <div className="relative flex-1">
            <input
              type="text"
              value={inputVal}
              onChange={(e) => {
                setInputVal(e.target.value);
                onPathChange(e.target.value);
              }}
              placeholder="Paste or browse codebase folder path..."
              className="w-full h-9 pl-3 pr-8 rounded-lg bg-[#0b0f17] border border-[#2a3449] text-xs font-mono text-slate-200 placeholder-slate-500 outline-none focus:border-cyan-400/60 focus:ring-1 focus:ring-cyan-400/40 transition-all"
            />
            {inputVal && (
              <button
                type="button"
                onClick={() => setInputVal('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 text-xs"
              >
                ✕
              </button>
            )}
          </div>

          <button
            type="button"
            onClick={handleBrowse}
            className="h-9 px-3 rounded-lg bg-[#1a2232] hover:bg-[#232c3f] border border-[#2a3449] text-slate-200 text-xs font-medium flex items-center gap-1.5 transition-colors shrink-0"
            title="Browse folder on your PC"
          >
            <FolderOpen className="w-3.5 h-3.5 text-cyan-400" />
            <span>Browse…</span>
          </button>

          <button
            type="submit"
            disabled={isScanning || !inputVal.trim()}
            className={`h-9 px-4 rounded-lg font-medium text-xs flex items-center gap-1.5 transition-all shrink-0 ${
              isScanning
                ? 'bg-cyan-900 text-cyan-200 cursor-wait'
                : 'bg-cyan-500 hover:bg-cyan-400 text-black font-semibold shadow-lg shadow-cyan-500/20 active:scale-95'
            }`}
          >
            {isScanning ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Scanning…</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>Scan</span>
              </>
            )}
          </button>
        </form>
      </div>

      {/* Options & Action Toggles */}
      <div className="flex items-center gap-3">
        <div className="hidden lg:flex items-center gap-3 text-xs text-slate-400 border-r border-[#242d3f] pr-3">
          <label className="flex items-center gap-1.5 cursor-pointer hover:text-slate-200">
            <input
              type="checkbox"
              checked={showFiles}
              onChange={(e) => onToggleShowFiles(e.target.checked)}
              className="rounded bg-slate-900 border-slate-700 text-cyan-500 focus:ring-0"
            />
            <span>Show files</span>
          </label>

          <label className="flex items-center gap-1.5 cursor-pointer hover:text-slate-200">
            <input
              type="checkbox"
              checked={showHidden}
              onChange={(e) => onToggleShowHidden(e.target.checked)}
              className="rounded bg-slate-900 border-slate-700 text-cyan-500 focus:ring-0"
            />
            <span>Show hidden</span>
          </label>

          <label className="flex items-center gap-1.5 cursor-pointer hover:text-slate-200">
            <input
              type="checkbox"
              checked={skipJunk}
              onChange={(e) => onToggleSkipJunk(e.target.checked)}
              className="rounded bg-slate-900 border-slate-700 text-cyan-500 focus:ring-0"
            />
            <span>Skip junk</span>
          </label>
        </div>

        <div className="flex items-center gap-2">
          {/* Library Button */}
          <button
            onClick={onToggleLibrary}
            className={`h-9 px-3 rounded-lg border text-xs flex items-center gap-1.5 transition-colors ${
              isLibraryOpen
                ? 'bg-cyan-950/80 border-cyan-800 text-cyan-300'
                : 'bg-[#1a2232] border-[#2a3449] text-slate-300 hover:bg-[#232c3f]'
            }`}
            title="Diagram Library & Vault"
          >
            <BookOpen className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Library</span>
          </button>

          {/* AI Settings */}
          <button
            onClick={onOpenSettings}
            className="h-9 px-3 rounded-lg bg-[#1a2232] hover:bg-[#232c3f] border border-[#2a3449] text-slate-300 hover:text-cyan-300 text-xs flex items-center gap-1.5 transition-colors"
            title="Configure AI Models & Keys"
          >
            <SlidersHorizontal className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">AI Settings</span>
          </button>

          {/* Inspector Panel Toggle */}
          <button
            onClick={onToggleInspector}
            className={`h-9 px-3 rounded-lg border text-xs flex items-center gap-1.5 transition-colors ${
              isInspectorOpen
                ? 'bg-cyan-950/80 border-cyan-800 text-cyan-300'
                : 'bg-[#1a2232] border-[#2a3449] text-slate-300 hover:bg-[#232c3f]'
            }`}
            title="Inspector & AI Details"
          >
            {isInspectorOpen ? (
              <PanelRightClose className="w-3.5 h-3.5" />
            ) : (
              <PanelRightOpen className="w-3.5 h-3.5" />
            )}
            <span className="hidden sm:inline">Details</span>
          </button>
        </div>
      </div>
    </header>
  );
};
