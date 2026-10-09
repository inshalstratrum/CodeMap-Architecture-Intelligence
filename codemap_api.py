"""
CodeMap Full-Stack REST API & Web Server
Connects CodeMap's Python AST engine, AI providers, and Diagram Vault
to the modern React + Vite visual control center.
Runs on port 5273 using Python's standard library.
"""

import os
import sys
import json
import socket
import threading
import http.server
import socketserver
import webbrowser
import posixpath
import subprocess
import hashlib
import datetime
from urllib.parse import urlparse, parse_qs

import codemap_core as core
import codemap_diagrams as diagrams
import codemap_chat as chat

SERVER_PORT = 5273
_server_thread = None
_httpd = None
_actual_port = None

# In-memory active project state
_current_project = None
_current_path = ""
_current_stats = {}
_current_vault = None
_stop_event = threading.Event()


def get_visualizer_dist_dir():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "visualizer-ui", "dist")


def is_port_in_use(port):
    for host in ('127.0.0.1', '::1'):
        try:
            fam = socket.AF_INET6 if ':' in host else socket.AF_INET
            with socket.socket(fam, socket.SOCK_STREAM) as s:
                s.settimeout(0.2)
                if s.connect_ex((host, port)) == 0:
                    return True
        except Exception:
            pass
    return False


def serialize_project(proj):
    """Converts a CodeMap Project AST object into structured JSON for React."""
    if not proj:
        return None

    nodes_list = []
    for rel, node in proj.nodes.items():
        info = proj.info.get(rel, {})
        is_dir = node.is_dir
        parent_rel = posixpath.dirname(rel) if rel else ""

        # Language or folder type
        lang = info.get("lang", "Folder" if is_dir else "Code")

        if is_dir:
            # Aggregate external/peer dependencies for this folder
            files_in_dir = proj.files_under(rel)
            prefix = (rel + "/") if rel else ""
            out_targets = []
            in_sources = []
            seen_out = set()
            seen_in = set()
            ext_pkgs = set()
            defs = []
            total_lines = 0

            for f in files_in_dir:
                f_inf = proj.info.get(f, {})
                total_lines += f_inf.get("lines", 0)
                ext_pkgs.update(f_inf.get("external", []))
                if len(defs) < 25:
                    defs.extend(f_inf.get("defines", []))

                # Files this folder uses
                for t in f_inf.get("imports", []):
                    if not (prefix and t.startswith(prefix)) and t != rel and t not in seen_out:
                        seen_out.add(t)
                        out_targets.append(t)

                # Files that use this folder
                for u in proj.imported_by.get(f, []):
                    if not (prefix and u.startswith(prefix)) and u != rel and u not in seen_in:
                        seen_in.add(u)
                        in_sources.append(u)

            node_imports = out_targets
            node_imported_by = in_sources
            node_external = sorted(list(ext_pkgs))[:25]
            node_defines = list(dict.fromkeys(defs))[:25]
            node_lines = total_lines
            node_summary = f"Folder with {len(files_in_dir)} files ({total_lines} lines)."
        else:
            node_imports = info.get("imports", [])
            node_imported_by = proj.imported_by.get(rel, [])
            node_external = info.get("external", [])
            node_defines = info.get("defines", [])
            node_lines = info.get("lines", 0)
            node_summary = info.get("summary", "")

        nodes_list.append({
            "id": rel or "__root__",
            "rel": rel,
            "name": node.name if rel else proj.name,
            "path": node.path,
            "isDir": is_dir,
            "parentRel": parent_rel,
            "lang": lang,
            "role": info.get("role", "Folder" if is_dir else "File"),
            "lines": node_lines,
            "size": getattr(node, "size", 0),
            "imports": node_imports,
            "external": node_external,
            "importedBy": node_imported_by,
            "defines": node_defines,
            "endpoints": info.get("endpoints", []),
            "childrenCount": len(node.children) if is_dir else 0,
            "summary": node_summary,
        })

    # Group files by category for dedicated explorers
    json_files = []
    category_files = {"json": [], "typescript": [], "html_css": [], "python": [], "markdown": []}
    for rel, node in proj.nodes.items():
        if not node.is_dir and rel:
            lower = rel.lower()
            item = {"rel": rel, "name": node.name, "path": node.path, "folder": posixpath.dirname(rel) or "root"}
            if lower.endswith(".json"):
                json_files.append(item)
                category_files["json"].append(item)
            elif lower.endswith((".ts", ".tsx", ".js", ".jsx", ".mjs")):
                category_files["typescript"].append(item)
            elif lower.endswith((".html", ".htm", ".css", ".scss", ".sass")):
                category_files["html_css"].append(item)
            elif lower.endswith((".py", ".pyw")):
                category_files["python"].append(item)
            elif lower.endswith((".md", ".txt")):
                category_files["markdown"].append(item)

    # Overall project stats
    st = core.project_stats(proj, "")
    langs_dist = [{"name": k, "value": v} for k, v in st.get("langs", {}).items()]

    return {
        "name": proj.name,
        "rootPath": proj.root.path,
        "totalFiles": len(proj.files),
        "totalNodes": len(proj.nodes),
        "edgesCount": st.get("edges", 0),
        "languages": langs_dist,
        "jsonFiles": json_files,
        "categoryFiles": category_files,
        "nodes": nodes_list,
    }


class CodeMapAPIHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def end_headers(self):
        # Allow CORS for development and disable caching for API
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        if self.path.startswith('/api/'):
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/config":
            cfg = core.load_config()
            self._send_json(cfg)
            return

        elif path == "/api/project":
            global _current_project
            if _current_project:
                data = serialize_project(_current_project)
                self._send_json({"ok": True, "project": data})
            else:
                self._send_json({"ok": False, "project": None, "message": "No project scanned yet."})
            return

        elif path == "/api/vault":
            global _current_vault, _current_path
            if not _current_vault and _current_path:
                _current_vault = diagrams.DiagramVault(_current_path)
            items = _current_vault.get_all_items_with_diagrams() if _current_vault else []
            self._send_json({"ok": True, "items": items})
            return

        elif path == "/api/file-content":
            params = parse_qs(parsed.query)
            target = (params.get("path") or [""])[0]
            if not target or not os.path.isfile(target):
                self._send_json({"ok": False, "error": "File not found"}, status=404)
                return
            try:
                with open(target, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                self._send_json({"ok": True, "content": content, "path": target})
            except Exception as ex:
                self._send_json({"ok": False, "error": str(ex)}, status=500)
            return

        elif path == "/api/browse":
            # Opens native Windows folder browser
            chosen = ""
            try:
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk()
                root.withdraw()
                root.attributes("-topmost", True)
                chosen = filedialog.askdirectory(title="Select Codebase Folder to Visualize")
                root.destroy()
            except Exception as ex:
                print(f"[API] Browse error: {ex}")
            self._send_json({"path": chosen or ""})
            return

        # Serve static assets from visualizer-ui/dist
        dist_dir = get_visualizer_dist_dir()
        req_path = path.lstrip('/')
        local_file = os.path.join(dist_dir, req_path)

        if os.path.isfile(local_file):
            return super().do_GET()
        else:
            # SPA Fallback to index.html
            self.path = '/index.html'
            return super().do_GET()

    def do_POST(self):
        global _current_project, _current_path, _current_vault, _stop_event
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_json_body()

        if path == "/api/config":
            cfg = core.load_config()
            cfg.update(body)
            core.save_config(cfg)
            self._send_json({"ok": True, "message": "Settings saved"})
            return

        elif path == "/api/test-key":
            key = body.get("key", "").strip()
            provider = body.get("provider", "gemini")
            endpoint_url = body.get("endpointUrl", "").strip()

            if not key:
                self._send_json({"ok": False, "error": "API Key is empty"}, status=400)
                return

            import time, urllib.request
            start_t = time.time()
            try:
                if provider == "gemini":
                    test_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
                    req = urllib.request.Request(test_url)
                    with urllib.request.urlopen(req, timeout=12) as response:
                        raw = response.read().decode('utf-8')
                        data = json.loads(raw)
                        latency = int((time.time() - start_t) * 1000)
                        models = [m['name'].replace('models/', '') for m in data.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
                        pref = ["gemini-flash-latest", "gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"]
                        sorted_models = [m for m in pref if m in models] + [m for m in models if m not in pref]
                        self._send_json({"ok": True, "latencyMs": latency, "models": sorted_models})
                        return
                elif provider == "openai" or endpoint_url:
                    test_url = endpoint_url or "https://api.openai.com/v1/models"
                    req = urllib.request.Request(test_url, headers={"Authorization": f"Bearer {key}"})
                    with urllib.request.urlopen(req, timeout=12) as response:
                        raw = response.read().decode('utf-8')
                        data = json.loads(raw)
                        latency = int((time.time() - start_t) * 1000)
                        models = [m.get('id') for m in data.get('data', []) if m.get('id')]
                        self._send_json({"ok": True, "latencyMs": latency, "models": models})
                        return
            except Exception as ex:
                self._send_json({"ok": False, "error": str(ex)})
                return

        elif path == "/api/scan":
            folder_path = body.get("path", "").strip()
            show_hidden = body.get("showHidden", False)
            skip_junk = body.get("skipJunk", True)

            if not folder_path or not os.path.isdir(folder_path):
                self._send_json({"ok": False, "error": f"Invalid folder path: '{folder_path}'"}, status=400)
                return

            try:
                _stop_event.clear()
                _current_path = folder_path
                _current_vault = diagrams.DiagramVault(folder_path)

                counts = {"dirs": 0, "files": 0, "bytes": 0}
                root_node = core.scan_tree(folder_path, show_hidden, skip_junk, counts, _stop_event)
                proj = core.Project(root_node)
                proj.analyze()
                _current_project = proj

                serialized = serialize_project(proj)
                self._send_json({"ok": True, "project": serialized})
            except Exception as ex:
                self._send_json({"ok": False, "error": str(ex)}, status=500)
            return

        elif path == "/api/explain":
            rel = body.get("rel", "")
            is_file = body.get("isFile", False)
            cfg = core.load_config()

            if not _current_project:
                self._send_json({"ok": False, "error": "No project scanned"}, status=400)
                return

            try:
                context = chat.build_folder_context(_current_project, rel, is_file)
                custom_sys = cfg.get("system_diagrams", "") or "Explain this codebase clearly to a non-programmer."
                prompt = f"""Explain this {'file' if is_file else 'folder'} in plain English:
{context}

Format your response clearly:
1. Overview & Purpose (What does it do in 2 sentences)
2. How It Connects (What it uses and what uses it)
3. Key Components or Entry Points
4. Recommendations or Next Steps"""

                res = core.ai_generate(cfg, prompt, timeout=90, max_tokens=1400, system_instruction=custom_sys)
                self._send_json({"ok": True, "explanation": res})
            except Exception as ex:
                self._send_json({"ok": False, "error": str(ex)}, status=500)
            return

        elif path == "/api/generate-diagram":
            rel = body.get("rel", "")
            is_file = body.get("isFile", False)
            diag_type = body.get("type", "system")
            cfg = core.load_config()

            if not _current_project:
                self._send_json({"ok": False, "error": "No project scanned"}, status=400)
                return

            try:
                prompt = diagrams.build_diagram_prompt(_current_project, rel, diag_type)
                diag_model = cfg.get("model_diagrams", "").strip() or None
                diag_sys = cfg.get("system_diagrams", "").strip() or None
                diag_key = cfg.get("key_diagrams", "").strip()

                call_cfg = dict(cfg)
                if diag_key and call_cfg.get("provider") == "gemini":
                    call_cfg["keys"] = dict(call_cfg.get("keys", {}))
                    call_cfg["keys"]["gemini"] = diag_key

                res = core.ai_generate(call_cfg, prompt, timeout=120, max_tokens=2200,
                                       system_instruction=diag_sys, model_override=diag_model)
                mermaid_code, explanation = diagrams.extract_mermaid_and_text(res)
                spec = diagrams.DIAGRAM_TYPES.get(diag_type, diagrams.DIAGRAM_TYPES["system"])
                model_used = diag_model or call_cfg.get("models", {}).get("gemini", "AI")

                entry = None
                if _current_vault:
                    entry = _current_vault.add_diagram(rel, is_file, diag_type, spec["label"], mermaid_code, explanation, model_used)

                self._send_json({
                    "ok": True,
                    "type": diag_type,
                    "title": spec["label"],
                    "mermaid": mermaid_code,
                    "explanation": explanation,
                    "entry": entry
                })
            except Exception as ex:
                self._send_json({"ok": False, "error": str(ex)}, status=500)
            return

        elif path == "/api/generate-diagram-from-text":
            text = body.get("text", "").strip()
            diag_type = body.get("type", "system")
            title = body.get("title", "").strip() or "Custom Architecture"
            cfg = core.load_config()

            if not text:
                self._send_json({"ok": False, "error": "No description or text provided"}, status=400)
                return

            try:
                prompt = diagrams.build_custom_text_diagram_prompt(text, diag_type, title)
                diag_model = cfg.get("model_diagrams", "").strip() or None
                diag_sys = cfg.get("system_diagrams", "").strip() or None
                diag_key = cfg.get("key_diagrams", "").strip()

                call_cfg = dict(cfg)
                if diag_key and call_cfg.get("provider") == "gemini":
                    call_cfg["keys"] = dict(call_cfg.get("keys", {}))
                    call_cfg["keys"]["gemini"] = diag_key

                res = core.ai_generate(call_cfg, prompt, timeout=120, max_tokens=2200,
                                       system_instruction=diag_sys, model_override=diag_model)
                mermaid_code, explanation = diagrams.extract_mermaid_and_text(res)
                spec = diagrams.DIAGRAM_TYPES.get(diag_type, diagrams.DIAGRAM_TYPES["system"])
                model_used = diag_model or call_cfg.get("models", {}).get("gemini", "AI")

                if not _current_vault:
                    root_dir = _current_path or os.path.dirname(os.path.abspath(__file__))
                    _current_vault = diagrams.DiagramVault(root_dir)

                entry = _current_vault.add_diagram("@custom", False, diag_type, title, mermaid_code, explanation, model_used)

                self._send_json({
                    "ok": True,
                    "type": diag_type,
                    "title": title or spec["label"],
                    "mermaid": mermaid_code,
                    "explanation": explanation,
                    "entry": entry
                })
            except Exception as ex:
                self._send_json({"ok": False, "error": str(ex)}, status=500)
            return

        elif path == "/api/vault/save":
            rel = body.get("rel", "@custom")
            is_file = body.get("isFile", False)
            diag_type = body.get("type", "custom")
            title = body.get("title", "Custom Diagram")
            mermaid_code = body.get("mermaid", "").strip()
            explanation = body.get("explanation", "").strip()
            model_used = body.get("model", "Manual/Studio")

            if not mermaid_code:
                self._send_json({"ok": False, "error": "Mermaid code cannot be empty"}, status=400)
                return

            if not _current_vault:
                root_dir = _current_path or os.path.dirname(os.path.abspath(__file__))
                _current_vault = diagrams.DiagramVault(root_dir)

            entry = _current_vault.add_diagram(rel, is_file, diag_type, title, mermaid_code, explanation, model_used)
            self._send_json({"ok": True, "entry": entry})
            return

        elif path == "/api/open-system":
            target_path = body.get("path", "").strip()
            if not target_path and _current_path:
                rel = body.get("rel", "")
                if rel:
                    target_path = os.path.normpath(os.path.join(_current_path, *rel.split("/")))
                else:
                    target_path = _current_path

            if not target_path:
                self._send_json({"ok": False, "error": "No path specified"}, status=400)
                return

            try:
                abs_path = os.path.abspath(target_path)
                if os.path.exists(abs_path):
                    if os.path.isfile(abs_path):
                        subprocess.Popen(f'explorer /select,"{abs_path}"', shell=True)
                    else:
                        os.startfile(abs_path)
                    self._send_json({"ok": True, "path": abs_path})
                else:
                    self._send_json({"ok": False, "error": f"Path does not exist: {abs_path}"}, status=404)
            except Exception as ex:
                self._send_json({"ok": False, "error": str(ex)}, status=500)
            return

        elif path == "/api/search":
            query = body.get("query", "").strip().lower()
            if not query:
                self._send_json({"ok": True, "results": []})
                return

            if not _current_project:
                self._send_json({"ok": False, "error": "No project scanned"}, status=400)
                return

            results = []
            for node in _current_project.nodes.values():
                name_match = query in node.name.lower() or query in node.rel.lower()
                info = _current_project.info.get(node.rel, {})
                role_match = query in info.get("role", "").lower()
                def_match = any(query in d.lower() for d in info.get("defines", []))
                ext_match = any(query in e.lower() for e in info.get("external", []))

                if name_match or role_match or def_match or ext_match:
                    results.append({
                        "rel": node.rel,
                        "name": node.name,
                        "isDir": node.is_dir,
                        "lang": info.get("lang", ""),
                        "role": info.get("role", ""),
                        "defines": info.get("defines", [])[:5],
                        "matchType": "Name" if name_match else "Definition" if def_match else "Role"
                    })
                if len(results) >= 60:
                    break

            self._send_json({"ok": True, "results": results})
            return

        elif path == "/api/diagram/export-html":
            rel = body.get("rel", "")
            is_file = body.get("isFile", False)
            title = body.get("title", "Diagram")
            mermaid_code = body.get("mermaid", "").strip()
            explanation = body.get("explanation", "").strip()
            diag_type = body.get("type", "system")

            if not _current_vault:
                root_dir = _current_path or os.path.dirname(os.path.abspath(__file__))
                _current_vault = diagrams.DiagramVault(root_dir)

            entry = {
                "id": hashlib.sha1(f"{rel}:{mermaid_code[:30]}".encode("utf-8")).hexdigest()[:10],
                "type": diag_type,
                "title": title,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                "mermaid": mermaid_code,
                "explanation": explanation,
                "model": "CodeMap Studio",
                "target": rel or "(Custom)",
                "is_file": is_file,
            }

            path_written = _current_vault.get_annotated_export_path(rel, is_file, entry)
            open_folder = body.get("openFolder", False)
            if open_folder and os.path.exists(path_written):
                try:
                    subprocess.Popen(f'explorer /select,"{os.path.abspath(path_written)}"', shell=True)
                except Exception:
                    pass

            self._send_json({"ok": True, "path": path_written})
            return

        self._send_json({"error": "Endpoint not found"}, status=404)

    def _read_json_body(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            if length > 0:
                raw = self.rfile.read(length).decode('utf-8')
                return json.loads(raw)
        except Exception:
            pass
        return {}

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        payload = json.dumps(data).encode('utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def ensure_server_running(preferred_port=SERVER_PORT):
    global _server_thread, _httpd, _actual_port

    if _httpd is not None and _actual_port is not None:
        return _actual_port

    dist_dir = get_visualizer_dist_dir()
    if not os.path.exists(dist_dir) or not os.path.exists(os.path.join(dist_dir, "index.html")):
        return None

    socketserver.TCPServer.allow_reuse_address = True
    handler = lambda *args, **kwargs: CodeMapAPIHandler(*args, directory=dist_dir, **kwargs)

    for p in range(preferred_port, preferred_port + 25):
        if is_port_in_use(p):
            continue
        try:
            _httpd = socketserver.TCPServer(("", p), handler)
            _actual_port = p
            break
        except OSError:
            continue
    else:
        return None

    def _serve():
        try:
            _httpd.serve_forever()
        except Exception:
            pass

    _server_thread = threading.Thread(target=_serve, daemon=True)
    _server_thread.start()
    return _actual_port


def open_react_visualizer(file_path=None, json_data=None):
    port = ensure_server_running()
    if port:
        url = f"http://localhost:{port}/"
        webbrowser.open(url)
        return True
    return False


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        counts = {"dirs": 0, "files": 0, "bytes": 0}
        root_node = core.scan_tree(base_dir, False, True, counts, _stop_event)
        proj = core.Project(root_node)
        proj.analyze()
        _current_project = proj
        _current_path = base_dir
        _current_vault = diagrams.DiagramVault(base_dir)
        print(f"[CodeMap API] Pre-scanned '{base_dir}': {len(proj.files)} files, {len(proj.nodes)} nodes.")
    except Exception as ex:
        print(f"[CodeMap API] Initial scan notice: {ex}")

    p = ensure_server_running()
    if p:
        url = f"http://localhost:{p}/"
        print("=" * 68)
        print("  CodeMap React Visualizer & Full-Stack Control Center")
        print(f"  Running at: {url}")
        print("=" * 68)
        webbrowser.open(url)
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down server...")
    else:
        print("Error: Could not find visualizer-ui/dist.")

