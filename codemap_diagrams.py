"""
CodeMap Diagrams - Advanced Visual Diagram Studio & Vault System
-----------------------------------------------------------------
Designed specifically for non-programmers and vibe coders:
  * Multi-type Mermaid diagram generation via AI (System, Flow, Sequence, State, Table, Relations)
  * Beginner-friendly real-world analogy and translation prompts
  * Permanent Visuals Vault with versioning per file/folder (never overwrites previous diagrams)
  * Native Tkinter Canvas diagram renderer (pan, zoom, styled cards, connecting arrows)
  * Interactive standalone HTML/SVG exporter with Mermaid.js
  * Full-control export (single diagram, item history, or entire project vault)

Only the Python standard library is used.
"""

import datetime
import hashlib
import html
import json
import os
import posixpath
import re
import subprocess
import tempfile
import threading
import urllib.parse
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
from tkinter import font as tkfont

# Dedicated storage directory inside the project folder:
APP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".codemap")
os.makedirs(APP_DIR, exist_ok=True)
VAULT_DIR = os.path.join(APP_DIR, "visuals_vault")

# --------------------------------------------------------------------------
# Diagram Type Specifications
# --------------------------------------------------------------------------
DIAGRAM_TYPES = {
    "system": {
        "id": "system",
        "label": "🏗 System Architecture",
        "short": "System",
        "syntax": "flowchart TD",
        "desc": "High-level overview: what this component connects to, what it receives, and what it outputs.",
        "icon": "🏗",
    },
    "flow": {
        "id": "flow",
        "label": "🔄 Logic & Data Flow",
        "short": "Flow",
        "syntax": "flowchart LR",
        "desc": "Step-by-step path: what happens when data arrives, how it gets transformed, and where it goes.",
        "icon": "🔄",
    },
    "sequence": {
        "id": "sequence",
        "label": "⏱ Sequence & Interactions",
        "short": "Sequence",
        "syntax": "sequenceDiagram",
        "desc": "Time-ordered interaction: who speaks to whom (User -> UI -> Code -> Database/API).",
        "icon": "⏱",
    },
    "state": {
        "id": "state",
        "label": "🚦 State & Lifecycle",
        "short": "State",
        "syntax": "stateDiagram-v2",
        "desc": "Status transitions: idle -> loading -> success / error, and what triggers each state.",
        "icon": "🚦",
    },
    "table": {
        "id": "table",
        "label": "📊 Beginner Visual Summary & Table",
        "short": "Summary Table",
        "syntax": "flowchart TD",
        "desc": "Non-coder breakdown with real-world analogy, responsibilities table, and failure impact.",
        "icon": "📊",
    },
    "relations": {
        "id": "relations",
        "label": "🗺 Entities & Relationships",
        "short": "Entities",
        "syntax": "classDiagram",
        "desc": "Key objects, data structures, and how they relate to each other.",
        "icon": "🗺",
    },
    "densetree": {
        "id": "densetree",
        "label": "🌲 Dense Tree Hierarchy",
        "short": "Dense Tree",
        "syntax": "flowchart TD",
        "desc": "Compact multi-level folder and file tree hierarchy showing structural organization, parent-child nesting, and file roles.",
        "icon": "🌲",
    },
}

DIAGRAM_ORDER = ["system", "densetree", "flow", "sequence", "state", "table", "relations"]


def recommend_diagram_types(project, rel, is_file):
    """
    Analyzes project structure and returns an ordered list of diagram type keys
    optimized for this specific file or folder.
    First element is the primary recommended diagram.
    """
    if not project:
        return ["system", "flow", "table"]

    if not is_file:
        if not rel:
            return ["system", "flow", "table"]
        r_lower = rel.lower()
        files = project.files_under(rel) if hasattr(project, "files_under") else []
        has_endpoints = any(project.info.get(f, {}).get("endpoints") for f in files)
        has_ui = any(f.endswith((".tsx", ".jsx", ".vue", ".html")) or "/ui/" in f or "/components/" in f for f in files)
        has_data = any("/models/" in f or "/entities/" in f or "/data/" in f or "/schema/" in f or f.endswith((".prisma", ".sql")) for f in files)
        has_state = any("store" in f.lower() or "state" in f.lower() or "reducer" in f.lower() for f in files)

        if has_endpoints or "api" in r_lower or "route" in r_lower or "server" in r_lower:
            return ["sequence", "flow", "system", "table"]
        if has_state:
            return ["state", "flow", "system", "table"]
        if has_data:
            return ["relations", "table", "flow", "system"]
        if has_ui or "client" in r_lower or "frontend" in r_lower or "component" in r_lower:
            return ["flow", "system", "state", "table"]
        return ["system", "flow", "table", "sequence"]
    else:
        info = project.info.get(rel, {}) if hasattr(project, "info") else {}
        base = posixpath.basename(rel).lower()
        endpoints = info.get("endpoints", [])
        role = info.get("role", "").lower()

        if endpoints or "route" in base or "api" in base or "controller" in base:
            return ["sequence", "flow", "system", "table"]
        if "state" in base or "store" in base or "reducer" in base or "lifecycle" in base:
            return ["state", "flow", "table", "system"]
        if "type" in base or "model" in base or "schema" in base or "entity" in base or rel.endswith((".prisma", ".sql")):
            return ["relations", "table", "flow", "system"]
        if rel.endswith((".tsx", ".jsx", ".vue")) or "component" in role:
            return ["flow", "state", "system", "table"]
        if role.startswith("entry point") or base in ("main.py", "index.ts", "app.tsx", "server.js"):
            return ["system", "flow", "sequence", "table"]
        return ["flow", "table", "system", "relations"]

# --------------------------------------------------------------------------
# Beginner Prompting Instruction
# --------------------------------------------------------------------------
BEGINNER_SYSTEM_PROMPT = """You are an expert software visualizer and teacher explaining software architecture to a NON-PROGRAMMER (a creator who uses AI 'vibe coding' tools and does not write or read complex code syntax).

CRITICAL AUDIENCE & DIAGRAM RULES:
1. EXPLAIN USING REAL-WORLD ANALOGIES (e.g. like an architect's blueprint, a restaurant kitchen, a postal sorting office, or a train dispatch center).
2. NO CODE JARGON: Avoid abstract computer science jargon. When a technical word is unavoidable, explain it immediately in parentheses using simple everyday English.
3. VISUAL CLARITY & CLEAN ARCHITECTURE:
   - FOCUS ON THE BIG PICTURE (6 TO 10 NODES MAXIMUM): A beginner gets overwhelmed by 25+ nodes. Select ONLY the 6 to 10 most essential components, steps, or files.
   - TOP-DOWN DIRECTION (flowchart TD): Always default to top-down flow (`flowchart TD`) unless generating a sequenceDiagram or stateDiagram. Top-down flows fit desktop screens and scroll naturally without stretching horizontally.
   - SINGLE-LEVEL SUBGRAPHS ONLY (MAX 2-3 GROUPS): NEVER nest a subgraph inside another subgraph. Group related items into at most 2 or 3 flat, side-by-side or sequential subgraphs (e.g. `subgraph "1. User & Screens"`, `subgraph "2. Core Logic"`, `subgraph "3. Storage & Output"`).
   - CLEAR FORWARD FLOW: Arrows must move cleanly forward from trigger/input to processing to result. DO NOT create a tangled spiderweb of circular or bidirectional arrows between every node.
   - QUOTE ALL NODE LABELS: Always write `id["Friendly Name\n(optionalFile.ts)"]`. Never leave brackets unquoted.
   - SHORT ACTION ARROWS: Use short 2-4 word action labels on arrows (e.g. `A -- "Sends request" --> B`).
4. OUTPUT FORMAT:
   Always structure your response in exactly two parts:
   Part 1: Exactly one Mermaid code block starting with ```mermaid and ending with ```.
   Part 2: A clear, bulleted PLAIN ENGLISH GUIDE with these sections:
   - REAL-WORLD ANALOGY (1-2 sentences: what real-life object or person is this like?)
   - HOW TO READ THIS DIAGRAM (step-by-step walkthrough of the diagram nodes)
   - WHY THIS MATTERS (what would break from the user's perspective if this file stopped working)
"""


def build_diagram_prompt(project, rel, diag_type="system"):
    spec = DIAGRAM_TYPES.get(diag_type, DIAGRAM_TYPES["system"])
    node = project.nodes.get(rel) if (hasattr(project, "nodes") and project.nodes) else None
    is_file = bool(rel) and node is not None and not getattr(node, "is_dir", False)
    is_root = rel == "" or node is None

    if is_file:
        info = project.info.get(rel, {}) if (hasattr(project, "info") and project.info) else {}
        try:
            with open(node.path, "rb") as f:
                content = f.read(18000).decode("utf-8", errors="replace")
        except Exception:
            content = "(File content could not be read)"

        ext_lower = node.ext.lower()

        dense_rules = ""
        if diag_type == "densetree":
            dense_rules = (
                "- DENSE TREE FOCUS: Create a compact hierarchical tree (flowchart TD) showing the internal module/class/function or key/value breakdown.\n"
                "- Structure as a top-to-bottom branching tree: Target --> [Key Sections/Modules] --> [Items/Properties].\n"
            )

        if ext_lower == ".json":
            json_meta = "\n".join(f"- {m}" for m in info.get("meta", [])) or "- Standard JSON Data Structure"
            return f"""{BEGINNER_SYSTEM_PROMPT}

TARGET TO VISUALIZE:
JSON File: {rel}
Role in Project: {info.get('role', 'Configuration / Data Object')}
Metadata Summary:
{json_meta}

REQUESTED DIAGRAM TYPE: {spec['label']} ({spec['syntax']})
Specific Goal: {spec['desc']}

FILE CONTENT PREVIEW:
```json
{content}
```

Instructions for this diagram:
- This is a JSON data or configuration file.
- Generate a clear {spec['syntax']} diagram (flowchart TD or classDiagram) visualizing the primary data objects, nested keys, configurations, schemas, and data relationships.
- Structure it so a non-programmer can immediately see the hierarchical data shape, what key sections exist, and what values or sub-objects are configured.
- Avoid cluttered or deeply nested subgraphs. Use 6 to 10 key nodes representing the top-level keys and primary structured children.
{dense_rules}- Follow with the plain-English beginner explanation sections (The Big Picture, How It Connects, Key Components, Recommendations).
"""

        elif ext_lower in (".md", ".markdown"):
            return f"""{BEGINNER_SYSTEM_PROMPT}

TARGET TO VISUALIZE:
Documentation File: {rel}
Role in Project: {info.get('role', 'Documentation / System Specification')}
Document Summary: {info.get('doc', 'Markdown Document')}

REQUESTED DIAGRAM TYPE: {spec['label']} ({spec['syntax']})
Specific Goal: {spec['desc']}

DOCUMENT CONTENT PREVIEW:
```markdown
{content}
```

Instructions for this diagram:
- This is a Markdown documentation and system specification file.
- Carefully extract the conceptual architecture, workflow phases, execution steps, tool interactions, or user journeys documented in this text.
- Generate a clean {spec['syntax']} diagram with 6 to 10 descriptive nodes illustrating the system, workflow, or architecture described in the document.
- Ensure the flow reads logically from left-to-right (LR) or top-to-bottom (TD).
{dense_rules}- Follow with the plain-English beginner explanation sections (The Big Picture, How It Connects, Key Components, Recommendations).
"""

        imps = ", ".join(info.get("imports", [])[:20]) or "none (standalone)"
        by = ", ".join(project.imported_by.get(rel, [])[:20]) or "none (not directly imported)"
        ext = ", ".join(info.get("external", [])[:15]) or "none"
        defs = ", ".join(info.get("defines", [])[:15]) or "none"

        return f"""{BEGINNER_SYSTEM_PROMPT}

TARGET TO VISUALIZE:
File: {rel}
Language: {info.get('lang', 'Unknown')}
Role in Project: {info.get('role', 'Code Component')}
Functions/Classes it defines: {defs}
Files this file depends on: {imps}
Files that depend on this file: {by}
External libraries: {ext}

REQUESTED DIAGRAM TYPE: {spec['label']} ({spec['syntax']})
Specific Goal: {spec['desc']}

FILE CODE PREVIEW:
```
{content}
```

Instructions for this diagram:
- Create a valid {spec['syntax']} diagram with 6 to 10 nodes that makes this file's purpose and connections crystal clear to a non-programmer.
- Enforce clean forward flow from input to outcome.
{dense_rules}- If using subgraphs, use at most 2 flat (non-nested) groups.
- Follow with the plain-English explanation sections.
"""
    else:
        # Folder or whole project
        scope = project.files_under(rel)
        st = project_stats_light(project, rel)
        target_name = f"the whole project '{project.name}'" if is_root else f"the folder '{rel}'"
        file_list = []
        for f in scope[:40]:
            inf = project.info.get(f, {})
            file_list.append(f"- {f}: {inf.get('role', 'Code file')} (uses: {len(inf.get('imports', []))}, used by: {len(project.imported_by.get(f, []))})")
        files_str = "\n".join(file_list) or "Empty folder"

        dense_rules = ""
        if diag_type == "densetree":
            dense_rules = (
                "- DENSE TREE FOCUS: Create a multi-level folder and file tree hierarchy using flowchart TD.\n"
                "- Show the root folder branching into main subfolders, which branch into key files with their roles.\n"
                "- Keep the tree strictly downward branching so it reads like an interactive folder tree diagram.\n"
            )

        return f"""{BEGINNER_SYSTEM_PROMPT}

TARGET TO VISUALIZE:
Target: {target_name}
Total Files: {st['files']}
Languages: {st['langs']}
Top Key Files: {', '.join(st['top_files'])}

FILES IN THIS SCOPE:
{files_str}

REQUESTED DIAGRAM TYPE: {spec['label']} ({spec['syntax']})
Specific Goal: {spec['desc']}

Instructions for this diagram:
- Create a valid {spec['syntax']} diagram focusing on the 6 to 10 most essential components and flows inside {target_name}.
{dense_rules}- Group related items into at most 2 or 3 flat, non-nested subgraphs (e.g., "User Interface", "Core Logic", "Data Storage").
- Maintain a clean, readable forward flow without tangled crisscrossing arrows.
- Follow with the plain-English beginner explanation sections.
"""


def build_custom_text_diagram_prompt(custom_text, diag_type="system", title="Custom Architecture"):
    spec = DIAGRAM_TYPES.get(diag_type, DIAGRAM_TYPES["system"])
    dense_rules = ""
    if diag_type == "densetree":
        dense_rules = (
            "- DENSE TREE FOCUS: Create a compact hierarchical tree (flowchart TD) showing modules, components, subcomponents, and procedures.\n"
            "- Structure as a top-to-bottom branching tree with clean child nodes.\n"
        )

    return f"""{BEGINNER_SYSTEM_PROMPT}

TARGET TO VISUALIZE:
Custom Architecture / Description: {title}
Description & System Requirements:
```
{custom_text[:14000]}
```

REQUESTED DIAGRAM TYPE: {spec['label']} ({spec['syntax']})
Specific Goal: {spec['desc']}

Instructions for this diagram:
- Carefully analyze the provided description, user requirements, 3D visualizer pipelines, workflows, or AI organizational structure.
- Create a valid, clean {spec['syntax']} diagram with 6 to 12 clear, descriptive nodes that turns the description into an intuitive, crystal-clear visual model.
- Maintain a clean, forward-flowing structure without tangled crisscrossing connections.
{dense_rules}- If using subgraphs, use at most 2 or 3 flat, non-nested subgraphs.
- Follow with the plain-English beginner explanation sections (The Big Picture, How It Connects, Key Components, Recommendations).
"""


def project_stats_light(project, rel):
    scope = project.files_under(rel)
    langs = {}
    for f in scope:
        lang = project.info.get(f, {}).get("lang", "Other")
        langs[lang] = langs.get(lang, 0) + 1
    top_files = sorted(scope, key=lambda f: len(project.imported_by.get(f, [])), reverse=True)[:6]
    lang_str = ", ".join(f"{k} ({v})" for k, v in sorted(langs.items(), key=lambda x: x[1], reverse=True)[:4])
    return {"files": len(scope), "langs": lang_str or "Unknown", "top_files": top_files}


def extract_mermaid_and_text(ai_response):
    """Parses raw AI response into (mermaid_code, explanation_text)."""
    m = re.search(r"```(?:mermaid)?\s*\n(.*?)\n```", ai_response, re.DOTALL | re.IGNORECASE)
    if m:
        mermaid_code = m.group(1).strip()
        # Remove mermaid block from response for the explanation text
        explanation = (ai_response[:m.start()] + "\n" + ai_response[m.end():]).strip()
    else:
        # Check if response begins directly with a mermaid diagram declaration
        lines = ai_response.strip().splitlines()
        first_line = lines[0].strip().lower() if lines else ""
        if any(first_line.startswith(k) for k in ("graph ", "flowchart ", "sequencediagram", "statediagram", "classdiagram", "erdiagram")):
            mermaid_code = ai_response.strip()
            explanation = "Visual Diagram generated."
        else:
            mermaid_code = ""
            explanation = ai_response.strip()
    return mermaid_code, explanation


# --------------------------------------------------------------------------
# Visuals Vault - Dedicated Permanent Storage System
# --------------------------------------------------------------------------
class DiagramVault:
    """
    Manages saved diagrams for each file and folder in a project.
    Every file/folder has a dedicated history/vault.
    New diagrams are appended without deleting or overwriting previous versions.
    """

    def __init__(self, root_path):
        self.root_path = os.path.abspath(root_path)
        self.key = hashlib.sha1(self.root_path.lower().encode("utf-8")).hexdigest()[:16]
        os.makedirs(VAULT_DIR, exist_ok=True)
        self.filepath = os.path.join(VAULT_DIR, f"{self.key}.json")
        self.lock = threading.Lock()
        self.data = self._load()

    def _load(self):
        try:
            if os.path.exists(self.filepath):
                with open(self.filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {"project_root": self.root_path, "items": {}}

    def _save(self):
        try:
            tmp = self.filepath + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, self.filepath)
        except Exception:
            pass

    @staticmethod
    def key_for(rel, is_file):
        return rel if is_file else f"@dir:{rel}"

    def add_diagram(self, rel, is_file, diag_type, title, mermaid_code, explanation, model=""):
        """Saves a new diagram version. Preserves all existing versions!"""
        k = self.key_for(rel, is_file)
        now = datetime.datetime.now()
        ts_str = now.strftime("%Y-%m-%d %H:%M")
        diag_id = hashlib.sha1(f"{k}:{now.isoformat()}".encode("utf-8")).hexdigest()[:10]

        entry = {
            "id": diag_id,
            "type": diag_type,
            "title": title or DIAGRAM_TYPES.get(diag_type, {}).get("label", "Diagram"),
            "timestamp": ts_str,
            "mermaid": mermaid_code,
            "explanation": explanation,
            "model": model,
            "target": rel or "(Project Root)",
            "is_file": is_file,
        }

        with self.lock:
            items = self.data.setdefault("items", {})
            vault_list = items.setdefault(k, [])
            # Append to history so no previous diagram is deleted
            vault_list.insert(0, entry)
            self._save()
        return entry

    def get_diagrams(self, rel, is_file):
        """Returns all versions saved for this specific file or folder."""
        k = self.key_for(rel, is_file)
        with self.lock:
            return list(self.data.get("items", {}).get(k, []))

    def get_count(self, rel, is_file):
        k = self.key_for(rel, is_file)
        with self.lock:
            return len(self.data.get("items", {}).get(k, []))

    def delete_diagram(self, rel, is_file, diag_id):
        k = self.key_for(rel, is_file)
        with self.lock:
            items = self.data.get("items", {})
            if k in items:
                items[k] = [d for d in items[k] if d.get("id") != diag_id]
                self._save()

    def get_all_items_with_diagrams(self):
        """Returns dictionary of {rel_key: count} across the entire project."""
        with self.lock:
            items = self.data.get("items", {})
            return {k: len(v) for k, v in items.items() if v}

    def get_annotated_export_path(self, rel, is_file, entry=None):
        """
        Locates or writes an annotated HTML diagram file for this item in the local system folder.
        Returns the absolute file path on disk.
        """
        proj_name = os.path.basename(self.root_path) or "Project"
        proj_safe = re.sub(r"[^a-zA-Z0-9_\-]+", "_", proj_name).strip("_") or "Project"
        export_dir = os.path.join(VAULT_DIR, "diagram_files", proj_safe)
        os.makedirs(export_dir, exist_ok=True)

        target_name = posixpath.basename(rel) if rel else "project_root"
        safe_target = re.sub(r"[^a-zA-Z0-9_\-]+", "_", target_name).strip("_")

        diagrams_list = self.get_diagrams(rel, is_file)
        if not entry and diagrams_list:
            entry = diagrams_list[0]

        if not entry:
            return self.filepath

        dtype = entry.get("type", "system")
        safe_filename = f"{safe_target}_{dtype}.html"
        out_path = os.path.join(export_dir, safe_filename)

        # Render clean annotated HTML with Mermaid and explanations
        title = entry.get("title", "Diagram")
        m_code = entry.get("mermaid", "")
        content = HTML_MERMAID_TEMPLATE.format(
            PAGE_TITLE=f"{title} - {target_name}",
            DIAGRAM_TITLE=html.escape(f"{title} ({target_name})"),
            TARGET_LABEL=f"Target: {html.escape(rel or target_name)}",
            TIMESTAMP=entry.get("timestamp", ""),
            MODEL_USED=f"Model: {html.escape(entry.get('model', 'Gemini'))}",
            DIAGRAM_TYPE_LABEL=html.escape(DIAGRAM_TYPES.get(dtype, {}).get("label", "Diagram")),
            MERMAID_CODE=html.escape(m_code),
            RAW_MERMAID_JSON=json.dumps(m_code),
            EXPLANATION_HTML=format_explanation_html(entry.get("explanation", "")),
            SAFE_FILENAME=safe_target,
        )
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(content)
            return out_path
        except Exception as ex:
            print(f"[DiagramVault] Could not write annotated html: {ex}")
            return self.filepath

    def open_in_system_folder(self, rel, is_file):
        """Opens Windows Explorer with the saved diagram file highlighted."""
        path = self.get_annotated_export_path(rel, is_file)
        if os.path.exists(path):
            try:
                subprocess.run(f'explorer /select,"{os.path.abspath(path)}"', shell=True)
                return True
            except Exception:
                try:
                    os.startfile(os.path.dirname(path))
                    return True
                except Exception:
                    pass
        elif os.path.exists(self.filepath):
            try:
                subprocess.run(f'explorer /select,"{os.path.abspath(self.filepath)}"', shell=True)
                return True
            except Exception:
                pass
        return False


# --------------------------------------------------------------------------
# HTML & Interactive Browser Renderer
# --------------------------------------------------------------------------
HTML_MERMAID_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{PAGE_TITLE}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.1/dist/svg-pan-zoom.min.js"></script>
  <style>
    :root {{
      --bg: #f8fafc;
      --card-bg: #ffffff;
      --text: #1e293b;
      --border: #e2e8f0;
      --primary: #2563eb;
      --primary-hover: #1d4ed8;
      --muted: #64748b;
    }}
    body.dark-mode {{
      --bg: #0f172a;
      --card-bg: #1e293b;
      --text: #f1f5f9;
      --border: #334155;
      --primary: #3b82f6;
      --primary-hover: #60a5fa;
      --muted: #94a3b8;
    }}
    body {{
      margin: 0;
      padding: 0;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }}
    header {{
      background: var(--card-bg);
      border-bottom: 1px solid var(--border);
      padding: 12px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      position: sticky;
      top: 0;
      z-index: 100;
    }}
    h1 {{
      margin: 0;
      font-size: 1.15rem;
      color: var(--primary);
    }}
    .meta {{
      font-size: 0.85rem;
      color: var(--muted);
      margin-top: 2px;
    }}
    .actions {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    button {{
      background: var(--primary);
      color: white;
      border: none;
      padding: 7px 12px;
      border-radius: 6px;
      font-weight: 500;
      cursor: pointer;
      font-size: 0.85rem;
      transition: background 0.15s;
    }}
    button:hover {{
      background: var(--primary-hover);
    }}
    button.secondary {{
      background: var(--card-bg);
      color: var(--text);
      border: 1px solid var(--border);
    }}
    button.secondary:hover {{
      background: var(--border);
    }}
    main {{
      max-width: 1400px;
      margin: 20px auto;
      padding: 0 20px;
    }}
    .diagram-container {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      box-shadow: 0 4px 16px rgba(0,0,0,0.04);
      overflow: hidden;
      margin-bottom: 24px;
    }}
    .diagram-toolbar {{
      padding: 10px 16px;
      background: rgba(0,0,0,0.02);
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 0.85rem;
      color: var(--muted);
    }}
    .mermaid-box {{
      width: 100%;
      height: 70vh;
      min-height: 560px;
      max-height: 850px;
      display: flex;
      justify-content: center;
      align-items: center;
      background: white;
      position: relative;
      overflow: hidden;
    }}
    .mermaid-box svg {{
      width: 100% !important;
      height: 100% !important;
      max-width: none !important;
      max-height: none !important;
    }}
    .explanation-card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 24px;
      line-height: 1.6;
    }}
    .explanation-card h2 {{
      margin-top: 0;
      color: var(--primary);
      font-size: 1.15rem;
    }}
    pre.code-block {{
      background: #1e293b;
      color: #e2e8f0;
      padding: 14px;
      border-radius: 8px;
      font-size: 0.85rem;
      overflow-x: auto;
      font-family: Consolas, monospace;
    }}
    /* High clarity styling for Mermaid nodes */
    .node rect, .node circle, .node polygon, .node path {{
      rx: 8px !important;
      ry: 8px !important;
      stroke-width: 2px !important;
    }}
    .node text {{
      font-size: 13.5px !important;
      font-weight: 600 !important;
    }}
    .cluster rect {{
      rx: 12px !important;
      ry: 12px !important;
      stroke: #94a3b8 !important;
      stroke-width: 1.8px !important;
      fill: #f8fafc !important;
    }}
    .cluster text {{
      font-size: 13px !important;
      font-weight: 700 !important;
      fill: #334155 !important;
    }}
    .edgePath path {{
      stroke: #64748b !important;
      stroke-width: 2px !important;
    }}
    .edgeLabel {{
      background-color: #ffffff !important;
      padding: 3px 7px !important;
      border-radius: 4px !important;
      border: 1px solid #cbd5e1 !important;
      font-size: 12px !important;
    }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>{DIAGRAM_TITLE}</h1>
      <div class="meta">{TARGET_LABEL} &bull; Generated on {TIMESTAMP} &bull; {MODEL_USED}</div>
    </div>
    <div class="actions">
      <button class="secondary" onclick="toggleDirection()" title="Switch between Top-to-Bottom and Left-to-Right layout">🔄 Flip Direction</button>
      <button class="secondary" onclick="zoomIn()" title="Zoom In">➕</button>
      <button class="secondary" onclick="zoomOut()" title="Zoom Out">➖</button>
      <button class="secondary" onclick="fitView()" title="Fit entire diagram inside window">⛶ Fit View</button>
      <button class="secondary" onclick="resetZoom()" title="Reset to default 100% view">🔍 Reset</button>
      <button class="secondary" onclick="toggleTheme()">🌓 Theme</button>
      <button onclick="downloadSvg()">💾 Export SVG</button>
    </div>
  </header>

  <main>
    <div class="diagram-container">
      <div class="diagram-toolbar">
        <span>💡 Click and drag to pan diagram. Scroll mouse wheel to zoom in and out.</span>
        <span>{DIAGRAM_TYPE_LABEL}</span>
      </div>
      <div class="mermaid-box" id="mermaid-wrapper">
        <pre class="mermaid" id="diagram-svg">{MERMAID_CODE}</pre>
      </div>
    </div>

    <div class="explanation-card">
      <h2>📘 Plain-English Explanation (For Beginners)</h2>
      <div>{EXPLANATION_HTML}</div>

      <details style="margin-top: 24px;">
        <summary style="cursor: pointer; color: var(--muted); font-weight: 500;">View Raw Mermaid Code</summary>
        <pre class="code-block"><code id="raw-code-display">{MERMAID_CODE}</code></pre>
      </details>
    </div>
  </main>

  <script>
    mermaid.initialize({{
      startOnLoad: true,
      theme: 'default',
      securityLevel: 'loose',
      flowchart: {{ useMaxWidth: false, htmlLabels: true, curve: 'basis' }}
    }});

    let currentMermaidCode = {RAW_MERMAID_JSON};
    let panZoomInstance = null;

    function initPanZoom() {{
      const svgEl = document.querySelector('.mermaid-box svg');
      if (svgEl) {{
        svgEl.style.width = '100%';
        svgEl.style.height = '100%';
        svgEl.style.maxWidth = 'none';
        svgEl.style.maxHeight = 'none';
        if (panZoomInstance) {{
          try {{ panZoomInstance.destroy(); }} catch(e) {{}}
        }}
        try {{
          panZoomInstance = svgPanZoom(svgEl, {{
            zoomEnabled: true,
            controlIconsEnabled: false,
            fit: true,
            center: true,
            minZoom: 0.1,
            maxZoom: 15,
            zoomScaleSensitivity: 0.25
          }});
        }} catch(e) {{
          console.warn('svgPanZoom init error:', e);
        }}
      }}
    }}

    window.addEventListener('load', () => {{
      setTimeout(initPanZoom, 600);
    }});

    function resetZoom() {{
      if (panZoomInstance) {{
        panZoomInstance.reset();
        panZoomInstance.center();
      }}
    }}

    function fitView() {{
      if (panZoomInstance) {{
        panZoomInstance.fit();
        panZoomInstance.center();
      }}
    }}

    function zoomIn() {{
      if (panZoomInstance) panZoomInstance.zoomIn();
    }}

    function zoomOut() {{
      if (panZoomInstance) panZoomInstance.zoomOut();
    }}

    async function toggleDirection() {{
      let code = currentMermaidCode;
      if (/\\\\b(graph|flowchart)\\\\s+(TD|TB)\\\\b/i.test(code)) {{
        code = code.replace(/\\\\b(graph|flowchart)\\\\s+(TD|TB)\\\\b/i, '$1 LR');
      }} else if (/\\\\b(graph|flowchart)\\\\s+LR\\\\b/i.test(code)) {{
        code = code.replace(/\\\\b(graph|flowchart)\\\\s+LR\\\\b/i, '$1 TD');
      }} else {{
        return alert('Direction toggle is available for flowchart/graph diagrams.');
      }}
      currentMermaidCode = code;
      document.getElementById('raw-code-display').textContent = code;

      const wrapper = document.getElementById('mermaid-wrapper');
      wrapper.innerHTML = '<div style="color:#64748b; font-size:0.9rem;">Re-rendering diagram orientation...</div>';

      try {{
        const id = 'render_' + Math.floor(Math.random() * 10000);
        const res = await mermaid.render(id, code);
        wrapper.innerHTML = res.svg;
        setTimeout(initPanZoom, 150);
      }} catch(e) {{
        console.error('Re-render error:', e);
        wrapper.innerHTML = '<pre class="code-block" style="color:#ef4444;">Could not re-orient diagram: ' + e.message + '</pre>';
      }}
    }}

    function toggleTheme() {{
      document.body.classList.toggle('dark-mode');
    }}

    function downloadSvg() {{
      const svg = document.querySelector('.mermaid-box svg');
      if (!svg) return alert('Diagram is still rendering, please wait.');
      const data = new XMLSerializer().serializeToString(svg);
      const blob = new Blob([data], {{type: 'image/svg+xml;charset=utf-8'}});
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = '{SAFE_FILENAME}.svg';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    }}
  </script>
</body>
</html>
"""


def format_explanation_html(text):
    """Converts markdown-like explanation text into clean HTML."""
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            out.append("<br>")
            continue
        if line.startswith("#"):
            h_level = min(4, max(2, line.count("#", 0, 4) + 1))
            h_text = line.lstrip("#").strip()
            out.append(f"<h{h_level} style='margin-top: 18px; margin-bottom: 6px; color: #1e293b;'>{html.escape(h_text)}</h{h_level}>")
        elif line.startswith("- ") or line.startswith("* "):
            content = html.escape(line[2:].strip())
            # Bold highlights
            content = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", content)
            out.append(f"<div style='margin: 4px 0 4px 18px;'>&bull; {content}</div>")
        elif line.isupper() and len(line) < 50:
            out.append(f"<h3 style='margin-top: 18px; margin-bottom: 6px; color: #2563eb;'>{html.escape(line.title())}</h3>")
        else:
            esc = html.escape(line)
            esc = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", esc)
            out.append(f"<p style='margin: 6px 0;'>{esc}</p>")
    return "\n".join(out)


def open_interactive_browser_diagram(entry):
    """Generates an HTML file in tempdir and opens it in default web browser."""
    title = entry.get("title", "Software Diagram")
    target = entry.get("target", "Component")
    mermaid_code = entry.get("mermaid", "")
    explanation = entry.get("explanation", "")
    ts = entry.get("timestamp", "")
    model = entry.get("model", "Gemini")
    diag_type = entry.get("type", "system")
    type_label = DIAGRAM_TYPES.get(diag_type, {}).get("label", "Diagram")
    safe_name = re.sub(r"[^a-zA-Z0-9_\-]+", "_", f"{target}_{diag_type}").strip("_")

    content = HTML_MERMAID_TEMPLATE.format(
        PAGE_TITLE=f"{title} - CodeMap Visualizer",
        DIAGRAM_TITLE=html.escape(title),
        TARGET_LABEL=f"Target: {html.escape(target)}",
        TIMESTAMP=ts,
        MODEL_USED=f"Model: {html.escape(model)}",
        DIAGRAM_TYPE_LABEL=html.escape(type_label),
        MERMAID_CODE=html.escape(mermaid_code),
        RAW_MERMAID_JSON=json.dumps(mermaid_code),
        EXPLANATION_HTML=format_explanation_html(explanation),
        SAFE_FILENAME=safe_name,
    )

    tmp_dir = tempfile.gettempdir()
    html_path = os.path.join(tmp_dir, f"codemap_diagram_{safe_name}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(content)

    webbrowser.open(f"file:///{urllib.parse.quote(html_path.replace(chr(92), '/'))}")
    return html_path


# --------------------------------------------------------------------------
# Native Tkinter Canvas Diagram Renderer
# --------------------------------------------------------------------------
class DiagramCanvas(tk.Frame):
    """
    Advanced hierarchical DAG visualizer directly inside Tkinter Canvas.
    Features:
      * True topological layering (Sugiyama framework) with robust cycle breaking.
      * Subgraph clustering: renders grouping containers with title badges.
      * Smart curved Bezier connectors with arrowheads and label pill badges.
      * High-clarity typography with typed role badges (User, Screen, Logic, Data, Store).
      * Interactive node flow highlighting (click a node to trace upstream & downstream paths).
      * Orientation toggling (Top-to-Bottom vs Left-to-Right) and Fit-to-View.
    """

    def __init__(self, master, app=None, **kw):
        super().__init__(master, **kw)
        self.app = app
        self.project = None
        self.zoom = 1.0
        self.direction = "TD"
        self.entry = None
        self.parsed_nodes = {}
        self.parsed_edges = []
        self.parsed_subgraphs = {}
        self.node_positions = {}
        self.node_targets = {}
        self.node_buttons = {}
        self.subgraph_boxes = {}
        self.preds = {}
        self.succs = {}
        self.selected_node = None
        self._down = (0, 0)
        self._moved = False

        self._build_ui()

    def set_project(self, project):
        self.project = project

    def _build_ui(self):
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(body, bg="#f8fafc", highlightthickness=0)
        self.ys = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
        self.xs = ttk.Scrollbar(body, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.ys.set, xscrollcommand=self.xs.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.ys.grid(row=0, column=1, sticky="ns")
        self.xs.grid(row=1, column=0, sticky="ew")
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)

        c = self.canvas
        c.bind("<ButtonPress-1>", self._on_press)
        c.bind("<B1-Motion>", self._on_drag)
        c.bind("<ButtonRelease-1>", self._on_release)
        c.bind("<Button-3>", self._on_right_click)
        c.bind("<Button-2>", self._on_right_click)
        c.bind("<MouseWheel>", self._on_wheel)
        c.bind("<Button-4>", lambda e: self.set_zoom(self.zoom * 1.15))
        c.bind("<Button-5>", lambda e: self.set_zoom(self.zoom / 1.15))

    def set_zoom(self, z):
        self.zoom = max(0.3, min(3.5, z))
        self.render()

    def fit_view(self):
        """Scales and positions the diagram so the entire graph fits into view."""
        bb = self.canvas.bbox("all")
        if not bb:
            return
        c_w = self.canvas.winfo_width() or 800
        c_h = self.canvas.winfo_height() or 600
        diag_w = max(100, bb[2] - bb[0])
        diag_h = max(100, bb[3] - bb[1])

        scale_x = (c_w - 60) / (diag_w / self.zoom)
        scale_y = (c_h - 60) / (diag_h / self.zoom)
        self.zoom = max(0.4, min(1.8, min(scale_x, scale_y)))
        self.render()
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)

    def toggle_direction(self):
        """Flips between Top-to-Bottom (TD) and Left-to-Right (LR) layout."""
        self.direction = "LR" if self.direction == "TD" else "TD"
        self.render()

    def _on_press(self, e):
        self.canvas.scan_mark(e.x, e.y)
        self._down = (e.x, e.y)
        self._moved = False

    def _on_drag(self, e):
        if abs(e.x - self._down[0]) > 4 or abs(e.y - self._down[1]) > 4:
            self._moved = True
            self.canvas.configure(cursor="fleur")
            self.canvas.scan_dragto(e.x, e.y, gain=1)

    def _on_release(self, e):
        self.canvas.configure(cursor="")
        if not self._moved:
            cx = self.canvas.canvasx(e.x)
            cy = self.canvas.canvasy(e.y)

            # 1. Check if clicked on a folder/file button
            for nid, (bx, by, bw, bh, rel, is_file) in self.node_buttons.items():
                if bx <= cx <= bx + bw and by <= cy <= by + bh:
                    self._open_node_target(rel)
                    return

            # 2. Check card click
            clicked_node = None
            for nid, (nx, ny, nw, nh) in self.node_positions.items():
                if nx <= cx <= nx + nw and ny <= cy <= ny + nh:
                    clicked_node = nid
                    break

            if clicked_node != self.selected_node:
                self.selected_node = clicked_node
                self.render()

    def _on_wheel(self, e):
        delta = e.delta if e.delta else (120 if e.num == 4 else -120)
        if e.state & 0x1:  # Shift = horizontal scroll
            self.canvas.xview_scroll(-2 if delta > 0 else 2, "units")
        else:
            # Direct wheel = smooth zoom in/out
            self.set_zoom(self.zoom * (1.15 if delta > 0 else 1 / 1.15))

    def _find_project_node(self, nid, title, sub):
        if not self.project:
            return None, False
        for cand in (sub, nid, title):
            if not cand:
                continue
            cand_clean = cand.strip().strip("()[]\"'")
            if cand_clean in self.project.nodes:
                return cand_clean, not self.project.nodes[cand_clean].is_dir
            base = posixpath.basename(cand_clean).lower()
            matches = getattr(self.project, "_filename_index", {}).get(base)
            if matches:
                return matches[0], True
            stem = posixpath.splitext(base)[0]
            matches = getattr(self.project, "_filename_index", {}).get(stem)
            if matches:
                return matches[0], True
        return None, False

    def _open_node_target(self, rel):
        if not self.project or rel not in self.project.nodes:
            return
        node = self.project.nodes[rel]
        try:
            os.startfile(node.path)
        except Exception as err:
            messagebox.showerror("Could not open", f"Failed to open {node.path}: {err}")

    def _on_right_click(self, e):
        cx = self.canvas.canvasx(e.x)
        cy = self.canvas.canvasy(e.y)
        clicked_node = None
        for nid, (nx, ny, nw, nh) in self.node_positions.items():
            if nx <= cx <= nx + nw and ny <= cy <= ny + nh:
                clicked_node = nid
                break
        if not clicked_node:
            return

        target_info = self.node_targets.get(clicked_node)
        rel = target_info[0] if target_info else clicked_node
        is_file = target_info[1] if target_info else False
        node_name = posixpath.basename(rel) if target_info else clicked_node

        menu = tk.Menu(self.canvas, tearoff=0)
        menu.add_command(label=f"💬 Ask AI about '{node_name}'...",
                         command=lambda: self._open_chat(rel, is_file))
        menu.add_command(label=f"✨ Generate Diagram for '{node_name}'",
                         command=lambda: self._gen_for_node(rel, is_file))
        if target_info:
            menu.add_separator()
            menu.add_command(label=f"📁 Open in Explorer / Editor",
                             command=lambda: self._open_node_target(rel))
            menu.add_command(label=f"🗺 Reveal in Mind Map",
                             command=lambda: self._reveal_in_map(rel))
        try:
            menu.tk_popup(e.x_root, e.y_root)
        finally:
            menu.grab_release()

    def _open_chat(self, rel, is_file):
        if self.app:
            import codemap_chat
            codemap_chat.FolderChatDialog(self.app.master, self.app, rel, is_file)

    def _gen_for_node(self, rel, is_file):
        if self.app and hasattr(self.app, "diagram_studio"):
            self.app.diagram_studio.set_target(rel)
            self.app.diagram_studio.generate()

    def _reveal_in_map(self, rel):
        if self.app and hasattr(self.app, "mindmap"):
            self.app.mindmap.reveal(rel)
            self.app.nb.select(self.app.mindmap)

    def display_diagram(self, entry):
        self.entry = entry
        self.selected_node = None
        self.direction = "TD"
        self.render()

    def _parse_mermaid(self, text):
        nodes = {}
        edges = []
        subgraphs = {}
        sg_stack = []

        direction = "TD"
        m_dir = re.search(r"\b(graph|flowchart)\s+(TD|TB|LR|RL|BT)\b", text, re.IGNORECASE)
        if m_dir:
            direction = m_dir.group(2).upper()
            if direction == "TB":
                direction = "TD"

        clean_lines = []
        for line in text.splitlines():
            s = line.strip()
            if not s or s.startswith("%%"):
                continue
            clean_lines.append(s)

        if not clean_lines:
            return {}, [], {}, "TD"

        first_line = clean_lines[0].lower()
        is_sequence = "sequencediagram" in text.lower() or first_line.startswith("sequence")
        is_state = "statediagram" in text.lower() or first_line.startswith("state")

        # ------------------------------------------------------------------
        # Mode A: Sequence Diagram (Participants, Containers/Boxes, Messages)
        # ------------------------------------------------------------------
        if is_sequence:
            direction = "TD"
            box_re = re.compile(
                r'^box(?:\s+(?:rgb|rgba)\([^)]+\))?\s*(?:"([^"]+)"|([^"\n\r]+))?',
                re.IGNORECASE,
            )
            part_re = re.compile(
                r'^(?:actor|participant)\s+([A-Za-z0-9_\-]+)(?:\s+as\s+(?:"([^"]+)"|([^"\n\r]+)))?',
                re.IGNORECASE,
            )
            seq_edge_re = re.compile(
                r'^([A-Za-z0-9_\-]+)\s*(?:-->>|->>|-->|->|-\)|--\))\s*[+-]?\s*([A-Za-z0-9_\-]+)\s*:\s*(.*)$'
            )

            for s in clean_lines:
                if s.lower() in ("sequencediagram", "autonumber"):
                    continue

                if s.lower().startswith("box"):
                    bm = box_re.match(s)
                    raw_t = (bm.group(1) or bm.group(2) or "").strip() if bm else ""
                    raw_t = re.sub(r"^(?:rgb|rgba)\([^)]+\)\s*", "", raw_t).strip()
                    sg_id = f"box_{len(subgraphs)}"
                    title = raw_t or f"Group {len(subgraphs) + 1}"
                    subgraphs[sg_id] = {"id": sg_id, "title": title, "nodes": []}
                    sg_stack.append(sg_id)
                    continue

                if s.lower() == "end":
                    if sg_stack:
                        sg_stack.pop()
                    continue

                cur_sg = sg_stack[-1] if sg_stack else None

                pm = part_re.match(s)
                if pm:
                    nid = pm.group(1)
                    raw_lbl = pm.group(2) or pm.group(3) or nid
                    lbl = re.sub(r"<br\s*/?>", " ", raw_lbl).strip('" ')
                    nodes[nid] = {"id": nid, "label": lbl, "sg": cur_sg}
                    if cur_sg and cur_sg in subgraphs and nid not in subgraphs[cur_sg]["nodes"]:
                        subgraphs[cur_sg]["nodes"].append(nid)
                    continue

                em = seq_edge_re.match(s)
                if em:
                    src = em.group(1)
                    dst = em.group(2)
                    lbl = em.group(3).strip()
                    edges.append((src, dst, lbl))
                    if src not in nodes:
                        nodes[src] = {"id": src, "label": src, "sg": cur_sg}
                        if cur_sg and cur_sg in subgraphs and src not in subgraphs[cur_sg]["nodes"]:
                            subgraphs[cur_sg]["nodes"].append(src)
                    if dst not in nodes:
                        nodes[dst] = {"id": dst, "label": dst, "sg": cur_sg}
                        if cur_sg and cur_sg in subgraphs and dst not in subgraphs[cur_sg]["nodes"]:
                            subgraphs[cur_sg]["nodes"].append(dst)
                    continue

            return nodes, edges, subgraphs, direction

        # ------------------------------------------------------------------
        # Mode B: State Diagram (States & Event Transitions)
        # ------------------------------------------------------------------
        if is_state:
            state_desc_re = re.compile(r'^state\s+"([^"]+)"\s+as\s+([A-Za-z0-9_\-]+)', re.IGNORECASE)
            state_edge_re = re.compile(r'([A-Za-z0-9_\*\[\]]+)\s*-->\s*([A-Za-z0-9_\*\[\]]+)(?:\s*:\s*(.*))?')
            for s in clean_lines:
                if s.lower().startswith("statediagram"):
                    continue
                sm = state_desc_re.match(s)
                if sm:
                    lbl = sm.group(1).strip()
                    nid = sm.group(2).strip()
                    nodes[nid] = {"id": nid, "label": lbl, "sg": None}
                    continue
                em = state_edge_re.search(s)
                if em:
                    raw_src = em.group(1)
                    raw_dst = em.group(2)
                    lbl = (em.group(3) or "").strip()
                    src = "Start" if "[*]" in raw_src else raw_src
                    dst = "End" if "[*]" in raw_dst else raw_dst
                    edges.append((src, dst, lbl))
                    if src not in nodes:
                        nodes[src] = {"id": src, "label": "🔘 Start" if src == "Start" else src, "sg": None}
                    if dst not in nodes:
                        nodes[dst] = {"id": dst, "label": "⏹ End" if dst == "End" else dst, "sg": None}
            return nodes, edges, subgraphs, direction

        # ------------------------------------------------------------------
        # Mode C: Flowchart / Graph / Class Diagram
        # ------------------------------------------------------------------
        sg_re = re.compile(
            r'subgraph\s+(?:(?P<id>[A-Za-z0-9_\-]+)\s*)?(?:\["(?P<t1>[^"]+)"\]|\[(?P<t2>[^\]]+)\]|"(?P<t3>[^"]+)")?',
            re.IGNORECASE,
        )
        node_re = re.compile(
            r'([A-Za-z0-9_\-]+)\s*(?:\["([^"]+)"\]|\[([^\]]+)\]|\("([^"]+)"\)|\(([^)]+)\)|\{\{([^}]+)\}\}|\{([^}]+)\})'
        )
        edge_re = re.compile(
            r'([A-Za-z0-9_\-]+)\s*(?:--\s*(?:"([^"]+)"|([^->]+))\s*-->|-->\|([^|]+)\||-->|==>|-\.->|---|--\s*>\s*)\s*([A-Za-z0-9_\-]+)'
        )

        for s in clean_lines:
            if re.match(r'^(?:style|classDef|rgb|rgba|fill|stroke)\b', s, re.IGNORECASE):
                continue

            if s.lower().startswith("subgraph"):
                sm = sg_re.search(s)
                if sm:
                    raw_id = sm.group("id")
                    raw_t = sm.group("t1") or sm.group("t2") or sm.group("t3")
                    sg_id = raw_id or raw_t or f"sg_{len(subgraphs)}"
                    title = (raw_t or raw_id or sg_id).strip('" ')
                    subgraphs[sg_id] = {"id": sg_id, "title": title, "nodes": []}
                    sg_stack.append(sg_id)
                continue

            if s.lower() == "end":
                if sg_stack:
                    sg_stack.pop()
                continue

            cur_sg = sg_stack[-1] if sg_stack else None

            for em in edge_re.finditer(s):
                src = em.group(1)
                lbl = (em.group(2) or em.group(3) or em.group(4) or "").strip()
                dst = em.group(5)
                edges.append((src, dst, lbl))
                if src not in nodes:
                    nodes[src] = {"id": src, "label": src, "sg": cur_sg}
                if dst not in nodes:
                    nodes[dst] = {"id": dst, "label": dst, "sg": cur_sg}

            for nm in node_re.finditer(s):
                nid = nm.group(1)
                if nid.lower() in ("rgb", "rgba", "style", "fill", "stroke", "box"):
                    continue
                lbl = next((g for g in nm.groups()[1:] if g is not None), nid).strip()
                lbl = re.sub(r"<br\s*/?>", " ", lbl)
                if nid not in nodes:
                    nodes[nid] = {"id": nid, "label": lbl, "sg": cur_sg}
                else:
                    nodes[nid]["label"] = lbl
                    if cur_sg and not nodes[nid]["sg"]:
                        nodes[nid]["sg"] = cur_sg

                if cur_sg and cur_sg in subgraphs and nid not in subgraphs[cur_sg]["nodes"]:
                    subgraphs[cur_sg]["nodes"].append(nid)

        return nodes, edges, subgraphs, direction

    def _compute_layout(self, nodes, edges, subgraphs, direction, z):
        succs = {n: set() for n in nodes}
        preds = {n: set() for n in nodes}
        for src, dst, _ in edges:
            if src in nodes and dst in nodes and src != dst:
                succs[src].add(dst)
                preds[dst].add(src)

        # Kahn DAG Ranking with cycle-breaking
        in_deg = {n: len(preds[n]) for n in nodes}
        ranks = {}
        visited = set()
        queue = [n for n, d in in_deg.items() if d == 0]
        for q in queue:
            ranks[q] = 0

        while len(visited) < len(nodes):
            if not queue:
                unvis = [n for n in nodes if n not in visited]
                if not unvis:
                    break
                cand = min(unvis, key=lambda n: in_deg.get(n, 999))
                cand_preds = [ranks[p] for p in preds[cand] if p in ranks]
                ranks[cand] = (max(cand_preds) + 1) if cand_preds else 0
                queue.append(cand)

            curr = queue.pop(0)
            if curr in visited:
                continue
            visited.add(curr)
            cr = ranks.get(curr, 0)
            for nxt in succs[curr]:
                if nxt not in visited:
                    in_deg[nxt] -= 1
                    ranks[nxt] = max(ranks.get(nxt, 0), cr + 1)
                    if in_deg[nxt] <= 0:
                        queue.append(nxt)

        # Compact ranks
        unique_ranks = sorted(set(ranks.values())) if ranks else [0]
        rank_map = {old: new for new, old in enumerate(unique_ranks)}
        compact_ranks = {n: rank_map.get(ranks.get(n, 0), 0) for n in nodes}
        max_rank = max(compact_ranks.values()) if compact_ranks else 0
        layers = [[] for _ in range(max_rank + 1)]
        for n, r in compact_ranks.items():
            layers[r].append(n)

        # Barycenter & Subgraph sort
        for r in range(len(layers)):
            layer_nodes = layers[r]
            def sort_key(n):
                sg_val = nodes[n].get("sg") or ""
                p_ranks = [layers[compact_ranks[p]].index(p) for p in preds[n] if p in compact_ranks and compact_ranks[p] < r and p in layers[compact_ranks[p]]]
                bary = sum(p_ranks) / len(p_ranks) if p_ranks else 0.0
                return (sg_val, bary)
            layer_nodes.sort(key=sort_key)

        pos = {}
        is_td = (direction == "TD")
        card_w = round(215 * z)
        card_h = round(80 * z)
        gx = round(45 * z)
        gy = round(75 * z)

        if is_td:
            max_layer_w = max((len(l) * (card_w + gx) - gx for l in layers), default=card_w)
            center_x = max_layer_w / 2 + round(60 * z)
            for r, l in enumerate(layers):
                lw = len(l) * (card_w + gx) - gx
                sx = center_x - lw / 2
                sy = round(60 * z) + r * (card_h + gy)
                for i, nid in enumerate(l):
                    nx = sx + i * (card_w + gx)
                    pos[nid] = (nx, sy, card_w, card_h)
        else:
            max_layer_h = max((len(l) * (card_h + gy) - gy for l in layers), default=card_h)
            center_y = max_layer_h / 2 + round(60 * z)
            for r, l in enumerate(layers):
                lh = len(l) * (card_h + gy) - gy
                sy = center_y - lh / 2
                sx = round(60 * z) + r * (card_w + gx)
                for i, nid in enumerate(l):
                    ny = sy + i * (card_h + gy)
                    pos[nid] = (sx, ny, card_w, card_h)

        sg_boxes = {}
        pad = round(20 * z)
        header_h = round(26 * z)
        for sg_id, sg in subgraphs.items():
            member_nodes = [n for n in sg["nodes"] if n in pos]
            if member_nodes:
                min_x = min(pos[n][0] for n in member_nodes) - pad
                min_y = min(pos[n][1] for n in member_nodes) - pad - header_h
                max_x = max(pos[n][0] + pos[n][2] for n in member_nodes) + pad
                max_y = max(pos[n][1] + pos[n][3] for n in member_nodes) + pad
                sg_boxes[sg_id] = {
                    "title": sg["title"],
                    "box": (min_x, min_y, max_x - min_x, max_y - min_y),
                    "header_h": header_h,
                }

        return pos, sg_boxes, preds, succs

    def _classify_node(self, nid, label, preds, succs):
        l_low = (label + " " + nid).lower()
        if any(k in l_low for k in ("user", "human", "client", "trigger", "event", "start")):
            return ("#eff6ff", "#3b82f6", "#1d4ed8"), "👤 User / Trigger"
        elif any(k in l_low for k in ("screen", "dashboard", "view", "display", "ui", "interface", "page", "result")):
            return ("#faf5ff", "#8b5cf6", "#6d28d9"), "🖥 Screen / Display"
        elif any(k in l_low for k in ("rule", "type", "contract", "schema", "blueprint", "note", "guide", "record", "doc")):
            return ("#fffbeb", "#f59e0b", "#b45309"), "📄 Blueprint / Data"
        elif any(k in l_low for k in ("store", "db", "database", "vault", "archive", "cache", "asset", "texture")):
            return ("#fff1f2", "#ef4444", "#be123c"), "💾 Storage / Cache"
        elif len(preds.get(nid, [])) == 0:
            return ("#eff6ff", "#3b82f6", "#1d4ed8"), "📥 Input / Source"
        elif len(succs.get(nid, [])) == 0:
            return ("#f5f3ff", "#8b5cf6", "#6d28d9"), "📤 Output / Result"
        else:
            return ("#f0fdf4", "#10b981", "#15803d"), "⚙ Core Logic"

    @staticmethod
    def _split_label(label, nid):
        m_paren = re.search(r"^(.*?)\s*\((.*?)\)$", label)
        if m_paren:
            title = m_paren.group(1).strip()
            sub = f"({m_paren.group(2).strip()})"
        elif "\n" in label:
            parts = label.split("\n", 1)
            title = parts[0].strip()
            sub = parts[1].strip()
        else:
            title = label
            sub = ""
        return title, sub

    def render(self):
        c = self.canvas
        c.delete("all")

        if not self.entry or not self.entry.get("mermaid"):
            c.create_text(40, 40, anchor="nw", text="No visual diagram generated yet.\nSelect a file/folder and click 'Generate Diagram' above.",
                          fill="#64748b", font=("Segoe UI", 11))
            c.configure(scrollregion=(0, 0, 600, 300))
            return

        mermaid = self.entry["mermaid"]
        nodes, edges, subgraphs, auto_dir = self._parse_mermaid(mermaid)

        if not nodes:
            c.create_text(30, 20, anchor="nw", text=f"📐 Mermaid Diagram Specification ({self.entry.get('type', 'system').upper()}):",
                          font=("Segoe UI", 11, "bold"), fill="#1e293b")
            c.create_text(30, 50, anchor="nw", text=mermaid, font=("Consolas", 10), fill="#334155")
            c.configure(scrollregion=(0, 0, 900, max(400, len(mermaid.splitlines()) * 22 + 80)))
            return

        direction = self.direction or auto_dir or "TD"
        z = self.zoom
        f_badge = tkfont.Font(family="Segoe UI", size=max(6, round(8 * z)), weight="bold")
        f_title = tkfont.Font(family="Segoe UI", size=max(7, round(9.5 * z)), weight="bold")
        f_sub = tkfont.Font(family="Segoe UI", size=max(6, round(8 * z)))
        f_edge = tkfont.Font(family="Segoe UI", size=max(6, round(7.8 * z)))
        f_sg = tkfont.Font(family="Segoe UI", size=max(7, round(9 * z)), weight="bold")

        pos, sg_boxes, preds, succs = self._compute_layout(nodes, edges, subgraphs, direction, z)
        self.node_positions = pos
        self.subgraph_boxes = sg_boxes
        self.preds = preds
        self.succs = succs
        self.node_targets = {}
        self.node_buttons = {}
        sel = self.selected_node

        # 1. Draw Subgraph Container Panels (behind nodes and lines)
        for sg_id, sg_info in sg_boxes.items():
            bx, by, bw, bh = sg_info["box"]
            hh = sg_info["header_h"]
            r_sg = round(12 * z)
            pts_sg = [bx + r_sg, by, bx + bw - r_sg, by, bx + bw, by, bx + bw, by + r_sg,
                      bx + bw, by + bh - r_sg, bx + bw, by + bh, bx + bw - r_sg, by + bh,
                      bx + r_sg, by + bh, bx, by + bh, bx, by + bh - r_sg, bx, by + r_sg, bx, by]
            c.create_polygon(pts_sg, smooth=True, fill="#f8fafc", outline="#cbd5e1", width=max(1, round(1.5 * z)))

            # Header pill
            title_text = f"📂 {sg_info['title']}"
            t_w = f_sg.measure(title_text) + round(16 * z)
            c.create_rectangle(bx + round(10 * z), by + round(6 * z), bx + round(10 * z) + t_w, by + round(6 * z) + hh - round(6 * z),
                               fill="#e2e8f0", outline="#cbd5e1", width=1)
            c.create_text(bx + round(18 * z), by + round(6 * z) + (hh - round(6 * z)) / 2, anchor="w",
                          text=title_text, font=f_sg, fill="#334155")

        # 2. Draw Connecting Edges (Bezier curves)
        is_td = (direction == "TD")
        for src, dst, elbl in edges:
            if src in pos and dst in pos and src != dst:
                sx, sy, sw, sh = pos[src]
                dx, dy, dw, dh = pos[dst]

                # Determine edge styling based on selection
                if sel:
                    if src == sel:
                        line_col = "#059669"  # Outgoing from selected (emerald)
                        line_w = max(2, round(2.8 * z))
                    elif dst == sel:
                        line_col = "#0284c7"  # Incoming to selected (sky blue)
                        line_w = max(2, round(2.8 * z))
                    else:
                        line_col = "#e2e8f0"  # Dimmed
                        line_w = 1
                else:
                    line_col = "#64748b"
                    line_w = max(1, round(1.8 * z))

                if is_td:
                    if dy > sy + sh / 2:
                        x1, y1 = sx + sw / 2, sy + sh
                        x2, y2 = dx + dw / 2, dy
                        cx1, cy1 = x1, y1 + (y2 - y1) * 0.45
                        cx2, cy2 = x2, y2 - (y2 - y1) * 0.45
                        c.create_line(x1, y1, cx1, cy1, cx2, cy2, x2, y2, smooth=True, arrow=tk.LAST,
                                      fill=line_col, width=line_w, arrowshape=(10 * z, 12 * z, 4 * z))
                        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                    else:
                        # Backward / loop edge
                        x1, y1 = sx + sw, sy + sh / 2
                        x2, y2 = dx + dw, dy + dh / 2
                        loop_x = max(sx + sw, dx + dw) + round(35 * z)
                        c.create_line(x1, y1, loop_x, y1, loop_x, y2, x2, y2, smooth=True, arrow=tk.LAST,
                                      fill=line_col, width=line_w, arrowshape=(10 * z, 12 * z, 4 * z))
                        mx, my = loop_x + round(8 * z), (y1 + y2) / 2
                else:
                    # LR direction
                    if dx > sx + sw / 2:
                        x1, y1 = sx + sw, sy + sh / 2
                        x2, y2 = dx, dy + dh / 2
                        cx1, cy1 = x1 + (x2 - x1) * 0.45, y1
                        cx2, cy2 = x2 - (x2 - x1) * 0.45, y2
                        c.create_line(x1, y1, cx1, cy1, cx2, cy2, x2, y2, smooth=True, arrow=tk.LAST,
                                      fill=line_col, width=line_w, arrowshape=(10 * z, 12 * z, 4 * z))
                        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                    else:
                        x1, y1 = sx + sw / 2, sy + sh
                        x2, y2 = dx + dw / 2, dy + dh
                        loop_y = max(sy + sh, dy + dh) + round(30 * z)
                        c.create_line(x1, y1, x1, loop_y, x2, loop_y, x2, y2, smooth=True, arrow=tk.LAST,
                                      fill=line_col, width=line_w, arrowshape=(10 * z, 12 * z, 4 * z))
                        mx, my = (x1 + x2) / 2, loop_y + round(8 * z)

                # Edge label badge
                if elbl and (not sel or sel in (src, dst)):
                    badge_w = f_edge.measure(elbl) + round(10 * z)
                    badge_h = round(16 * z)
                    c.create_rectangle(mx - badge_w / 2, my - badge_h / 2, mx + badge_w / 2, my + badge_h / 2,
                                       fill="#ffffff", outline="#cbd5e1", width=1)
                    c.create_text(mx, my, text=elbl, font=f_edge, fill="#2563eb")

        # 3. Draw Node Cards
        for nid, (x, y, w, h) in pos.items():
            raw_lbl = nodes[nid]["label"]
            title, sub = self._split_label(raw_lbl, nid)
            (bg_col, border_col, text_col), role_tag = self._classify_node(nid, raw_lbl, preds, succs)

            # Check selection state
            if sel:
                if nid == sel:
                    border_col = "#2563eb"
                    border_w = max(2, round(3.5 * z))
                    bg_col = "#ffffff"
                elif nid in preds.get(sel, []):
                    border_col = "#0284c7"
                    border_w = max(2, round(2.5 * z))
                    role_tag = f"⬅ Input to {sel}"
                elif nid in succs.get(sel, []):
                    border_col = "#059669"
                    border_w = max(2, round(2.5 * z))
                    role_tag = f"➡ Output from {sel}"
                else:
                    # Dimmed
                    bg_col = "#f8fafc"
                    border_col = "#e2e8f0"
                    text_col = "#94a3b8"
                    border_w = 1
            else:
                border_w = max(1, round(1.8 * z))

            # Rounded card polygon
            r = round(10 * z)
            pts = [x + r, y, x + w - r, y, x + w, y, x + w, y + r, x + w, y + h - r, x + w, y + h,
                   x + w - r, y + h, x + r, y + h, x, y + h, x, y + h - r, x, y + r, x, y]
            c.create_polygon(pts, smooth=True, fill=bg_col, outline=border_col, width=border_w)

            # Role badge at top
            c.create_text(x + round(12 * z), y + round(14 * z), anchor="w",
                          text=role_tag, font=f_badge, fill=text_col)

            # Match with project file/folder for quick actions
            rel_target, is_file = self._find_project_node(nid, title, sub)
            if rel_target:
                self.node_targets[nid] = (rel_target, is_file)
                btn_icon = "📄" if is_file else "📁"
                btn_w = round(22 * z)
                btn_h = round(18 * z)
                btn_x = x + w - btn_w - round(8 * z)
                btn_y = y + round(6 * z)
                self.node_buttons[nid] = (btn_x, btn_y, btn_w, btn_h, rel_target, is_file)
                c.create_rectangle(btn_x, btn_y, btn_x + btn_w, btn_y + btn_h,
                                   fill="#f1f5f9", outline="#cbd5e1", width=1)
                c.create_text(btn_x + btn_w / 2, btn_y + btn_h / 2,
                              text=btn_icon, font=f_badge)

            # Main title (wrapped)
            lines = []
            words = title.split()
            cur = ""
            for w_tok in words:
                if len(cur) + len(w_tok) < 22:
                    cur = f"{cur} {w_tok}".strip()
                else:
                    lines.append(cur)
                    cur = w_tok
            if cur:
                lines.append(cur)
            title_wrapped = "\n".join(lines[:2])
            c.create_text(x + round(12 * z), y + round(34 * z), anchor="nw",
                          text=title_wrapped, font=f_title, fill="#1e293b" if not (sel and nid != sel and nid not in preds.get(sel, []) and nid not in succs.get(sel, [])) else "#94a3b8")

            # Subtitle (file or identifier)
            if sub:
                sub_disp = sub if len(sub) <= 25 else sub[:23] + "..."
                c.create_text(x + round(12 * z), y + round(64 * z), anchor="w",
                              text=sub_disp, font=f_sub, fill="#64748b" if not (sel and nid != sel) else "#94a3b8")

        # 4. Floating selection status overlay
        if sel:
            in_c = len(preds.get(sel, []))
            out_c = len(succs.get(sel, []))
            stat_msg = f"📌 Focused: {sel}  |  {in_c} input(s) ➔ {out_c} output(s)  •  (Click blank area to reset focus)"
            c.create_rectangle(round(20 * z), round(14 * z), round(20 * z) + f_title.measure(stat_msg) + round(24 * z), round(42 * z),
                               fill="#eff6ff", outline="#3b82f6", width=round(1.5 * z))
            c.create_text(round(32 * z), round(28 * z), anchor="w", text=stat_msg, font=f_badge, fill="#1d4ed8")

        bb = c.bbox("all")
        if bb:
            c.configure(scrollregion=(0, 0, bb[2] + round(80 * z), bb[3] + round(80 * z)))
        else:
            c.configure(scrollregion=(0, 0, 1000, 600))



# --------------------------------------------------------------------------
# Whole-Project Vault HTML Exporter
# --------------------------------------------------------------------------
VAULT_INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{PROJECT_NAME} - Complete Visuals Vault</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      margin: 0;
      display: flex;
      height: 100vh;
      overflow: hidden;
      background: #f8fafc;
      color: #1e293b;
    }}
    #sidebar {{
      width: 320px;
      background: #ffffff;
      border-right: 1px solid #e2e8f0;
      display: flex;
      flex-direction: column;
    }}
    .sidebar-header {{
      padding: 16px;
      border-bottom: 1px solid #e2e8f0;
      background: #f1f5f9;
    }}
    .sidebar-header h2 {{
      margin: 0;
      font-size: 1.1rem;
      color: #2563eb;
    }}
    .search-box {{
      padding: 10px 16px;
      border-bottom: 1px solid #e2e8f0;
    }}
    .search-box input {{
      width: 100%;
      padding: 8px 12px;
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      box-sizing: border-box;
    }}
    #item-list {{
      flex: 1;
      overflow-y: auto;
      list-style: none;
      margin: 0;
      padding: 8px 0;
    }}
    .list-item {{
      padding: 10px 16px;
      cursor: pointer;
      border-bottom: 1px solid #f1f5f9;
      font-size: 0.9rem;
    }}
    .list-item:hover, .list-item.active {{
      background: #eff6ff;
      color: #2563eb;
      font-weight: 500;
    }}
    .badge {{
      float: right;
      background: #e2e8f0;
      color: #475569;
      padding: 2px 6px;
      border-radius: 10px;
      font-size: 0.75rem;
    }}
    #content {{
      flex: 1;
      overflow-y: auto;
      padding: 24px 32px;
    }}
    .card {{
      background: white;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      padding: 20px;
      margin-bottom: 24px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.02);
    }}
  </style>
</head>
<body>
  <div id="sidebar">
    <div class="sidebar-header">
      <h2>📚 {PROJECT_NAME}</h2>
      <div style="font-size: 0.8rem; color: #64748b; margin-top: 4px;">Visuals & Diagrams Vault ({TOTAL_DIAGRAMS} diagrams)</div>
    </div>
    <div class="search-box">
      <input type="text" id="filter" placeholder="Filter files and folders..." oninput="filterItems()">
    </div>
    <ul id="item-list">
      {SIDEBAR_ITEMS}
    </ul>
  </div>

  <div id="content">
    <div id="viewer">
      <div class="card">
        <h2>👈 Select a file or folder from the sidebar</h2>
        <p style="color: #64748b;">Every diagram generated for your project is stored here with full version history.</p>
      </div>
    </div>
  </div>

  <script>
    mermaid.initialize({{ startOnLoad: true, theme: 'default', securityLevel: 'loose' }});

    const vaultData = {VAULT_DATA_JSON};

    function showItem(key) {{
      document.querySelectorAll('.list-item').forEach(el => el.classList.remove('active'));
      const activeEl = document.querySelector(`[data-key="${{key}}"]`);
      if (activeEl) activeEl.classList.add('active');

      const items = vaultData[key] || [];
      const viewer = document.getElementById('viewer');
      if (!items.length) {{
        viewer.innerHTML = '<div class="card">No diagrams for this item.</div>';
        return;
      }}

      let html = `<h1 style="color: #1e293b; margin-top: 0;">${{key.replace('@dir:', '📁 Folder: ')}}</h1>`;
      items.forEach((d, i) => {{
        html += `
          <div class="card">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #e2e8f0; padding-bottom: 10px; margin-bottom: 14px;">
              <h3 style="margin: 0; color: #2563eb;">${{d.title}} (v${{items.length - i}})</h3>
              <span style="font-size: 0.85rem; color: #64748b;">${{d.timestamp}} &bull; ${{d.model || 'Gemini'}}</span>
            </div>
            <div style="background: white; padding: 14px; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 14px;">
              <pre class="mermaid">${{d.mermaid}}</pre>
            </div>
            <div style="line-height: 1.6; color: #334155;">${{d.explanation}}</div>
          </div>
        `;
      }});

      viewer.innerHTML = html;
      mermaid.run();
    }}

    function filterItems() {{
      const q = document.getElementById('filter').value.toLowerCase();
      document.querySelectorAll('.list-item').forEach(el => {{
        const text = el.textContent.toLowerCase();
        el.style.display = text.includes(q) ? '' : 'none';
      }});
    }}

    // Auto-select first item
    const firstKey = Object.keys(vaultData)[0];
    if (firstKey) showItem(firstKey);
  </script>
</body>
</html>
"""


def export_single_diagram(entry, fmt="html"):
    """Exports a single diagram entry in HTML, Markdown, or Mermaid format."""
    target = entry.get("target", "component")
    diag_type = entry.get("type", "system")
    safe_name = re.sub(r"[^a-zA-Z0-9_\-]+", "_", f"{target}_{diag_type}").strip("_")

    if fmt == "html":
        title = entry.get("title", "Diagram")
        m_code = entry.get("mermaid", "")
        content = HTML_MERMAID_TEMPLATE.format(
            PAGE_TITLE=f"{title} - CodeMap Visualizer",
            DIAGRAM_TITLE=html.escape(title),
            TARGET_LABEL=f"Target: {html.escape(target)}",
            TIMESTAMP=entry.get("timestamp", ""),
            MODEL_USED=f"Model: {html.escape(entry.get('model', 'Gemini'))}",
            DIAGRAM_TYPE_LABEL=html.escape(DIAGRAM_TYPES.get(diag_type, {}).get("label", "Diagram")),
            MERMAID_CODE=html.escape(m_code),
            RAW_MERMAID_JSON=json.dumps(m_code),
            EXPLANATION_HTML=format_explanation_html(entry.get("explanation", "")),
            SAFE_FILENAME=safe_name,
        )
        filetypes = [("HTML File", "*.html"), ("All Files", "*.*")]
        ext = ".html"
    elif fmt == "mmd":
        content = entry.get("mermaid", "")
        filetypes = [("Mermaid File", "*.mmd"), ("Text File", "*.txt"), ("All Files", "*.*")]
        ext = ".mmd"
    else:  # md
        title = entry.get("title", "Diagram")
        content = (
            f"# {title}\n\nTarget: `{target}` | Generated: {entry.get('timestamp', '')} | Model: {entry.get('model', '')}\n\n"
            f"```mermaid\n{entry.get('mermaid', '')}\n```\n\n"
            f"## Plain-English Explanation\n\n{entry.get('explanation', '')}\n"
        )
        filetypes = [("Markdown File", "*.md"), ("Text File", "*.txt"), ("All Files", "*.*")]
        ext = ".md"

    save_path = filedialog.asksaveasfilename(
        title=f"Export Diagram ({fmt.upper()})",
        defaultextension=ext,
        initialfile=f"{safe_name}{ext}",
        filetypes=filetypes,
    )
    if save_path:
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(content)
        return save_path
    return None


def export_entire_vault_html(project_name, vault):
    """Exports all diagrams in the vault to a unified interactive web documentation suite."""
    items = vault.data.get("items", {})
    total_diagrams = sum(len(v) for v in items.values())

    sidebar_li = []
    for k in sorted(items.keys()):
        label = k[len("@dir:"):] if k.startswith("@dir:") else k
        icon = "📁 " if k.startswith("@dir:") else "📄 "
        cnt = len(items[k])
        sidebar_li.append(
            f'<li class="list-item" data-key="{html.escape(k)}" onclick="showItem(\'{html.escape(k)}\')">'
            f'{icon}{html.escape(label)}<span class="badge">{cnt}</span></li>'
        )

    out_html = VAULT_INDEX_TEMPLATE.format(
        PROJECT_NAME=html.escape(project_name),
        TOTAL_DIAGRAMS=total_diagrams,
        SIDEBAR_ITEMS="\n".join(sidebar_li),
        VAULT_DATA_JSON=json.dumps(items, ensure_ascii=False),
    )

    save_path = filedialog.asksaveasfilename(
        title="Export Complete Visuals Vault",
        defaultextension=".html",
        initialfile=f"{project_name}_Visuals_Vault.html",
        filetypes=[("HTML File", "*.html"), ("All Files", "*.*")],
    )

    if save_path:
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(out_html)
        return save_path
    return None


# --------------------------------------------------------------------------
# Standalone Visual Diagrams & Flows Studio Application
# --------------------------------------------------------------------------
class StandaloneDiagramStudio(tk.Tk):
    """
    Standalone Desktop Studio for CodeMap Visual Diagrams & Vault.
    Provides immediate visual inspection, AI-powered generation via OmniRoute / Gemini,
    pan/zoom rendering on canvas, and 1-click web/HTML export.
    """

    def __init__(self, initial_dir=None):
        super().__init__()
        self.title("CodeMap Visual Diagrams & Flows Studio (WCAG AAA High-Contrast)")
        self.geometry("1280x840")
        self.minsize(980, 640)

        # High-Contrast Color Palette
        self.configure(bg="#0f172a")

        self.root_path = initial_dir or os.path.abspath(r"E:\00 - Master Tools & Switch Board")
        if not os.path.exists(self.root_path):
            self.root_path = os.path.dirname(os.path.abspath(__file__))

        self.vault = DiagramVault(self.root_path)
        self.current_entry = None
        self.current_rel = "System Overview"
        self.current_is_file = False

        self._setup_styles()
        self._build_ui()
        self._refresh_vault_list()
        self._load_sample_or_latest()

    def _setup_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

    def _build_ui(self):
        # Top Header Bar
        top_bar = tk.Frame(self, bg="#1e293b", height=60, padx=16, pady=10)
        top_bar.pack(fill="x", side="top")

        lbl_title = tk.Label(
            top_bar,
            text="🗺️ CodeMap Visual Diagrams & Flows Studio",
            font=("Segoe UI", 14, "bold"),
            bg="#1e293b",
            fg="#38bdf8",
        )
        lbl_title.pack(side="left")

        lbl_path = tk.Label(
            top_bar,
            text=f"📂 {self.root_path}",
            font=("Segoe UI", 10),
            bg="#1e293b",
            fg="#94a3b8",
        )
        lbl_path.pack(side="left", padx=16)

        btn_chg = tk.Button(
            top_bar,
            text="📁 Change Folder",
            font=("Segoe UI", 9, "bold"),
            bg="#334155",
            fg="#f8fafc",
            activebackground="#475569",
            activeforeground="#ffffff",
            relief="flat",
            padx=10,
            pady=4,
            command=self._change_project_folder,
        )
        btn_chg.pack(side="right", padx=6)

        btn_open_vault = tk.Button(
            top_bar,
            text="📂 Open Vault Folder",
            font=("Segoe UI", 9, "bold"),
            bg="#334155",
            fg="#f8fafc",
            activebackground="#475569",
            activeforeground="#ffffff",
            relief="flat",
            padx=10,
            pady=4,
            command=lambda: self.vault.open_in_system_folder(self.current_rel, self.current_is_file),
        )
        btn_open_vault.pack(side="right", padx=6)

        # Main Splitter
        main_split = tk.PanedWindow(self, orient="horizontal", bg="#0f172a", sashwidth=6)
        main_split.pack(fill="both", expand=True, padx=8, pady=8)

        # Left Drawer: Visuals Vault & Saved Diagrams
        left_panel = tk.Frame(main_split, bg="#1e293b", width=340, padx=12, pady=12)
        left_panel.pack_propagate(False)
        main_split.add(left_panel, minsize=260)

        lbl_vault_head = tk.Label(
            left_panel,
            text="📚 Visuals Vault (Saved Diagrams)",
            font=("Segoe UI", 11, "bold"),
            bg="#1e293b",
            fg="#f8fafc",
        )
        lbl_vault_head.pack(anchor="w", pady=(0, 8))

        # Listbox for Vault items
        self.lst_diagrams = tk.Listbox(
            left_panel,
            bg="#0f172a",
            fg="#e2e8f0",
            selectbackground="#0284c7",
            selectforeground="#ffffff",
            font=("Segoe UI", 10),
            relief="flat",
            highlightthickness=1,
            highlightcolor="#38bdf8",
        )
        self.lst_diagrams.pack(fill="both", expand=True)
        self.lst_diagrams.bind("<<ListboxSelect>>", self._on_vault_item_selected)

        # Left Bottom Actions
        btn_export_all = tk.Button(
            left_panel,
            text="🌐 Export Complete Web Vault",
            font=("Segoe UI", 9, "bold"),
            bg="#0284c7",
            fg="#ffffff",
            relief="flat",
            padx=10,
            pady=6,
            command=self._export_complete_vault,
        )
        btn_export_all.pack(fill="x", pady=(10, 0))

        # Right Main Canvas & Control Suite
        right_panel = tk.Frame(main_split, bg="#0f172a", padx=10, pady=10)
        main_split.add(right_panel, minsize=600)

        # Right Action Toolbar
        action_bar = tk.Frame(right_panel, bg="#1e293b", height=50, padx=12, pady=8)
        action_bar.pack(fill="x", side="top", pady=(0, 8))

        tk.Label(
            action_bar,
            text="Type:",
            font=("Segoe UI", 10, "bold"),
            bg="#1e293b",
            fg="#f8fafc",
        ).pack(side="left")

        self.cmb_type = ttk.Combobox(
            action_bar,
            values=[v["label"] for v in DIAGRAM_TYPES.values()],
            state="readonly",
            width=24,
            font=("Segoe UI", 9),
        )
        self.cmb_type.current(0)
        self.cmb_type.pack(side="left", padx=8)

        btn_generate = tk.Button(
            action_bar,
            text="🪄 Generate with AI",
            font=("Segoe UI", 9, "bold"),
            bg="#10b981",
            fg="#ffffff",
            relief="flat",
            padx=12,
            pady=4,
            command=self._generate_with_ai,
        )
        btn_generate.pack(side="left", padx=6)

        btn_browser = tk.Button(
            action_bar,
            text="🌐 View in Browser",
            font=("Segoe UI", 9, "bold"),
            bg="#0284c7",
            fg="#ffffff",
            relief="flat",
            padx=10,
            pady=4,
            command=self._open_in_browser,
        )
        btn_browser.pack(side="left", padx=6)

        btn_export = tk.Button(
            action_bar,
            text="💾 Export",
            font=("Segoe UI", 9, "bold"),
            bg="#334155",
            fg="#f8fafc",
            relief="flat",
            padx=10,
            pady=4,
            command=self._export_single,
        )
        btn_export.pack(side="left", padx=6)

        btn_fit = tk.Button(
            action_bar,
            text="🔍 Fit View",
            font=("Segoe UI", 9, "bold"),
            bg="#334155",
            fg="#f8fafc",
            relief="flat",
            padx=8,
            pady=4,
            command=lambda: self.canvas_view.fit_view() if hasattr(self, "canvas_view") else None,
        )
        btn_fit.pack(side="right", padx=4)

        btn_dir = tk.Button(
            action_bar,
            text="🔄 Flip (TD/LR)",
            font=("Segoe UI", 9, "bold"),
            bg="#334155",
            fg="#f8fafc",
            relief="flat",
            padx=8,
            pady=4,
            command=lambda: self.canvas_view.toggle_direction() if hasattr(self, "canvas_view") else None,
        )
        btn_dir.pack(side="right", padx=4)

        # Right Center: Diagram Canvas
        canvas_holder = tk.Frame(right_panel, bg="#f8fafc", relief="solid", bd=1)
        canvas_holder.pack(fill="both", expand=True)

        self.canvas_view = DiagramCanvas(canvas_holder)
        self.canvas_view.pack(fill="both", expand=True)

        # Right Bottom: Explanation & Mermaid Editor Tabs
        bottom_tabs = ttk.Notebook(right_panel, height=160)
        bottom_tabs.pack(fill="x", side="bottom", pady=(8, 0))

        tab_exp = tk.Frame(bottom_tabs, bg="#1e293b", padx=10, pady=8)
        self.txt_explanation = tk.Text(
            tab_exp, bg="#0f172a", fg="#f8fafc", font=("Segoe UI", 10), wrap="word", relief="flat"
        )
        self.txt_explanation.pack(fill="both", expand=True)
        bottom_tabs.add(tab_exp, text="📝 Architecture & Flow Explanation")

        tab_code = tk.Frame(bottom_tabs, bg="#1e293b", padx=10, pady=8)
        self.txt_mermaid = tk.Text(
            tab_code, bg="#0f172a", fg="#38bdf8", font=("Consolas", 10), wrap="none", relief="flat"
        )
        self.txt_mermaid.pack(fill="both", expand=True)
        btn_re_render = tk.Button(
            tab_code,
            text="🔄 Apply Changes to Canvas",
            font=("Segoe UI", 9, "bold"),
            bg="#0284c7",
            fg="#ffffff",
            relief="flat",
            command=self._apply_mermaid_edit,
        )
        btn_re_render.pack(anchor="e", pady=(4, 0))
        bottom_tabs.add(tab_code, text="💻 Raw Mermaid Code (Live Editable)")

    def _refresh_vault_list(self):
        self.lst_diagrams.delete(0, tk.END)
        self.vault_entries = []
        items = self.vault.data.get("items", {})
        for key, diag_list in items.items():
            for d in diag_list:
                label = f"{d.get('type', 'system').upper()} | {d.get('title', key)}"
                self.lst_diagrams.insert(tk.END, label)
                self.vault_entries.append((key, d))

    def _load_sample_or_latest(self):
        if self.vault_entries:
            self.lst_diagrams.selection_set(0)
            self._load_diagram_entry(self.vault_entries[0][1])
        else:
            sample_mermaid = (
                "flowchart TD\n"
                "    User[\"👤 User / Operator\"] -->|Voice or Mouse| Cockpit[\"🎛️ Master Cockpit v6.1\"]\n"
                "    Cockpit -->|Direct3D11 Mirror| Phone[\"📱 Mobile Mirror (POCO / Infinix)\"]\n"
                "    Cockpit -->|Port 20128| OmniRoute[\"🧠 OmniRoute AI Hub\"]\n"
                "    Cockpit -->|Stealth Engine| Scrapling[\"🕷️ Scrapling Desktop Studio\"]\n"
                "    OmniRoute -->|Gemini 3 Flash| Gemini[\"⚡ Google AI Studio\"]\n"
                "    OmniRoute -->|Port 5000| Piper[\"🗣️ Piper Neural TTS\"]\n"
            )
            sample_exp = (
                "Master Unified Architecture Flow:\n"
                "- Master Cockpit coordinates the zero-margin mobile mirror, switchboard services, and AI.\n"
                "- OmniRoute delivers ultra-low-latency Gemini 3 Flash intelligence with local voice TTS."
            )
            sample_entry = {
                "id": "sample-master",
                "type": "system",
                "title": "Master Unified Architecture Flow",
                "mermaid": sample_mermaid,
                "explanation": sample_exp,
            }
            self.vault.add_diagram(
                "System Overview", False, "system", "Master Unified Architecture Flow", sample_mermaid, sample_exp
            )
            self._refresh_vault_list()
            self._load_diagram_entry(sample_entry)

    def _on_vault_item_selected(self, event):
        sel = self.lst_diagrams.curselection()
        if sel and sel[0] < len(self.vault_entries):
            entry = self.vault_entries[sel[0]][1]
            self._load_diagram_entry(entry)

    def _load_diagram_entry(self, entry):
        self.current_entry = entry
        self.canvas_view.display_diagram(entry)
        self.txt_explanation.delete("1.0", tk.END)
        self.txt_explanation.insert("1.0", entry.get("explanation", ""))
        self.txt_mermaid.delete("1.0", tk.END)
        self.txt_mermaid.insert("1.0", entry.get("mermaid", ""))

    def _apply_mermaid_edit(self):
        code = self.txt_mermaid.get("1.0", tk.END).strip()
        if code and self.current_entry:
            self.current_entry["mermaid"] = code
            self.canvas_view.display_diagram(self.current_entry)

    def _change_project_folder(self):
        d = filedialog.askdirectory(initialdir=self.root_path, title="Select Project / Codebase Folder")
        if d:
            self.root_path = os.path.abspath(d)
            self.vault = DiagramVault(self.root_path)
            self._refresh_vault_list()
            self._load_sample_or_latest()

    def _generate_with_ai(self):
        diag_label = self.cmb_type.get()
        diag_type = "system"
        for k, v in DIAGRAM_TYPES.items():
            if v["label"] == diag_label:
                diag_type = k
                break

        # Prompt user for optional specific requirements or instructions
        custom_req = simpledialog.askstring(
            "AI Visual Flow Designer",
            f"Enter custom instructions or flow requirements (optional):\n(Leave blank to auto-analyze {os.path.basename(self.root_path)})",
            parent=self
        )

        files_sample = [f for f in os.listdir(self.root_path) if not f.startswith(".")][:20]
        context = f"Project: {os.path.basename(self.root_path)}\nContents: {', '.join(files_sample)}"
        if custom_req and custom_req.strip():
            context += f"\nUser Custom Goal: {custom_req.strip()}"

        prompt = build_custom_text_diagram_prompt(context, diag_type=diag_type, title=os.path.basename(self.root_path))

        def _worker():
            try:
                import urllib.request
                omni_url = "http://127.0.0.1:20128/v1/chat/completions"
                headers = {
                    "Authorization": "Bearer sk-d4f0b046681944adc6eeff0deadd8e5b",
                    "Content-Type": "application/json",
                }
                body = {
                    "model": "obsidian-voice",
                    "messages": [{"role": "user", "content": prompt}],
                }
                req = urllib.request.Request(omni_url, data=json.dumps(body).encode(), headers=headers)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode())
                ai_text = data["choices"][0]["message"]["content"]
                mermaid_code, explanation = extract_mermaid_and_text(ai_text)
                title = f"{os.path.basename(self.root_path)} {DIAGRAM_TYPES[diag_type]['short']}"
                self.vault.add_diagram(
                    os.path.basename(self.root_path), False, diag_type, title, mermaid_code, explanation, model="gemini-3-flash"
                )

                # Try speech feedback
                try:
                    p = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
                    if p not in sys.path:
                        sys.path.insert(0, p)
                    import master_ai_bridge
                    master_ai_bridge.speak_text_async(f"Generated {title}. {explanation[:200]}")
                except Exception:
                    pass

                def _update():
                    self._refresh_vault_list()
                    entry = {
                        "id": "new",
                        "type": diag_type,
                        "title": title,
                        "mermaid": mermaid_code,
                        "explanation": explanation,
                    }
                    self._load_diagram_entry(entry)
                    messagebox.showinfo("Diagram Generated", f"Successfully generated {title} with Gemini 3 Flash!")

                self.after(0, _update)
            except Exception as e:
                def _err():
                    messagebox.showerror("AI Error", f"Could not generate diagram via OmniRoute:\n{e}")
                self.after(0, _err)

        threading.Thread(target=_worker, daemon=True).start()

    def _open_in_browser(self):
        if self.current_entry:
            open_interactive_browser_diagram(self.current_entry)
        else:
            messagebox.showinfo("No Diagram", "Please select or generate a diagram first.")

    def _export_single(self):
        if self.current_entry:
            saved = export_single_diagram(self.current_entry, "html")
            if saved:
                messagebox.showinfo("Exported", f"Saved to:\n{saved}")

    def _export_complete_vault(self):
        saved = export_entire_vault_html(os.path.basename(self.root_path), self.vault)
        if saved:
            messagebox.showinfo("Vault Exported", f"Complete Visuals Vault saved to:\n{saved}")


def main():
    app = StandaloneDiagramStudio()
    app.mainloop()


if __name__ == "__main__":
    main()


