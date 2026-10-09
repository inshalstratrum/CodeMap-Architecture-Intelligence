export interface ProjectNode {
  id: string;
  rel: string;
  name: string;
  path: string;
  isDir: boolean;
  parentRel: string;
  lang: string;
  role: string;
  lines: number;
  size: number;
  imports: string[];
  external: string[];
  importedBy: string[];
  defines: string[];
  endpoints: string[];
  childrenCount: number;
  summary: string;
}

export interface CategorizedFileItem {
  rel: string;
  name: string;
  path: string;
  folder: string;
}

export interface ProjectData {
  name: string;
  rootPath: string;
  totalFiles: number;
  totalNodes: number;
  edgesCount: number;
  languages: { name: string; value: number }[];
  jsonFiles?: CategorizedFileItem[];
  categoryFiles?: {
    json: CategorizedFileItem[];
    typescript: CategorizedFileItem[];
    html_css: CategorizedFileItem[];
    python: CategorizedFileItem[];
    markdown: CategorizedFileItem[];
  };
  nodes: ProjectNode[];
}

export interface DiagramEntry {
  id: string;
  type: string;
  title: string;
  mermaid: string;
  explanation: string;
  timestamp?: string;
  model?: string;
}

export interface TestKeyResult {
  ok: boolean;
  latencyMs?: number;
  models?: string[];
  error?: string;
}

const API_BASE = '';

export async function scanProject(path: string, showHidden = false, skipJunk = true): Promise<ProjectData> {
  const res = await fetch(`${API_BASE}/api/scan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path, showHidden, skipJunk }),
  });
  const data = await res.json();
  if (!res.ok || !data.ok) throw new Error(data.error || 'Scan failed');
  return data.project;
}

export async function getProject(): Promise<ProjectData | null> {
  try {
    const res = await fetch(`${API_BASE}/api/project`);
    const data = await res.json();
    return data.ok ? data.project : null;
  } catch {
    return null;
  }
}

export async function browseFolder(): Promise<string> {
  try {
    const res = await fetch(`${API_BASE}/api/browse`);
    const data = await res.json();
    return data.path || '';
  } catch {
    return '';
  }
}

export async function explainNode(rel: string, isFile: boolean): Promise<string> {
  const res = await fetch(`${API_BASE}/api/explain`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rel, isFile }),
  });
  const data = await res.json();
  if (!res.ok || !data.ok) throw new Error(data.error || 'Explanation failed');
  return data.explanation;
}

export async function generateDiagram(rel: string, isFile: boolean, type: string): Promise<DiagramEntry> {
  const res = await fetch(`${API_BASE}/api/generate-diagram`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rel, isFile, type }),
  });
  const data = await res.json();
  if (!res.ok || !data.ok) throw new Error(data.error || 'Diagram generation failed');
  return data.entry || {
    id: `${rel}_${type}_${Date.now()}`,
    type: data.type,
    title: data.title,
    mermaid: data.mermaid,
    explanation: data.explanation,
  };
}

export async function generateDiagramFromText(
  text: string,
  type = 'system',
  title = 'Custom Architecture'
): Promise<DiagramEntry> {
  const res = await fetch(`${API_BASE}/api/generate-diagram-from-text`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, type, title }),
  });
  const data = await res.json();
  if (!res.ok || !data.ok) throw new Error(data.error || 'Diagram generation failed');
  return data.entry || {
    id: `@custom_${type}_${Date.now()}`,
    type: data.type,
    title: data.title,
    mermaid: data.mermaid,
    explanation: data.explanation,
  };
}

export async function saveDiagramToVault(
  mermaid: string,
  explanation = '',
  title = 'Custom Diagram',
  rel = '@custom',
  isFile = false,
  type = 'custom'
): Promise<DiagramEntry> {
  const res = await fetch(`${API_BASE}/api/vault/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rel, isFile, type, title, mermaid, explanation }),
  });
  const data = await res.json();
  if (!res.ok || !data.ok) throw new Error(data.error || 'Save to vault failed');
  return data.entry;
}

export async function getVaultItems(): Promise<string[]> {
  try {
    const res = await fetch(`${API_BASE}/api/vault`);
    const data = await res.json();
    return data.ok ? data.items : [];
  } catch {
    return [];
  }
}

export async function getVaultHistory(rel: string, isFile: boolean): Promise<DiagramEntry[]> {
  try {
    const res = await fetch(`${API_BASE}/api/vault/items`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rel, isFile }),
    });
    const data = await res.json();
    return data.ok ? data.diagrams : [];
  } catch {
    return [];
  }
}

export async function fetchFileContent(filePath: string): Promise<string> {
  const res = await fetch(`${API_BASE}/api/file-content?path=${encodeURIComponent(filePath)}`);
  const data = await res.json();
  if (!res.ok || !data.ok) throw new Error(data.error || 'Failed to read file');
  return data.content;
}

export async function testApiKey(key: string, provider = 'gemini', endpointUrl = ''): Promise<TestKeyResult> {
  try {
    const res = await fetch(`${API_BASE}/api/test-key`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key, provider, endpointUrl }),
    });
    return await res.json();
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

export async function getConfig(): Promise<Record<string, any>> {
  try {
    const res = await fetch(`${API_BASE}/api/config`);
    return await res.json();
  } catch {
    return {};
  }
}

export async function saveConfig(cfg: Record<string, any>): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cfg),
    });
    const data = await res.json();
    return !!data.ok;
  } catch {
    return false;
  }
}

export interface SearchResultItem {
  rel: string;
  name: string;
  isDir: boolean;
  lang: string;
  role: string;
  defines?: string[];
  matchType: string;
}

export async function openInSystem(path = '', rel = ''): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/open-system`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path, rel }),
    });
    const data = await res.json();
    return !!data.ok;
  } catch {
    return false;
  }
}

export async function searchCodebase(query: string): Promise<SearchResultItem[]> {
  try {
    const res = await fetch(`${API_BASE}/api/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    });
    const data = await res.json();
    return data.ok ? data.results : [];
  } catch {
    return [];
  }
}

export async function exportDiagramHtml(
  rel: string,
  isFile: boolean,
  title: string,
  mermaid: string,
  explanation: string,
  type = 'system',
  openFolder = true
): Promise<string> {
  const res = await fetch(`${API_BASE}/api/diagram/export-html`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rel, isFile, title, mermaid, explanation, type, openFolder }),
  });
  const data = await res.json();
  if (!res.ok || !data.ok) throw new Error(data.error || 'Failed to export HTML');
  return data.path;
}
