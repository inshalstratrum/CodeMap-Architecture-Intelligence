import React, { useState, useEffect } from 'react';
import {
  X,
  SlidersHorizontal,
  Key,
  Cpu,
  FileText,
  Check,
  Loader2,
  Zap,
  Globe,
  AlertCircle,
  Clock,
} from 'lucide-react';
import { getConfig, saveConfig, testApiKey, TestKeyResult } from '../lib/apiClient';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const DEFAULT_GEMINI_MODELS = [
  'gemini-3.6-flash',
  'gemini-3.5-flash',
  'gemini-3.8-flash',
  'gemini-3.7-flash',
  'gemini-3.5-flash-lite',
  'gemini-flash-latest',
  'gemini-2.5-pro',
];

export const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose }) => {
  const [activeTab, setActiveTab] = useState<'general' | 'routing' | 'prompts'>('general');
  const [config, setConfig] = useState<Record<string, any>>({});
  const [isSaving, setIsSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  // Testing states
  const [testingKey, setTestingKey] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, TestKeyResult>>({});
  const [fetchedModels, setFetchedModels] = useState<string[]>(DEFAULT_GEMINI_MODELS);

  useEffect(() => {
    if (isOpen) {
      getConfig().then((cfg) => setConfig(cfg));
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSave = async () => {
    setIsSaving(true);
    const ok = await saveConfig(config);
    setIsSaving(false);
    if (ok) {
      setSavedSuccess(true);
      setTimeout(() => {
        setSavedSuccess(false);
        onClose();
      }, 1200);
    }
  };

  const updateKey = (provider: string, val: string) => {
    setConfig((prev) => ({
      ...prev,
      keys: {
        ...(prev.keys || {}),
        [provider]: val,
      },
    }));
  };

  const handleTestKey = async (keyName: string, keyValue: string, provider = 'gemini', endpointUrl = '') => {
    if (!keyValue.trim()) {
      setTestResults((prev) => ({
        ...prev,
        [keyName]: { ok: false, error: 'Key is empty' },
      }));
      return;
    }
    setTestingKey(keyName);
    const res = await testApiKey(keyValue.trim(), provider, endpointUrl);
    setTestResults((prev) => ({
      ...prev,
      [keyName]: res,
    }));
    if (res.ok && res.models && res.models.length > 0) {
      setFetchedModels(res.models);
    }
    setTestingKey(null);
  };

  return (
    <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="w-full max-w-2xl bg-[#111622] border border-[#242d3f] rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh] animate-in zoom-in-95 duration-150 select-none">
        {/* Modal Header */}
        <div className="px-5 py-4 border-b border-[#242d3f] bg-[#0e131d] flex items-center justify-between">
          <div className="flex items-center gap-2.5 text-cyan-400">
            <SlidersHorizontal className="w-4 h-4" />
            <h3 className="font-mono text-sm font-bold text-slate-100">
              CodeMap AI Settings & Agent Configuration
            </h3>
          </div>

          <button
            onClick={onClose}
            className="p-1 hover:bg-slate-800 text-slate-400 hover:text-slate-200 rounded-lg transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tab Selector */}
        <div className="flex items-center border-b border-[#242d3f] bg-[#0f141f] px-4 gap-1 text-xs">
          <button
            onClick={() => setActiveTab('general')}
            className={`flex items-center gap-1.5 px-3 py-2.5 border-b-2 font-medium transition-colors ${
              activeTab === 'general'
                ? 'border-cyan-400 text-cyan-300'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Key className="w-3.5 h-3.5" />
            <span>API & Providers</span>
          </button>

          <button
            onClick={() => setActiveTab('routing')}
            className={`flex items-center gap-1.5 px-3 py-2.5 border-b-2 font-medium transition-colors ${
              activeTab === 'routing'
                ? 'border-cyan-400 text-cyan-300'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Cpu className="w-3.5 h-3.5" />
            <span>Specialized Routing</span>
          </button>

          <button
            onClick={() => setActiveTab('prompts')}
            className={`flex items-center gap-1.5 px-3 py-2.5 border-b-2 font-medium transition-colors ${
              activeTab === 'prompts'
                ? 'border-cyan-400 text-cyan-300'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            <span>System Instructions</span>
          </button>
        </div>

        {/* Tab Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4 text-xs font-mono">
          {activeTab === 'general' && (
            <div className="space-y-4">
              <div>
                <label className="block text-slate-400 mb-1 font-semibold">Active AI Provider:</label>
                <select
                  value={config.provider || 'gemini'}
                  onChange={(e) => setConfig({ ...config, provider: e.target.value })}
                  className="w-full h-9 px-3 rounded-lg bg-[#0b0f17] border border-[#242d3f] text-slate-200 outline-none"
                >
                  <option value="gemini">Google Gemini (Recommended - Free Tier Available)</option>
                  <option value="anthropic">Anthropic Claude</option>
                  <option value="openai">OpenAI ChatGPT</option>
                </select>
              </div>

              {/* General Gemini Key with Test Connection */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="text-slate-400 font-semibold">General Gemini API Key:</label>
                  {testResults['gemini'] && (
                    <span className={`text-[10px] flex items-center gap-1 ${testResults['gemini'].ok ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {testResults['gemini'].ok ? (
                        <>
                          <Check className="w-3 h-3" />
                          <span>Connected ({testResults['gemini'].latencyMs}ms)</span>
                        </>
                      ) : (
                        <>
                          <AlertCircle className="w-3 h-3" />
                          <span>Failed: {testResults['gemini'].error?.slice(0, 35)}</span>
                        </>
                      )}
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="password"
                    value={config.keys?.gemini || ''}
                    onChange={(e) => updateKey('gemini', e.target.value)}
                    placeholder="AIzaSy..."
                    className="flex-1 h-9 px-3 rounded-lg bg-[#0b0f17] border border-[#242d3f] text-slate-200 outline-none focus:border-cyan-400"
                  />
                  <button
                    type="button"
                    onClick={() => handleTestKey('gemini', config.keys?.gemini || '')}
                    disabled={testingKey === 'gemini'}
                    className="h-9 px-3 rounded-lg bg-[#1a2232] hover:bg-[#232c3f] border border-[#2a3449] text-cyan-300 font-semibold flex items-center gap-1.5 transition-colors shrink-0"
                  >
                    {testingKey === 'gemini' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5" />}
                    <span>Test</span>
                  </button>
                </div>
              </div>

              {/* Model Choice for Gemini */}
              <div>
                <label className="block text-slate-400 mb-1 font-semibold">Default Gemini Model:</label>
                <select
                  value={config.models?.gemini || 'gemini-flash-latest'}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      models: { ...(config.models || {}), gemini: e.target.value },
                    })
                  }
                  className="w-full h-9 px-3 rounded-lg bg-[#0b0f17] border border-[#242d3f] text-slate-200 outline-none"
                >
                  {fetchedModels.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              </div>

              {/* Omni-Root / Custom Local Multi-API Endpoint */}
              <div className="p-3 bg-[#0d121c] border border-[#242d3f] rounded-xl space-y-2.5">
                <div className="flex items-center gap-2 text-cyan-400 font-bold">
                  <Globe className="w-3.5 h-3.5" />
                  <span>Omni-Root / Custom Multi-API Key (Optional)</span>
                </div>
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  If you use an Omni-Root proxy or local router aggregating free keys:
                </p>
                <div>
                  <label className="block text-slate-500 mb-1 text-[10px]">Custom Endpoint URL:</label>
                  <input
                    type="text"
                    value={config.omni_url || ''}
                    onChange={(e) => setConfig({ ...config, omni_url: e.target.value })}
                    placeholder="http://localhost:8000/v1/chat/completions"
                    className="w-full h-8 px-2.5 rounded-lg bg-[#0b0f17] border border-[#242d3f] text-slate-200 outline-none text-xs"
                  />
                </div>
                <div>
                  <label className="block text-slate-500 mb-1 text-[10px]">Omni-Root Key:</label>
                  <input
                    type="password"
                    value={config.omni_key || ''}
                    onChange={(e) => setConfig({ ...config, omni_key: e.target.value })}
                    placeholder="omni-..."
                    className="w-full h-8 px-2.5 rounded-lg bg-[#0b0f17] border border-[#242d3f] text-slate-200 outline-none text-xs"
                  />
                </div>
              </div>
            </div>
          )}

          {activeTab === 'routing' && (
            <div className="space-y-4">
              <div className="p-3 bg-cyan-950/40 border border-cyan-800/40 rounded-xl text-cyan-300 text-[11px] leading-relaxed">
                💡 <strong>Multi-Key Routing:</strong> Use dedicated API keys from different Google Cloud projects for Diagram Studio and Voice Assistant so they do not share rate limits.
              </div>

              {/* Diagram Studio Key */}
              <div className="p-3 bg-[#0d121c] border border-[#242d3f] rounded-xl space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-cyan-400 font-bold">1. Diagram Studio Model & Key</span>
                  {testResults['key_diagrams'] && (
                    <span className={`text-[10px] flex items-center gap-1 ${testResults['key_diagrams'].ok ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {testResults['key_diagrams'].ok ? '✅ Connected' : '❌ Failed'}
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="password"
                    value={config.key_diagrams || ''}
                    onChange={(e) => setConfig({ ...config, key_diagrams: e.target.value })}
                    placeholder="Leave blank to use General Key"
                    className="flex-1 h-8 px-2.5 rounded-lg bg-[#0b0f17] border border-[#242d3f] text-slate-200 outline-none text-xs"
                  />
                  <button
                    type="button"
                    onClick={() => handleTestKey('key_diagrams', config.key_diagrams || config.keys?.gemini || '')}
                    disabled={testingKey === 'key_diagrams'}
                    className="h-8 px-2.5 rounded-lg bg-[#1a2232] hover:bg-[#232c3f] border border-[#2a3449] text-cyan-300 text-xs flex items-center gap-1"
                  >
                    {testingKey === 'key_diagrams' ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
                    <span>Test</span>
                  </button>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Diagram Model Override:</label>
                  <select
                    value={config.model_diagrams || 'gemini-flash-latest'}
                    onChange={(e) => setConfig({ ...config, model_diagrams: e.target.value })}
                    className="w-full h-8 px-2.5 rounded-lg bg-[#0b0f17] border border-[#242d3f] text-slate-200 outline-none text-xs"
                  >
                    {fetchedModels.map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Voice Key */}
              <div className="p-3 bg-[#0d121c] border border-[#242d3f] rounded-xl space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-amber-400 font-bold">2. Voice & Chat Assistant Model & Key</span>
                  {testResults['key_voice'] && (
                    <span className={`text-[10px] flex items-center gap-1 ${testResults['key_voice'].ok ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {testResults['key_voice'].ok ? '✅ Connected' : '❌ Failed'}
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="password"
                    value={config.key_voice || ''}
                    onChange={(e) => setConfig({ ...config, key_voice: e.target.value })}
                    placeholder="Leave blank to use General Key"
                    className="flex-1 h-8 px-2.5 rounded-lg bg-[#0b0f17] border border-[#242d3f] text-slate-200 outline-none text-xs"
                  />
                  <button
                    type="button"
                    onClick={() => handleTestKey('key_voice', config.key_voice || config.keys?.gemini || '')}
                    disabled={testingKey === 'key_voice'}
                    className="h-8 px-2.5 rounded-lg bg-[#1a2232] hover:bg-[#232c3f] border border-[#2a3449] text-amber-300 text-xs flex items-center gap-1"
                  >
                    {testingKey === 'key_voice' ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
                    <span>Test</span>
                  </button>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 text-[11px]">Voice Model Override:</label>
                  <select
                    value={config.model_voice || 'gemini-2.5-flash-lite'}
                    onChange={(e) => setConfig({ ...config, model_voice: e.target.value })}
                    className="w-full h-8 px-2.5 rounded-lg bg-[#0b0f17] border border-[#242d3f] text-slate-200 outline-none text-xs"
                  >
                    {fetchedModels.map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'prompts' && (
            <div className="space-y-4">
              <div>
                <label className="block text-slate-400 mb-1 font-semibold">Diagram Studio System Rules:</label>
                <textarea
                  rows={4}
                  value={config.system_diagrams || ''}
                  onChange={(e) => setConfig({ ...config, system_diagrams: e.target.value })}
                  placeholder="Custom architectural principles or formatting instructions..."
                  className="w-full p-2.5 rounded-lg bg-[#0b0f17] border border-[#242d3f] text-slate-200 outline-none resize-none leading-relaxed"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1 font-semibold">Voice & Chat Persona / Instructions:</label>
                <textarea
                  rows={4}
                  value={config.system_voice || ''}
                  onChange={(e) => setConfig({ ...config, system_voice: e.target.value })}
                  placeholder="Tone, analogies, language preference (e.g. Urdu/English), patient teacher rules..."
                  className="w-full p-2.5 rounded-lg bg-[#0b0f17] border border-[#242d3f] text-slate-200 outline-none resize-none leading-relaxed"
                />
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-5 py-3 border-t border-[#242d3f] bg-[#0e131d] flex items-center justify-between">
          <span className="text-[11px] text-slate-500 font-mono">
            Config is saved to <code>.codemap/config.json</code>
          </span>

          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="px-3 py-1.5 rounded-lg bg-[#1a2232] hover:bg-[#232c3f] border border-[#2a3449] text-slate-300 text-xs transition-colors"
            >
              Cancel
            </button>

            <button
              onClick={handleSave}
              disabled={isSaving}
              className="px-4 py-1.5 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-black font-semibold text-xs flex items-center gap-1.5 transition-colors shadow-lg shadow-cyan-500/20"
            >
              {isSaving ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : savedSuccess ? (
                <Check className="w-3.5 h-3.5 text-emerald-950" />
              ) : null}
              <span>{savedSuccess ? 'Saved!' : 'Save Settings'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
