"""
CodeMap - core engine (no window code in here)

  * scans a folder into a tree
  * reads Python / JavaScript / TypeScript / JSON / HTML / CSS / Markdown files
    and works out which file uses which (real dependency links)
  * talks to an AI helper (Claude / ChatGPT / Gemini - via CLI or API key)
  * exports everything as linked notes for an Obsidian vault

Only the Python standard library is used - nothing to pip-install.
"""

import ast
import datetime
import hashlib
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict

import codemap_diagrams as diagrams

# Dedicated storage directory inside the project folder:
APP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".codemap")
os.makedirs(APP_DIR, exist_ok=True)
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
CACHE_PATH = os.path.join(APP_DIR, "explanations.json")

build_diagram_prompt = diagrams.build_diagram_prompt
extract_mermaid_and_text = diagrams.extract_mermaid_and_text
DiagramVault = diagrams.DiagramVault
DIAGRAM_TYPES = diagrams.DIAGRAM_TYPES

MAX_ANALYZE_BYTES = 1_500_000
MAX_PROMPT_CHARS = 24_000

BRANCH, LAST, PIPE, SPACE = "├── ", "└── ", "│   ", "    "

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------
JUNK_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", ".idea", ".vscode",
    "dist", "build", ".next", ".nuxt", ".cache", ".pytest_cache", ".mypy_cache",
    ".tox", "coverage", ".svn", ".hg", "site-packages", ".gradle",
    "bower_components", ".turbo", ".parcel-cache", ".ruff_cache",
}

LANG_BY_EXT = {
    ".py": "Python", ".pyw": "Python",
    ".js": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".es": "JavaScript", ".es6": "JavaScript", ".jsx": "JavaScript (React)",
    ".ts": "TypeScript", ".tsx": "TypeScript (React)",
    ".vue": "Vue", ".svelte": "Svelte",
    ".json": "JSON", ".md": "Markdown", ".markdown": "Markdown",
    ".html": "HTML", ".htm": "HTML", ".css": "CSS", ".scss": "CSS",
    ".yml": "YAML", ".yaml": "YAML", ".toml": "TOML", ".ini": "Config",
    ".cfg": "Config", ".sql": "SQL", ".sh": "Shell", ".bat": "Batch",
    ".ps1": "PowerShell", ".txt": "Text", ".env": "Env", ".xml": "XML",
}
NAME_LANG = {"dockerfile": "Docker", "makefile": "Makefile"}

JS_CODE_EXTS = {".js", ".mjs", ".cjs", ".es", ".es6", ".jsx", ".ts", ".tsx", ".vue", ".svelte"}
JS_RESOLVE_EXTS = [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".es", ".es6",
                   ".vue", ".svelte", ".json", ".css", ".scss"]

NODE_BUILTINS = {
    "fs", "path", "os", "http", "https", "crypto", "url", "util", "events", "stream",
    "child_process", "zlib", "readline", "assert", "buffer", "net", "tls", "dns",
    "cluster", "module", "process", "querystring", "string_decoder", "timers", "tty",
    "vm", "worker_threads", "perf_hooks", "fs/promises", "http2", "dgram",
}

FALLBACK_STDLIB = {
    "abc", "argparse", "array", "ast", "asyncio", "base64", "bisect", "builtins",
    "calendar", "collections", "concurrent", "configparser", "contextlib", "copy",
    "csv", "ctypes", "dataclasses", "datetime", "decimal", "difflib", "email", "enum",
    "errno", "fnmatch", "functools", "gc", "getpass", "glob", "gzip", "hashlib",
    "heapq", "hmac", "html", "http", "importlib", "inspect", "io", "itertools", "json",
    "logging", "math", "mimetypes", "multiprocessing", "operator", "os", "pathlib",
    "pickle", "platform", "pprint", "queue", "random", "re", "secrets", "select",
    "shlex", "shutil", "signal", "socket", "sqlite3", "ssl", "stat", "statistics",
    "string", "struct", "subprocess", "sys", "tempfile", "textwrap", "threading",
    "time", "timeit", "tkinter", "traceback", "types", "typing", "unittest", "urllib",
    "uuid", "warnings", "weakref", "xml", "zipfile", "zlib", "__future__",
}
STDLIB = set(getattr(sys, "stdlib_module_names", None) or FALLBACK_STDLIB)

JS_FROM = re.compile(r"""\bfrom\s*['"]([^'"\n]+)['"]""")
JS_SIDE = re.compile(r"""\bimport\s*['"]([^'"\n]+)['"]""")
JS_REQ = re.compile(r"""\brequire\s*\(\s*['"]([^'"\n]+)['"]\s*\)""")
JS_DYN = re.compile(r"""\bimport\s*\(\s*['"]([^'"\n]+)['"]\s*\)""")
JS_EXPORT = re.compile(
    r"""^\s*export\s+(?:default\s+)?(?:async\s+)?(function\*?|class|const|let|var|interface|type|enum)\s+([A-Za-z_$][\w$]*)""",
    re.M)
JS_EXPORT_DEFAULT = re.compile(r"""^\s*export\s+default\s+(?!function|class|async)([A-Za-z_$][\w$]*)""", re.M)
JS_ENDPOINT = re.compile(r"""\b(?:app|router|server|fastify)\.(get|post|put|delete|patch)\s*\(\s*['"`]([^'"`]+)['"`]""")
PY_ENDPOINT = re.compile(r"""@\w+(?:\.\w+)*\.(get|post|put|delete|patch|route)\(\s*['"]([^'"]+)['"]""")
PY_IMPORT_FALLBACK = re.compile(r"^\s*(?:from\s+([\w.]+)\s+import\s+(.+)|import\s+([\w., ]+))", re.M)


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def clean_path(raw):
    p = (raw or "").strip().strip('"').strip("'").strip()
    return os.path.expandvars(os.path.expanduser(p))


def _attrs(entry):
    try:
        return entry.stat(follow_symlinks=False).st_file_attributes  # Windows only
    except (AttributeError, OSError):
        return 0


def is_hidden(entry):
    return entry.name.startswith(".") or bool(_attrs(entry) & 0x2)


def is_link(entry):
    try:
        return entry.is_symlink() or bool(_attrs(entry) & 0x400)
    except OSError:
        return False


def read_text(path, limit=MAX_ANALYZE_BYTES):
    try:
        with open(path, "rb") as f:
            data = f.read(limit)
    except OSError:
        return ""
    return data.decode("utf-8", errors="replace")


def first_line(s, n=200):
    for line in (s or "").strip().splitlines():
        line = line.strip(" \t#*/")
        if line:
            return line[:n]
    return ""


def lang_group(lang):
    if lang.startswith("Python"):
        return "py"
    if lang.startswith(("JavaScript", "TypeScript", "Vue", "Svelte")):
        return "js"
    if lang == "JSON":
        return "json"
    if lang in ("HTML", "CSS"):
        return "web"
    return "other"


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


# --------------------------------------------------------------------------
# Folder scanning + plain text tree
# --------------------------------------------------------------------------
class Node:
    __slots__ = ("name", "path", "rel", "is_dir", "parent", "children", "size", "mtime",
                 "skipped", "link", "error", "ext", "nfiles")

    def __init__(self, name, path, rel, is_dir, parent=None):
        self.name, self.path, self.rel, self.is_dir, self.parent = name, path, rel, is_dir, parent
        self.children = []
        self.size = 0
        self.mtime = 0
        self.skipped = False
        self.link = False
        self.error = None
        self.ext = "" if is_dir else os.path.splitext(name)[1].lower()
        self.nfiles = 0

    def ancestors(self):
        p = self.parent
        while p is not None:
            yield p
            p = p.parent


def scan_tree(root_path, show_hidden=False, skip_junk=True, counts=None, stop=None):
    root_path = os.path.abspath(root_path)
    counts = counts if counts is not None else {"dirs": 0, "files": 0}
    root = Node(os.path.basename(root_path.rstrip("\\/")) or root_path, root_path, "", True)

    def rec(node):
        if stop is not None and stop.is_set():
            return
        try:
            with os.scandir(node.path) as it:
                entries = list(it)
        except PermissionError:
            node.error = "Access denied"
            return
        except OSError as e:
            node.error = f"Error: {e.strerror or e}"
            return
        dirs, files = [], []
        for e in entries:
            if not show_hidden and is_hidden(e):
                continue
            try:
                d = e.is_dir(follow_symlinks=False)
            except OSError:
                d = False
            (dirs if d else files).append(e)
        dirs.sort(key=lambda e: e.name.lower())
        files.sort(key=lambda e: e.name.lower())
        for e in dirs:
            rel = f"{node.rel}/{e.name}" if node.rel else e.name
            ch = Node(e.name, e.path, rel, True, node)
            node.children.append(ch)
            counts["dirs"] += 1
            if is_link(e):
                ch.link = True
            elif skip_junk and e.name.lower() in JUNK_DIRS:
                ch.skipped = True
            else:
                rec(ch)
        for e in files:
            rel = f"{node.rel}/{e.name}" if node.rel else e.name
            ch = Node(e.name, e.path, rel, False, node)
            try:
                st = e.stat(follow_symlinks=False)
                ch.size, ch.mtime = st.st_size, st.st_mtime_ns
            except OSError:
                pass
            node.children.append(ch)
            counts["files"] += 1

    rec(root)

    def cnt(n):
        if not n.is_dir:
            return 1
        n.nfiles = sum(cnt(c) for c in n.children)
        return n.nfiles

    cnt(root)
    return root


def render_text_tree(root, include_files=True):
    lines = [root.path]
    counts = {"dirs": 0, "files": 0}

    def rec(node, prefix):
        items = [c for c in node.children if c.is_dir or include_files]
        for i, ch in enumerate(items):
            last = i == len(items) - 1
            conn = LAST if last else BRANCH
            child_prefix = prefix + (SPACE if last else PIPE)
            if ch.is_dir:
                counts["dirs"] += 1
                note = "  [skipped]" if ch.skipped else "  [link - not followed]" if ch.link else ""
                lines.append(f"{prefix}{conn}{ch.name}/{note}")
                if ch.error:
                    lines.append(f"{child_prefix}{LAST}[{ch.error}]")
                rec(ch, child_prefix)
            else:
                counts["files"] += 1
                lines.append(f"{prefix}{conn}{ch.name}")

    rec(root, "")
    if root.error:
        lines.append(f"{LAST}[{root.error}]")
    return "\n".join(lines), counts


# --------------------------------------------------------------------------
# Project analysis (who imports whom)
# --------------------------------------------------------------------------
def _strip_json_comments(text):
    text = re.sub(r'("(?:\\.|[^"\\])*")|//[^\n]*|/\*.*?\*/', lambda m: m.group(1) or "", text, flags=re.S)
    return re.sub(r",(\s*[}\]])", r"\1", text)


class Project:
    def __init__(self, root):
        self.root = root
        self.name = root.name
        self.nodes = {}
        self.info = {}
        self.imported_by = defaultdict(list)
        self.aliases = []
        self.base_urls = []
        self._py_suffix = defaultdict(list)
        self.root_names = {root.name, os.path.basename(os.path.dirname(root.path))}

        def idx(n):
            self.nodes[n.rel] = n
            for c in n.children:
                idx(c)

        idx(root)
        self.files = [r for r, n in self.nodes.items() if not n.is_dir]
        self.file_set = set(self.files)
        self._filename_index = defaultdict(list)
        for f in self.files:
            b = posixpath.basename(f)
            self._filename_index[b.lower()].append(f)
            stem = posixpath.splitext(b)[0].lower()
            if stem:
                self._filename_index[stem].append(f)
        self._dirname_index = defaultdict(list)
        for r, n in self.nodes.items():
            if n.is_dir and r:
                b = posixpath.basename(r)
                self._dirname_index[b.lower()].append(r)

    # ---- public ----------------------------------------------------------
    def analyze(self, progress=None):
        self._load_tsconfig()
        self._build_py_index()
        total = len(self.files)
        for i, rel in enumerate(self.files):
            self.info[rel] = self._analyze_file(rel)
            if progress and i % 25 == 0:
                progress(i, total)
        for rel, inf in self.info.items():
            for t in inf["imports"]:
                self.imported_by[t].append(rel)
        for k in self.imported_by:
            self.imported_by[k].sort()
        for rel, inf in self.info.items():
            n_by = len(self.imported_by.get(rel, []))
            inf["role"] = guess_role(rel, inf, len(inf["imports"]), n_by)
            inf["summary"] = offline_summary(rel, inf, n_by)

    def files_under(self, rel=""):
        if rel == "":
            return list(self.files)
        prefix = rel + "/"
        return [f for f in self.files if f.startswith(prefix)]

    def sig(self, rel):
        """A fingerprint that changes when a file (or anything inside a folder) changes."""
        if rel in self.file_set:
            n = self.nodes[rel]
            return f"{n.size}:{n.mtime}"
        h = hashlib.sha1()
        for f in sorted(self.files_under(rel)):
            n = self.nodes[f]
            h.update(f"{f}|{n.size}|{n.mtime};".encode("utf-8", "replace"))
        return h.hexdigest()[:20]

    def explainable_files(self):
        skip_names = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "uv.lock"}
        out = []
        for f in self.files:
            inf = self.info[f]
            n = self.nodes[f]
            if not inf["analyzed"] or n.size == 0 or posixpath.basename(f).lower() in skip_names:
                continue
            if inf["group"] not in ("py", "js", "json", "web"):
                continue
            if inf["group"] == "json" and n.size > 100_000:
                continue
            out.append(f)
        out.sort(key=lambda f: (-len(self.imported_by.get(f, [])), f))
        return out

    # ---- tsconfig / aliases ---------------------------------------------
    def _load_tsconfig(self):
        root = self.root.path
        cfgs = []
        for d in (root, os.path.dirname(root)):
            for name in ("tsconfig.json", "jsconfig.json", "tsconfig.app.json"):
                p = os.path.join(d, name)
                if os.path.isfile(p) and p not in cfgs:
                    cfgs.append(p)
        for f in self.files:
            if posixpath.basename(f).lower() in ("tsconfig.json", "jsconfig.json", "tsconfig.app.json"):
                p = os.path.join(root, *f.split("/"))
                if p not in cfgs:
                    cfgs.append(p)
        for path in cfgs[:12]:
            try:
                data = json.loads(_strip_json_comments(read_text(path)))
                opts = data.get("compilerOptions", {}) or {}
            except (ValueError, AttributeError):
                continue
            cfg_dir = os.path.dirname(path)
            base = os.path.join(cfg_dir, opts["baseUrl"]) if opts.get("baseUrl") else cfg_dir
            if opts.get("baseUrl"):
                b = self._to_rel(base)
                if b not in self.base_urls and not b.startswith(".."):
                    self.base_urls.append(b)
            for key, targets in (opts.get("paths") or {}).items():
                prefix = key[:-1] if key.endswith("*") else key
                rels = [self._to_rel(os.path.join(base, t.rstrip("*")))
                        for t in (targets if isinstance(targets, list) else [])]
                rels = [r for r in rels if not r.startswith("..")]
                if rels:
                    self.aliases.append((prefix, rels, key.endswith("*")))
        src_dirs = [r for r, n in self.nodes.items() if n.is_dir and n.name == "src" and not n.skipped]
        targets = list(dict.fromkeys(["", "src"] + src_dirs))
        for pre in ("@/", "~/", "@src/"):
            self.aliases.append((pre, targets, True))
        for b in ("", "src"):
            if b not in self.base_urls:
                self.base_urls.append(b)

    def _to_rel(self, abs_path):
        r = os.path.relpath(abs_path, self.root.path).replace("\\", "/")
        r = posixpath.normpath(r)
        return "" if r == "." else r

    # ---- Python -----------------------------------------------------------
    def _build_py_index(self):
        for f in self.files:
            if not f.lower().endswith(".py"):
                continue
            parts = f[:-3].split("/")
            if parts[-1] == "__init__":
                parts = parts[:-1]
            for i in range(len(parts)):
                self._py_suffix[".".join(parts[i:])].append(f)

    def _find_py(self, parts):
        if not parts:
            return "__init__.py" if "__init__.py" in self.file_set else None
        p = "/".join(parts)
        for cand in (p + ".py", p + "/__init__.py"):
            if cand in self.file_set:
                return cand
        return None

    def _res_abs(self, dotted, from_rel):
        parts = dotted.split(".")
        cands = self._py_suffix.get(dotted)
        if not cands and len(parts) > 1 and parts[0] in self.root_names:
            cands = self._py_suffix.get(".".join(parts[1:]))
        if not cands:
            return None
        if len(cands) == 1:
            return cands[0]
        here = from_rel.split("/")[:-1]

        def score(c):
            n = 0
            for a, b in zip(c.split("/")[:-1], here):
                if a != b:
                    break
                n += 1
            return (-n, c)

        return sorted(cands, key=score)[0]

    def _analyze_py(self, rel, text, info):
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError, RecursionError):
            tree = None
        reqs = []  # (lineno, level, module, names)
        if tree is not None:
            info["doc"] = first_line(ast.get_docstring(tree) or "")
            for n in ast.walk(tree):
                if isinstance(n, ast.Import):
                    for a in n.names:
                        reqs.append((n.lineno, 0, a.name, []))
                elif isinstance(n, ast.ImportFrom):
                    reqs.append((n.lineno, n.level or 0, n.module or "", [a.name for a in n.names]))
            for n in tree.body:
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    info["defines"].append(f"{n.name}()")
                elif isinstance(n, ast.ClassDef):
                    info["defines"].append(f"class {n.name}")
        else:
            info["meta"].append("This file could not be fully read (it may contain a syntax error).")
            for m in PY_IMPORT_FALLBACK.finditer(text):
                if m.group(1):
                    reqs.append((0, 0, m.group(1), [x.strip().split(" ")[0] for x in m.group(2).split(",")]))
                else:
                    for mod in m.group(3).split(","):
                        reqs.append((0, 0, mod.strip().split(" ")[0], []))
        imports, external = [], []
        here = posixpath.dirname(rel)
        for _, level, module, names in sorted(reqs, key=lambda r: r[0]):
            found = []
            if level:
                base = here.split("/") if here else []
                up = level - 1
                if up > len(base):
                    continue
                base = base[:len(base) - up]
                modparts = module.split(".") if module else []
                sub = [self._find_py(base + modparts + [nm]) for nm in names]
                sub = [x for x in sub if x]
                mod_t = self._find_py(base + modparts) if modparts or not sub else None
                found.extend(sub)
                if mod_t and (not sub or not mod_t.endswith("__init__.py")):
                    found.insert(0, mod_t)
            else:
                for nm in names:
                    if nm != "*":
                        t = self._res_abs(f"{module}.{nm}", rel)
                        if t:
                            found.append(t)
                if not found:
                    t = self._res_abs(module, rel)
                    if t:
                        found.append(t)
                if not found and module:
                    top = module.split(".")[0]
                    if top not in STDLIB and top not in self.root_names:
                        external.append(top)
            imports.extend(found)
        info["imports"], info["external"] = imports, external
        info["endpoints"] = [f"{m.group(1).upper()} {m.group(2)}" for m in PY_ENDPOINT.finditer(text)][:20]

    # ---- JavaScript / TypeScript -----------------------------------------
    def _find_js(self, base):
        base = posixpath.normpath(base) if base else "."
        if base in (".", "") or base.startswith(".."):
            return None
        if base in self.file_set:
            return base
        for ext in JS_RESOLVE_EXTS:
            if base + ext in self.file_set:
                return base + ext
        stem, e = posixpath.splitext(base)
        if e in (".js", ".jsx", ".mjs", ".cjs"):
            for ext in (".ts", ".tsx"):
                if stem + ext in self.file_set:
                    return stem + ext
        for ext in JS_RESOLVE_EXTS:
            if f"{base}/index{ext}" in self.file_set:
                return f"{base}/index{ext}"
        return None

    def _res_js(self, spec, rel):
        spec = spec.split("?")[0].split("#")[0]
        if not spec:
            return None
        if spec.startswith("."):
            return self._find_js(posixpath.join(posixpath.dirname(rel), spec))
        for prefix, targets, wildcard in self.aliases:
            if (wildcard and spec.startswith(prefix)) or (not wildcard and spec == prefix):
                tail = spec[len(prefix):] if wildcard else ""
                for t in targets:
                    r = self._find_js(posixpath.join(t, tail))
                    if r:
                        return r
        for b in self.base_urls:
            r = self._find_js(posixpath.join(b, spec))
            if r:
                return r
        return None

    @staticmethod
    def _external_js(spec):
        spec = spec.split("?")[0]
        if not spec or spec.startswith((".", "/", "node:", "@/", "~/")):
            return None
        parts = spec.split("/")
        name = "/".join(parts[:2]) if spec.startswith("@") else parts[0]
        if name in NODE_BUILTINS or spec in NODE_BUILTINS:
            return None
        return name

    def _analyze_js(self, rel, text, info):
        specs = []
        for rx in (JS_FROM, JS_SIDE, JS_REQ, JS_DYN):
            for m in rx.finditer(text):
                specs.append((m.start(), m.group(1)))
        specs.sort()
        imports, external = [], []
        for _, spec in specs:
            t = self._res_js(spec, rel)
            if t:
                imports.append(t)
            else:
                ext = self._external_js(spec)
                if ext:
                    external.append(ext)
        info["imports"], info["external"] = imports, external
        defs = []
        for m in JS_EXPORT.finditer(text):
            kind, name = m.group(1), m.group(2)
            if kind.startswith("function"):
                defs.append(f"{name}()")
            elif kind in ("const", "let", "var"):
                defs.append(name)
            else:
                defs.append(f"{kind} {name}")
        for m in JS_EXPORT_DEFAULT.finditer(text):
            defs.append(f"{m.group(1)} (default export)")
        info["defines"] = list(dict.fromkeys(defs))[:20]
        info["endpoints"] = [f"{m.group(1).upper()} {m.group(2)}" for m in JS_ENDPOINT.finditer(text)][:20]
        m = re.match(r"\s*(?:/\*+\s*|//+\s*)([^\n*][^\n]*)", text)
        if m:
            info["doc"] = first_line(m.group(1).replace("*/", ""))

    # ---- other file types --------------------------------------------------
    def _analyze_json(self, rel, text, info):
        name = posixpath.basename(rel).lower()
        try:
            data = json.loads(text)
        except ValueError:
            try:
                data = json.loads(_strip_json_comments(text))
            except ValueError:
                info["meta"].append("JSON file with errors - could not be read.")
                return
        if name == "package.json" and isinstance(data, dict):
            info["doc"] = str(data.get("description", ""))[:200]
            info["meta"].append(f"Project name: {data.get('name', '?')} (version {data.get('version', '?')})")
            scripts = list((data.get("scripts") or {}).keys())
            if scripts:
                info["meta"].append("Commands you can run: " + ", ".join(scripts[:12]))
            deps = list((data.get("dependencies") or {}).keys())
            dev = list((data.get("devDependencies") or {}).keys())
            if deps:
                info["meta"].append(f"Uses {len(deps)} libraries: " + ", ".join(deps[:15]) + (" ..." if len(deps) > 15 else ""))
            if dev:
                info["meta"].append(f"{len(dev)} development-only tools (e.g. " + ", ".join(dev[:6]) + ")")
        elif isinstance(data, dict):
            keys = list(data.keys())
            info["meta"].append(f"Top-level entries ({len(keys)}): " + ", ".join(map(str, keys[:12])) + (" ..." if len(keys) > 12 else ""))
        elif isinstance(data, list):
            info["meta"].append(f"A list with {len(data)} items.")

    def _resolve_local(self, spec, rel):
        spec = spec.split("?")[0].split("#")[0].strip()
        if not spec or spec.startswith(("http:", "https:", "//", "#", "mailto:", "data:", "javascript:")):
            return None
        base = posixpath.normpath(spec.lstrip("/")) if spec.startswith("/") else \
            posixpath.normpath(posixpath.join(posixpath.dirname(rel), spec))
        return base if base in self.file_set else None

    def _resolve_doc_link(self, target, from_rel):
        target = target.split("|")[0].split("#")[0].strip().replace("\\", "/").rstrip("/")
        if not target or target.startswith(("http:", "https:", "//", "#", "mailto:", "data:", "javascript:")):
            return None
        # 1. Try direct local relative resolution
        res = self._resolve_local(target, from_rel)
        if res:
            return res
        if not target.endswith(".md"):
            res = self._resolve_local(target + ".md", from_rel)
            if res:
                return res
        # Check if target is a known directory node relative to from_rel or root
        here_dir = posixpath.dirname(from_rel)
        rel_dir = posixpath.normpath(posixpath.join(here_dir, target)) if here_dir else target
        if rel_dir in self.nodes:
            return rel_dir
        if target in self.nodes:
            return target
        # 2. Try vault/project-wide filename index (for Obsidian style wikilinks)
        base = posixpath.basename(target).lower()
        cands = self._filename_index.get(base) or self._filename_index.get(base + ".md")
        if not cands:
            stem = posixpath.splitext(base)[0].lower()
            cands = self._filename_index.get(stem)
        if not cands and hasattr(self, "_dirname_index"):
            cands = self._dirname_index.get(base)
        if cands:
            if len(cands) == 1:
                return cands[0]
            def dist_score(cand):
                cand_dir = posixpath.dirname(cand)
                p1, p2 = here_dir.split("/"), cand_dir.split("/")
                common = sum(1 for a, b in zip(p1, p2) if a == b)
                return -common
            return sorted(cands, key=dist_score)[0]
        return None

    def _analyze_file(self, rel):
        node = self.nodes[rel]
        base = posixpath.basename(rel).lower()
        lang = LANG_BY_EXT.get(node.ext) or NAME_LANG.get(base)
        info = {"lang": lang or "Other", "group": lang_group(lang or "Other"), "lines": 0,
                "imports": [], "external": [], "defines": [], "endpoints": [], "doc": "",
                "meta": [], "analyzed": False, "role": "", "summary": ""}
        if lang is None or node.size > MAX_ANALYZE_BYTES:
            return info
        text = read_text(node.path)
        info["analyzed"] = True
        info["lines"] = text.count("\n") + 1 if text else 0
        try:
            if node.ext in (".py", ".pyw"):
                self._analyze_py(rel, text, info)
            elif node.ext in JS_CODE_EXTS:
                self._analyze_js(rel, text, info)
            elif node.ext == ".json":
                self._analyze_json(rel, text, info)
            elif node.ext in (".md", ".markdown"):
                m = re.search(r"^#{1,3}\s+(.+)$", text, re.M)
                info["doc"] = m.group(1).strip()[:200] if m else first_line(text)
                # Parse Obsidian WikiLinks: [[Target]] or [[Target|Alias]]
                for wl in re.findall(r"\[\[([^\]]+)\]\]", text):
                    t = self._resolve_doc_link(wl, rel)
                    if t and t != rel:
                        info["imports"].append(t)
                # Parse Standard Markdown Links: [Title](target)
                for ml in re.findall(r"\[(?:[^\]]*)\]\(([^)]+)\)", text):
                    t = self._resolve_doc_link(ml, rel)
                    if t and t != rel:
                        info["imports"].append(t)
                # Parse Backtick file/folder references: `filename.md`, `folder/`
                for bt in re.findall(r"`([^`\n\r]+)`", text):
                    t = self._resolve_doc_link(bt.strip(), rel)
                    if t and t != rel:
                        info["imports"].append(t)
                # Parse Quoted file references
                for q in re.findall(r"""["']([^"'\n\r]+\.(?:md|markdown|py|js|ts|tsx|json|html|css|txt))["']""", text):
                    t = self._resolve_doc_link(q.strip(), rel)
                    if t and t != rel:
                        info["imports"].append(t)
            elif node.ext in (".html", ".htm"):
                m = re.search(r"<title>(.*?)</title>", text, re.S | re.I)
                info["doc"] = first_line(m.group(1)) if m else ""
                for spec in re.findall(r"""(?:src|href)\s*=\s*["']([^"']+)["']""", text, re.I):
                    t = self._resolve_local(spec, rel)
                    if t:
                        info["imports"].append(t)
            elif node.ext in (".css", ".scss"):
                for spec in re.findall(r"""@import\s+(?:url\()?['"]?([^'")\s;]+)""", text):
                    t = self._resolve_local(spec, rel)
                    if t:
                        info["imports"].append(t)
        except Exception as e:  # noqa: BLE001 - never let one bad file stop the scan
            info["meta"].append(f"(Could not fully analyze this file: {e})")
        info["imports"] = [t for t in dict.fromkeys(info["imports"]) if t != rel]
        info["external"] = list(dict.fromkeys(info["external"]))
        return info


# --------------------------------------------------------------------------
# Plain-English guesses that work with no AI at all
# --------------------------------------------------------------------------
ENTRY_NAMES = {"main.py", "app.py", "__main__.py", "manage.py", "wsgi.py", "asgi.py", "run.py",
               "server.js", "server.ts", "index.js", "index.ts", "main.js", "main.ts", "app.js",
               "app.ts", "main.tsx", "index.tsx", "index.jsx", "main.jsx", "app.tsx", "app.jsx"}


def guess_role(rel, info, n_imp, n_by):
    name = posixpath.basename(rel).lower()
    stem = name.rsplit(".", 1)[0]
    parts = [p.lower() for p in rel.split("/")]
    ext = os.path.splitext(name)[1]
    tokens = set(re.split(r"[^a-z0-9]+", stem))

    if name == "__init__.py" and info.get("lines", 0) <= 2:
        return "Package marker - tells Python this folder is a group of code files"
    if name in ENTRY_NAMES:
        return "Entry point - where the program (or a section of it) starts running"
    if re.search(r"(^|[._-])(test|tests|spec)([._-]|$)", name) or {"tests", "__tests__", "test", "spec"} & set(parts):
        return "Automated test - checks that other code works correctly"
    if name in ("package.json", "tsconfig.json", "jsconfig.json", "pyproject.toml", "setup.py",
                "requirements.txt", "dockerfile", "docker-compose.yml", ".env", "vite.config.ts",
                "vite.config.js", "webpack.config.js", "next.config.js") or "config" in tokens \
            or "settings" in tokens or "constants" in tokens:
        return "Configuration - settings that control how the project is built or behaves"
    if ext in (".md", ".markdown"):
        return "Documentation - text written for humans"
    if ext in (".css", ".scss"):
        return "Styling - controls how the interface looks"
    if ext in (".html", ".htm"):
        return "Web page / template"
    if tokens & {"model", "models", "schema", "schemas", "entity", "entities", "types", "interfaces"}:
        return "Data structure - describes what the information in the system looks like"
    if tokens & {"migration", "migrations", "db", "database", "sql", "orm", "repository", "repositories"}:
        return "Database-related - stores or reads saved data"
    if tokens & {"route", "routes", "router", "routers", "controller", "controllers", "api",
                 "endpoint", "endpoints", "views", "handlers", "handler"} or info.get("endpoints"):
        return "Web requests (API) - code that receives or sends requests over the web"
    if "middleware" in tokens:
        return "Middleware - checks or changes requests on their way through"
    if tokens & {"service", "services", "usecase", "usecases"}:
        return "Business logic - does the real work of the app"
    if tokens & {"store", "context", "state", "reducer", "reducers", "slice"}:
        return "Shared app state - remembers information while the app runs"
    if name.startswith("use") and len(stem) > 3 and ext in JS_CODE_EXTS:
        return "Reusable interface logic (a 'hook')"
    if tokens & {"util", "utils", "helper", "helpers", "common", "lib", "tools", "shared"}:
        return "Helper functions shared by other files"
    if ext in (".tsx", ".jsx", ".vue", ".svelte"):
        return "User-interface piece - part of what the user sees on screen"
    if ext == ".json":
        return "Data or settings file"
    if info["group"] in ("py", "js"):
        if n_by == 0 and n_imp > 0:
            return "Top-level file - uses other files, but nothing else uses it (possible starting point)"
        if n_by >= 3:
            return f"Shared building block - used by {n_by} other files"
        return "Code file"
    return f"{info['lang']} file"


def offline_summary(rel, info, n_by):
    parts = [info["role"] + "."]
    if info.get("doc"):
        parts.append(f"Its own description: \"{info['doc']}\".")
    if info["imports"]:
        names = ", ".join(posixpath.basename(x) for x in info["imports"][:5])
        more = f" and {len(info['imports']) - 5} more" if len(info["imports"]) > 5 else ""
        parts.append(f"It relies on {len(info['imports'])} other project file(s): {names}{more}.")
    if n_by:
        parts.append(f"{n_by} other file(s) rely on it.")
    if info["defines"]:
        parts.append("It defines: " + ", ".join(info["defines"][:8]) + (" ..." if len(info["defines"]) > 8 else "") + ".")
    if info["endpoints"]:
        parts.append("It exposes web addresses such as " + ", ".join(info["endpoints"][:4]) + ".")
    return " ".join(parts)


def project_stats(project, rel=""):
    files = project.files_under(rel)
    langs = Counter(project.info[f]["lang"] for f in files)
    code = [f for f in files if project.info[f]["group"] in ("py", "js")]
    entry = [f for f in code if project.info[f]["role"].startswith("Entry point")]
    entry += [f for f in code if project.info[f]["role"].startswith("Top-level") and f not in entry]
    hubs = sorted(((f, len(project.imported_by.get(f, []))) for f in code), key=lambda x: -x[1])
    hubs = [h for h in hubs if h[1] > 0][:10]
    orphans = [f for f in code if not project.info[f]["imports"] and not project.imported_by.get(f)
               and not project.info[f]["role"].startswith(("Automated test", "Configuration", "Package marker"))]
    ext = Counter()
    for f in files:
        for e in project.info[f]["external"]:
            ext[e] += 1
    endpoints = [(e, f) for f in files for e in project.info[f]["endpoints"]]
    edges = sum(len(project.info[f]["imports"]) for f in files)
    return {"files": len(files), "langs": langs, "entry": entry[:10], "hubs": hubs, "orphans": orphans[:15],
            "externals": ext.most_common(15), "endpoints": endpoints[:25], "edges": edges}


def folder_summary(project, rel):
    node = project.nodes[rel]
    files = project.files_under(rel)
    prefix = rel + "/" if rel else ""
    inside = set(files)
    out_c, in_c = Counter(), Counter()
    for f in files:
        for t in project.info[f]["imports"]:
            if t not in inside:
                out_c[posixpath.dirname(t) or "(root)"] += 1
        for u in project.imported_by.get(f, []):
            if u not in inside:
                in_c[posixpath.dirname(u) or "(root)"] += 1
    top = sorted(files, key=lambda f: -len(project.imported_by.get(f, [])))
    top = [f for f in top if project.imported_by.get(f)][:8]
    subdirs = [c for c in node.children if c.is_dir]
    return {"files": len(files), "subfolders": len(subdirs), "langs": Counter(project.info[f]["lang"] for f in files),
            "top": top, "out": out_c.most_common(8), "in": in_c.most_common(8), "prefix": prefix}


# --------------------------------------------------------------------------
# AI helpers: prompts, providers, cache
# --------------------------------------------------------------------------
class AIError(Exception):
    pass


PROVIDERS = {
    "claude_cli": {"label": "Claude Code CLI  (uses your Claude subscription - no key)", "kind": "cli", "cmd": "claude",
                   "hint": "Easiest if you already use Claude Code in a terminal. Nothing to paste."},
    "codex_cli": {"label": "Codex CLI  (uses your ChatGPT subscription - no key)", "kind": "cli", "cmd": "codex",
                  "hint": "Uses the 'codex' command-line tool from OpenAI. Nothing to paste."},
    "gemini_cli": {"label": "Gemini CLI  (uses your Google account - no key)", "kind": "cli", "cmd": "gemini",
                   "hint": "Uses the 'gemini' command-line tool from Google. Nothing to paste."},
    "gemini": {"label": "Google Gemini API  (paste a key - has a free tier)", "kind": "api", "model": "gemini-2.5-flash",
               "url": "https://aistudio.google.com/apikey",
               "hint": "Cheapest way to start: create a free key at Google AI Studio and paste it above."},
    "anthropic": {"label": "Claude API  (paste an API key)", "kind": "api", "model": "claude-3-5-sonnet-latest",
                  "url": "https://console.anthropic.com/settings/keys",
                  "hint": "Separate from a Claude.ai subscription - API usage is billed by use."},
    "openai": {"label": "OpenAI API  (paste an API key)", "kind": "api", "model": "gpt-4o-mini",
               "url": "https://platform.openai.com/api-keys",
               "hint": "Separate from a ChatGPT subscription - API usage is billed by use."},
    "offline": {"label": "Offline only  (no AI - free, uses code analysis only)", "kind": "offline",
                "hint": "Everything except the written explanations still works."},
}
PROVIDER_ORDER = ["claude_cli", "gemini_cli", "codex_cli", "gemini", "anthropic", "openai", "offline"]

DEFAULT_CFG = {
    "provider": None,
    "keys": {},
    "models": {},
    # Separate API keys per task type (Gemini only — other providers use keys dict)
    "key_diagrams": "",    # Dedicated Gemini API key for diagram generation (optional)
    "key_voice": "",       # Dedicated Gemini API key for voice/chat (optional)
    "model_diagrams": "",
    "model_voice": "",
    "system_diagrams": "",
    "system_voice": "",
    "skip_junk": True,
    "include_files": True,
    "show_hidden": False,
    "last_path": "",
    "last_vault": ""
}


def cli_path(provider):
    cmd = PROVIDERS.get(provider, {}).get("cmd")
    return shutil.which(cmd) if cmd else None


def load_config():
    cfg = json.loads(json.dumps(DEFAULT_CFG))
    cfg.update(load_json(CONFIG_PATH, {}))
    if cfg.get("provider") not in PROVIDERS:
        cfg["provider"] = next((p for p in ("claude_cli", "gemini_cli", "codex_cli") if cli_path(p)), "offline")
    return cfg


def save_config(cfg):
    try:
        save_json(CONFIG_PATH, cfg)
    except OSError:
        pass


def provider_ready(cfg):
    """Returns (ok, message)."""
    p = cfg.get("provider")
    spec = PROVIDERS.get(p)
    if not spec or spec["kind"] == "offline":
        return False, "No AI helper is selected yet."
    if spec["kind"] == "cli" and not cli_path(p):
        return False, f"The '{spec['cmd']}' command was not found on this PC."
    if spec["kind"] == "api" and not (cfg.get("keys", {}).get(p) or "").strip():
        return False, "No API key has been entered yet."
    return True, ""


def _format_http_error(e):
    body = e.read().decode("utf-8", errors="replace")
    msg = ""
    try:
        err_json = json.loads(body)
        if isinstance(err_json, dict):
            if "error" in err_json:
                err_data = err_json["error"]
                if isinstance(err_data, dict) and "message" in err_data:
                    msg = err_data["message"]
                elif isinstance(err_data, str):
                    msg = err_data
            elif "message" in err_json:
                msg = err_json["message"]
    except Exception:
        pass
    if not msg:
        msg = body[:500]
    hint = " (check that the API key is correct)" if e.code in (401, 403) else \
        " (the model name may be outdated - change it in AI Settings)" if e.code == 404 else \
        " (rate limit reached - please wait a moment)" if e.code == 429 else ""
    return f"The AI service answered with error {e.code}{hint}.\n{msg}"


def _get_json(url, headers, timeout):
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise AIError(_format_http_error(e))
    except urllib.error.URLError as e:
        raise AIError(f"Could not reach the AI service: {e.reason}")
    except TimeoutError:
        raise AIError("The AI service took too long to answer.")


def _post_json(url, headers, payload, timeout, retries=2):
    import time
    data = json.dumps(payload).encode("utf-8")
    hdrs = {"Content-Type": "application/json"}
    hdrs.update(headers)
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=data, headers=hdrs, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                time.sleep(2.0 * (attempt + 1))
                continue
            raise AIError(_format_http_error(e))
        except urllib.error.URLError as e:
            raise AIError(f"Could not reach the AI service: {e.reason}")
        except TimeoutError:
            raise AIError("The AI service took too long to answer.")


def fetch_available_models(provider, key):
    """Fetches free and available models directly from the provider's API."""
    if not key or not key.strip():
        return []
    key = key.strip()
    if provider == "gemini":
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={urllib.parse.quote(key)}"
        try:
            data = _get_json(url, {}, timeout=15)
            models = []
            for item in data.get("models", []):
                name = item.get("name", "")
                methods = item.get("supportedGenerationMethods", [])
                if "generateContent" in methods:
                    if name.startswith("models/"):
                        name = name[len("models/"):].strip()
                    if name and name not in models:
                        models.append(name)
            pref = ["gemini-2.5-flash", "gemini-3.8-flash", "gemini-3.6-flash", "gemini-flash-latest", "gemini-2.5-flash-lite", "gemini-2.5-pro"]
            sorted_m = [m for m in pref if m in models] + [m for m in models if m not in pref]
            return sorted_m
        except Exception as e:
            raise AIError(f"Gemini API model fetch failed: {e}")
    elif provider == "openai":
        url = "https://api.openai.com/v1/models"
        try:
            data = _get_json(url, {"Authorization": f"Bearer {key}"}, timeout=15)
            models = [m.get("id") for m in data.get("data", []) if m.get("id")]
            pref = ["gpt-4o-mini", "gpt-4o", "o3-mini", "gpt-4-turbo"]
            return [m for m in pref if m in models] + [m for m in models if m not in pref]
        except Exception as e:
            raise AIError(f"OpenAI API model fetch failed: {e}")
    elif provider == "anthropic":
        return ["claude-3-5-sonnet-latest", "claude-3-7-sonnet-latest", "claude-3-5-haiku-latest", "claude-3-opus-latest"]
    return []


def _run_cli(provider, prompt, timeout):
    cmd = PROVIDERS[provider]["cmd"]
    args = [cmd]
    if provider == "claude_cli":
        args += ["-p", "--output-format", "text"]
    try:
        res = subprocess.run(args, input=prompt, capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=timeout, cwd=tempfile.gettempdir(),
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        raise AIError("The AI command took too long to answer.")
    except OSError as e:
        raise AIError(f"Could not start the AI command: {e}")
    out = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", res.stdout or "").strip()
    if res.returncode != 0 or not out:
        err = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", res.stderr or "").strip()[-600:]
        raise AIError(f"The AI command failed (exit code {res.returncode}).\n{err}")
    return out


def ai_generate(cfg, prompt, timeout=180, max_tokens=1600, system_instruction=None, model_override=None):
    p = cfg.get("provider")
    ok, msg = provider_ready(cfg)
    if not ok:
        raise AIError(msg)
    spec = PROVIDERS[p]
    if spec["kind"] == "cli":
        full_p = f"{system_instruction}\n\n{prompt}" if system_instruction else prompt
        return _run_cli(p, full_p, timeout)
    key = cfg["keys"][p].strip()
    model = (model_override or cfg.get("models", {}).get(p) or spec["model"]).strip()
    if model.startswith("models/"):
        model = model[len("models/"):].strip()
    model = model.replace(" ", "-")

    if p == "anthropic":
        payload = {"model": model, "max_tokens": max_tokens, "messages": [{"role": "user", "content": prompt}]}
        if system_instruction:
            payload["system"] = system_instruction
        d = _post_json("https://api.anthropic.com/v1/messages",
                       {"x-api-key": key, "anthropic-version": "2023-06-01"},
                       payload, timeout)
        text = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
    elif p == "openai":
        msgs = []
        if system_instruction:
            msgs.append({"role": "system", "content": system_instruction})
        msgs.append({"role": "user", "content": prompt})
        d = _post_json("https://api.openai.com/v1/chat/completions", {"Authorization": f"Bearer {key}"},
                       {"model": model, "messages": msgs}, timeout)
        text = (d.get("choices") or [{}])[0].get("message", {}).get("content", "")
    else:  # gemini
        candidate_models = [model]
        for fb in ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.5-flash-lite", "gemini-flash-latest"]:
            if fb not in candidate_models:
                candidate_models.append(fb)

        primary_err = None
        last_err = None
        d = None
        for idx, m in enumerate(candidate_models):
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{urllib.parse.quote(m)}:generateContent"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            if system_instruction:
                payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
            try:
                d = _post_json(url, {"x-goog-api-key": key}, payload, timeout)
                break
            except AIError as e:
                err_str = str(e)
                if idx == 0:
                    primary_err = e
                last_err = e
                if "404" in err_str or "503" in err_str or "high demand" in err_str or "overloaded" in err_str or "unavailable" in err_str:
                    continue
                raise e

        if d is None:
            if primary_err and "503" not in str(primary_err):
                raise primary_err
            if last_err:
                raise last_err
            raise AIError("Could not complete Gemini request across available models.")
        cands = d.get("candidates") or []
        if not cands:
            feedback = d.get("promptFeedback", {})
            block_reason = feedback.get("blockReason")
            if block_reason:
                raise AIError(f"Gemini blocked the prompt ({block_reason}).")
            raise AIError("The AI service returned no candidates.")
        cand = cands[0]
        finish_reason = cand.get("finishReason")
        text = "".join(x.get("text", "") for x in cand.get("content", {}).get("parts", []))
        if not text and finish_reason and finish_reason not in ("STOP", ""):
            raise AIError(f"Gemini stopped generation ({finish_reason}).")
    text = (text or "").strip()
    if not text:
        raise AIError("The AI service returned an empty answer.")
    return text


STYLE_RULES = (
    "Write for a non-programmer (a social-science student who builds software with AI 'vibe coding' tools). "
    "Use plain text only - no markdown symbols such as ** or #. Put each section title in CAPITAL LETTERS on its own line, "
    "and use short bullet points starting with '- '. Explain any technical term the first time you use it. "
    "Do not use tools and do not ask questions."
)


def build_file_prompt(project, rel):
    node, info = project.nodes[rel], project.info[rel]
    text = read_text(node.path)
    cut = ""
    if len(text) > MAX_PROMPT_CHARS:
        text, cut = text[:MAX_PROMPT_CHARS], "\n[... file truncated for length ...]"
    imps = ", ".join(info["imports"][:25]) or "none"
    by = ", ".join(project.imported_by.get(rel, [])[:25]) or "none"
    ext = ", ".join(info["external"][:20]) or "none"
    return (
        f"You are helping someone understand a code project called '{project.name}'.\n\n"
        f"FILE: {rel}\nLANGUAGE: {info['lang']}\n"
        f"PROJECT FILES THIS FILE USES: {imps}\nPROJECT FILES THAT USE THIS FILE: {by}\n"
        f"OUTSIDE LIBRARIES IT USES: {ext}\n\n"
        f"Explain this file. {STYLE_RULES}\nUse exactly these sections:\n"
        "PURPOSE (1-2 sentences: what job does this file do in the project?)\n"
        "HOW IT WORKS (step by step, simple language)\n"
        "HOW IT CONNECTS (which related files it depends on, which depend on it, and why)\n"
        "IF IT BROKE (what would stop working, described from a user's point of view)\n"
        "Keep it under 250 words.\n\n"
        f"FILE CONTENT:\n<<<\n{text}{cut}\n>>>\n"
    )


def build_overview_prompt(project, rel=""):
    scope = project.files_under(rel)
    inside = set(scope)
    lines = []
    for f in scope[:160]:
        inf = project.info[f]
        lines.append(f"- {f} [{inf['lang']}] {inf['role']}; uses {len(inf['imports'])} files; "
                     f"used by {len(project.imported_by.get(f, []))}; defines: {', '.join(inf['defines'][:6]) or '-'}"
                     + (f"; doc: {inf['doc']}" if inf["doc"] else ""))
    edges = [f"{f} -> {t}" for f in scope for t in project.info[f]["imports"] if t in inside][:220]
    st = project_stats(project, rel)
    what = f"the folder '{rel}'" if rel else f"the whole project '{project.name}'"
    return (
        f"You are helping someone understand {what}.\n\n"
        f"FILES:\n" + "\n".join(lines) + "\n\nWHO USES WHOM (file -> file it uses):\n" + ("\n".join(edges) or "none") +
        "\n\nOUTSIDE LIBRARIES: " + (", ".join(f"{n} ({c})" for n, c in st["externals"]) or "none") +
        "\nWEB ADDRESSES FOUND: " + (", ".join(f"{e} in {f}" for e, f in st["endpoints"][:15]) or "none") +
        f"\n\nExplain {what} as a whole. {STYLE_RULES}\nUse exactly these sections:\n"
        "BIG PICTURE (what does this appear to be, and what is it for?)\n"
        "MAIN PARTS (group the files into 3-6 parts and say what each part does)\n"
        "HOW THINGS CONNECT (how information or requests flow between the parts)\n"
        "WHERE TO START READING (the 5 most useful files to open first, in order, and why)\n"
        "Keep it under 400 words.\n"
    )


class ExplainCache:
    """Remembers AI explanations on disk so nothing is paid for twice."""

    def __init__(self, root_path):
        self.key = hashlib.sha1(os.path.abspath(root_path).lower().encode("utf-8")).hexdigest()[:16]
        self.lock = threading.Lock()
        self.all = load_json(CACHE_PATH, {})
        self.data = self.all.setdefault(self.key, {})

    @staticmethod
    def key_for(rel, is_file):
        return rel if is_file else f"@dir:{rel}"

    def get(self, key, sig):
        with self.lock:
            e = self.data.get(key)
        return e["text"] if e and e.get("sig") == sig else None

    def put(self, key, sig, text, provider):
        with self.lock:
            self.data[key] = {"sig": sig, "text": text, "provider": provider,
                              "time": datetime.datetime.now().isoformat(timespec="seconds")}
            try:
                fresh = load_json(CACHE_PATH, {})
                fresh[self.key] = self.data
                save_json(CACHE_PATH, fresh)
            except OSError:
                pass


# --------------------------------------------------------------------------
# Obsidian export
# --------------------------------------------------------------------------
def find_vault_root(path):
    cur = os.path.abspath(path)
    while True:
        if os.path.isdir(os.path.join(cur, ".obsidian")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def _safe_name(s):
    s = re.sub(r'[\\/:*?"<>|#^\[\]]', "_", s).strip(" .")
    return s or "file"


def note_name(rel):
    base = posixpath.basename(rel)
    stem, ext = posixpath.splitext(base)
    return _safe_name(f"{stem} ({ext[1:]})" if ext and stem else base)


def ai_to_markdown(text):
    out = []
    for line in text.splitlines():
        s = line.strip()
        if s and s == s.upper() and re.search(r"[A-Z]{3,}", s) and len(s) < 60 and not s.startswith("-"):
            out.append(f"### {s.capitalize()}")
        else:
            out.append(line)
    return "\n".join(out)


def _yaml(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def export_to_obsidian(project, cache, parent_dir, progress=None):
    """Writes linked notes. Returns (export_folder, overview_note_path, note_count)."""
    parent_dir = os.path.abspath(parent_dir)
    vault = find_vault_root(parent_dir) or parent_dir
    out_dir = os.path.join(parent_dir, _safe_name(f"CodeMap - {project.name}"))
    files_dir = os.path.join(out_dir, "Files")
    os.makedirs(files_dir, exist_ok=True)

    def note_path(rel):
        return os.path.join(files_dir, *rel.split("/")[:-1], note_name(rel) + ".md")

    def link(rel):
        p = os.path.relpath(note_path(rel), vault).replace("\\", "/")[:-3]
        return f"[[{p}|{posixpath.basename(rel)}]]"

    def ai_text(rel):
        return cache.get(rel, project.sig(rel)) if cache else None

    total = len(project.files)
    for i, rel in enumerate(project.files):
        n, inf = project.nodes[rel], project.info[rel]
        used_by = project.imported_by.get(rel, [])
        tag_lang = re.sub(r"[^a-z0-9]+", "-", inf["lang"].lower()).strip("-") or "other"
        md = ["---", "type: code-file", f"language: {_yaml(inf['lang'])}", f"path: {_yaml(rel)}",
              f"role: {_yaml(inf['role'])}", f"lines: {inf['lines']}",
              f"uses_count: {len(inf['imports'])}", f"used_by_count: {len(used_by)}",
              f"tags: [codemap, codemap/{tag_lang}]", "---", "",
              f"# {posixpath.basename(rel)}", "",
              f"> `{rel}` - {inf['lang']} - {inf['lines']} lines - {human_size(n.size)}", "",
              f"**Role:** {inf['role']}", ""]
        ai = ai_text(rel)
        md.append("## What this file does")
        md.append("")
        if ai:
            md.append(ai_to_markdown(ai))
        else:
            md.append(inf["summary"])
            md.append("")
            md.append("_Offline summary. Run 'Explain all files with AI' in CodeMap and export again for a full plain-English explanation._")
        md.append("")
        md.append("## Uses (depends on)")
        md.append("")
        md.extend([f"- {link(t)}" for t in inf["imports"]] or ["- _nothing inside this project_"])
        md.append("")
        md.append("## Used by")
        md.append("")
        md.extend([f"- {link(u)}" for u in used_by] or ["- _no other project file uses this one_"])
        md.append("")
        if inf["external"]:
            md += ["## Outside libraries", "", ", ".join(f"`{e}`" for e in inf["external"]), ""]
        if inf["defines"]:
            md += ["## Defines", ""] + [f"- `{d}`" for d in inf["defines"]] + [""]
        if inf["endpoints"]:
            md += ["## Web addresses (API)", ""] + [f"- `{e}`" for e in inf["endpoints"]] + [""]
        if inf["meta"]:
            md += ["## Details", ""] + [f"- {m}" for m in inf["meta"]] + [""]
        p = note_path(rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(md))
        if progress and i % 10 == 0:
            progress(i, total)

    # ---- overview note ----------------------------------------------------
    st = project_stats(project, "")
    ov_ai = cache.get(ResolveKey.root(), project.sig("")) if cache else None
    md = ["---", "type: code-overview", "tags: [codemap]", "---", "", f"# {project.name} - project map", "",
          f"_Generated by CodeMap on {datetime.date.today().isoformat()}_ - source folder: `{project.root.path}`", "",
          f"**{st['files']} files** - **{st['edges']} links between files** - "
          + ", ".join(f"{k} ({v})" for k, v in st["langs"].most_common(6)), "",
          "## The big picture", ""]
    if ov_ai:
        md.append(ai_to_markdown(ov_ai))
    else:
        md.append("_Run 'Explain with AI' on the project (click the top node in CodeMap) and export again to get a written overview here._")
    md += ["", "## Where to start", ""]
    md.extend([f"- {link(f)} - {project.info[f]['role']}" for f in st["entry"]] or ["- _no obvious entry point found_"])
    md += ["", "## Most-used files (many others depend on them)", ""]
    md.extend([f"- {link(f)} - used by {c} file{'s' if c != 1 else ''}" for f, c in st["hubs"]] or ["- _none_"])
    if st["externals"]:
        md += ["", "## Outside libraries used", "", ", ".join(f"`{n}` ({c})" for n, c in st["externals"])]
    if st["endpoints"]:
        md += ["", "## Web addresses (API) found", ""] + [f"- `{e}` - {link(f)}" for e, f in st["endpoints"]]
    md += ["", "## How the folders connect", "", "```mermaid", "flowchart LR"]
    md += _mermaid_folder_edges(project)
    md += ["```", "", "## Full file tree", ""]

    def tree(node, depth):
        for c in node.children:
            pad = "  " * depth
            if c.is_dir:
                extra = " _(skipped)_" if c.skipped else ""
                md.append(f"{pad}- **{c.name}/**{extra}")
                tree(c, depth + 1)
            else:
                md.append(f"{pad}- {link(c.rel)}")

    tree(project.root, 0)
    md += ["", "## Tips for Obsidian", "",
           "- Open the **Graph view** to see every file as a dot and every import as a line.",
           "- In Graph view > Groups, add `tag:#codemap/python`, `tag:#codemap/typescript`... to colour by language.",
           "- Click any link above to open a file's note, then read its **Uses** and **Used by** lists.", ""]
    overview = os.path.join(out_dir, "00 - Project Overview.md")
    with open(overview, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(md))
    if progress:
        progress(total, total)
    return out_dir, overview, total + 1


class ResolveKey:
    @staticmethod
    def root():
        return ExplainCache.key_for("", False)


def _mermaid_folder_edges(project):
    def group(rel, depth):
        parts = rel.split("/")[:-1]
        return "/".join(parts[:depth]) or "(root)"

    top_groups = {group(f, 1) for f in project.files if project.info[f]["group"] in ("py", "js")}
    depth = 2 if len(top_groups) < 5 else 1
    edges = Counter()
    for f in project.files:
        for t in project.info[f]["imports"]:
            a, b = group(f, depth), group(t, depth)
            if a != b:
                edges[(a, b)] += 1
    if not edges:
        return ["  none[\"No links between different folders found\"]"]
    ids, lines = {}, []
    for (a, b), c in edges.most_common(45):
        for g in (a, b):
            if g not in ids:
                ids[g] = f"g{len(ids)}"
                lines.append(f"  {ids[g]}[\"{g.replace(chr(34), '')}\"]")
        lines.append(f"  {ids[a]} -->|{c}| {ids[b]}")
    return lines
