"""
CodeMap - see how your code fits together.

Double-click "Run CodeMap.bat" to start (keep this file and codemap_core.py together).
"""

import os
import posixpath
import queue
import subprocess
import sys
import threading
import urllib.parse
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

import codemap_core as core
import codemap_diagrams as diagrams

GROUP_COL = {          # (fill, outline)
    "py": ("#dbeafe", "#3b82f6"),
    "js": ("#fef3c7", "#d97706"),
    "json": ("#dcfce7", "#16a34a"),
    "web": ("#fce7f3", "#db2777"),
    "other": ("#f1f5f9", "#94a3b8"),
}
FOLDER_COL = ("#e2e8f0", "#94a3b8")
ROOT_COL = ("#1e293b", "#0f172a")
GREEN, ORANGE = "#16a34a", "#ea580c"


# ==========================================================================
# Mind map (canvas)
# ==========================================================================
class MindMap(ttk.Frame):
    def __init__(self, master, on_select, on_context_menu=None):
        super().__init__(master)
        self.on_select = on_select
        self.on_context_menu = on_context_menu
        self.project = None
        self.expanded = {""}
        self.selected = None
        self.zoom = 1.0
        self.pos = {}
        self._fonts = {}
        self._region = (0, 0, 100, 100)
        self._down = (0, 0)
        self._moved = False

        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=6, pady=(6, 2))
        ttk.Button(bar, text="Expand all", command=self.expand_all).pack(side="left", padx=2)
        ttk.Button(bar, text="Collapse all", command=self.collapse_all).pack(side="left", padx=2)
        ttk.Button(bar, text=" - ", width=3, command=lambda: self.set_zoom(self.zoom / 1.2)).pack(side="left", padx=(14, 2))
        ttk.Button(bar, text=" + ", width=3, command=lambda: self.set_zoom(self.zoom * 1.2)).pack(side="left", padx=2)
        ttk.Button(bar, text="Reset zoom", command=lambda: self.set_zoom(1.0)).pack(side="left", padx=2)

        legend = ttk.Frame(self)
        legend.pack(fill="x", padx=6, pady=(0, 4))
        for text, key in (("Python", "py"), ("JS / TS", "js"), ("JSON", "json"), ("HTML / CSS", "web"), ("Other", "other")):
            tk.Label(legend, text=f" {text} ", bg=GROUP_COL[key][0], fg="#111827", font=("Segoe UI", 8),
                     highlightbackground=GROUP_COL[key][1], highlightthickness=1).pack(side="left", padx=2)
        tk.Label(legend, text="   green = this file/folder uses ", fg=GREEN, font=("Segoe UI", 8, "bold")).pack(side="left")
        tk.Label(legend, text=" orange = uses this file/folder ", fg=ORANGE, font=("Segoe UI", 8, "bold")).pack(side="left")

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(body, bg="#ffffff", highlightthickness=0)
        ys = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
        xs = ttk.Scrollbar(body, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)

        c = self.canvas
        c.bind("<ButtonPress-1>", self._on_press)
        c.bind("<B1-Motion>", self._on_drag)
        c.bind("<ButtonRelease-1>", self._on_release)
        c.bind("<Button-3>", self._on_right_click)
        c.bind("<Button-2>", self._on_right_click)
        c.bind("<Motion>", self._on_motion)
        c.bind("<MouseWheel>", self._on_wheel)
        c.bind("<Button-4>", self._on_wheel)
        c.bind("<Button-5>", self._on_wheel)
        c.bind("<Enter>", lambda e: c.focus_set())
        self.render()

    def _on_right_click(self, e):
        if self.project is None:
            return
        rel = self._hit(self.canvas.canvasx(e.x), self.canvas.canvasy(e.y))
        if rel is not None:
            # Right-click only selects and highlights; DO NOT toggle expand/collapse!
            self.selected = rel
            self.render()
            self.on_select(rel)
        if self.on_context_menu:
            self.on_context_menu(e, rel if rel is not None else self.selected)

    # ---- public --------------------------------------------------------
    def set_project(self, project):
        self.project = project
        self.expanded = {""}
        self.selected = ""
        self.zoom = 1.0
        self.render()
        self.after(80, lambda: self.center_on(""))

    def expand_all(self):
        if not self.project:
            return
        self.expanded = {r for r, n in self.project.nodes.items() if n.is_dir and n.children and not n.skipped and not n.link}
        self.render()
        self.after(30, lambda: self.center_on(""))

    def collapse_all(self):
        self.expanded = {""}
        self.render()
        self.center_on("")

    def reveal(self, rel):
        """Open every folder above `rel`, select it and scroll it into view."""
        if not self.project or rel not in self.project.nodes:
            return
        for a in self.project.nodes[rel].ancestors():
            self.expanded.add(a.rel)
        self.selected = rel
        self.render()
        self.after(30, lambda: self.center_on(rel))

    def set_zoom(self, z):
        z = max(0.5, min(2.2, z))
        fx, fy = self.canvas.xview()[0], self.canvas.yview()[0]
        self.zoom = z
        self.render()
        self.canvas.xview_moveto(fx)
        self.canvas.yview_moveto(fy)

    def center_on(self, rel, include_children=True):
        if not self.project or rel not in self.pos:
            return
        cw = max(50, self.canvas.winfo_width())
        ch = max(50, self.canvas.winfo_height())
        x, y, w, h = self.pos[rel]
        if include_children and rel in self.expanded:
            prefix = (rel + "/") if rel else ""
            cluster = [self.pos[r] for r in self.pos if r == rel or (prefix and r.startswith(prefix))]
            if cluster:
                min_x = min(p[0] for p in cluster)
                max_x = max(p[0] + p[2] for p in cluster)
                min_y = min(p[1] for p in cluster)
                max_y = max(p[1] + p[3] for p in cluster)
                mid_x = (min_x + max_x) / 2
                mid_y = (min_y + max_y) / 2
                self._set_view(mid_x - cw / 2, mid_y - ch / 2)
                return
        self._set_view(x + w / 2 - cw / 2, y + h / 2 - ch / 2)

    # ---- drawing -------------------------------------------------------
    def _font(self, size, bold=False):
        key = (size, bold)
        if key not in self._fonts:
            self._fonts[key] = tkfont.Font(family="Segoe UI", size=size, weight="bold" if bold else "normal")
        return self._fonts[key]

    def _rrect(self, x1, y1, x2, y2, r, **kw):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return self.canvas.create_polygon(pts, smooth=True, **kw)

    def render(self, anchor=None):
        c = self.canvas
        c.delete("all")
        self.pos = {}
        if self.project is None:
            c.create_text(30, 30, anchor="nw", fill="#64748b", font=self._font(11),
                          text="Paste a folder path above and press Scan.\nYour mind map will appear here.")
            c.configure(scrollregion=(0, 0, 500, 200))
            return
        z = self.zoom
        fs = max(7, round(10 * z))
        f, fb = self._font(fs), self._font(fs, True)
        H, VG, HG, PAD, M = round(28 * z), round(8 * z), round(60 * z), round(10 * z), round(24 * z)
        root = self.project.root

        def kids(n):
            return n.children if (n.is_dir and n.rel in self.expanded and not n.skipped and not n.link) else []

        def label(n):
            if n.is_dir:
                if n.skipped:
                    return f"{n.name}  (skipped)"
                if n.link:
                    return f"{n.name}  (link)"
                if not n.children:
                    return f"▫ {n.name}"
                if n.rel in self.expanded:
                    return f"▾ {n.name}"
                return f"▸ {n.name}   {n.nfiles}"
            return n.name

        def fnt(n):
            return fb if n.is_dir else f

        levels = {}

        def collect(n, d):
            levels.setdefault(d, []).append(n)
            for ch in kids(n):
                collect(ch, d + 1)

        collect(root, 0)
        colx = {0: M}
        for d in sorted(levels):
            maxw = max(fnt(n).measure(label(n)) + 2 * PAD for n in levels[d])
            colx[d + 1] = colx[d] + maxw + HG

        row = [0]

        def place(n, d):
            ch = kids(n)
            if not ch:
                y = M + row[0] * (H + VG)
                row[0] += 1
            else:
                ys = [place(k, d + 1) for k in ch]
                y = (ys[0] + ys[-1]) / 2
            self.pos[n.rel] = (colx[d], y, fnt(n).measure(label(n)) + 2 * PAD, H)
            return y

        place(root, 0)

        def connect(n):
            px, py, pw, ph = self.pos[n.rel]
            for k in kids(n):
                cx, cy, cw, chh = self.pos[k.rel]
                x1, y1, x2, y2 = px + pw, py + ph / 2, cx, cy + chh / 2
                xm = (x1 + x2) / 2
                c.create_line(x1, y1, xm, y1, xm, y2, x2, y2, smooth=True, fill="#cbd5e1", width=max(1, round(1.6 * z)))
                connect(k)

        connect(root)

        for rel, (x, y, w, h) in self.pos.items():
            n = self.project.nodes[rel]
            if n is root:
                fill, outline, fg = ROOT_COL[0], ROOT_COL[1], "#ffffff"
            elif n.is_dir:
                fill, outline = ("#f8fafc", "#e2e8f0") if n.skipped else FOLDER_COL
                fg = "#94a3b8" if n.skipped else "#1e293b"
            else:
                fill, outline = GROUP_COL[self.project.info.get(rel, {}).get("group", "other")]
                fg = "#111827"
            sel = rel == self.selected
            self._rrect(x, y, x + w, y + h, round(8 * z), fill=fill,
                        outline="#111827" if sel else outline, width=3 if sel else 1)
            c.create_text(x + PAD, y + h / 2, anchor="w", text=label(n), font=fnt(n), fill=fg)

        bb = c.bbox("all") or (0, 0, 100, 100)
        cw = max(c.winfo_width(), 800)
        ch = max(c.winfo_height(), 600)
        pad_x = max(round(cw * 2.0), 2500)
        pad_y = max(round(ch * 2.0), 2000)
        self._region = (bb[0] - pad_x, bb[1] - pad_y, bb[2] + pad_x, bb[3] + pad_y)
        c.configure(scrollregion=self._region)
        self._draw_relations()
        if anchor and anchor[0] in self.pos:
            self._set_view(self.pos[anchor[0]][0] - anchor[1], self.pos[anchor[0]][1] - anchor[2])

    def _arc(self, a, b, color, dashed):
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        z = self.zoom
        y1, y2 = ay + ah / 2, by + bh / 2
        if abs(ax - bx) < 4:
            x1, x2 = ax + aw, bx + bw
            lift = max(40.0 * z, abs(y2 - y1) * 0.2)
            pts = [x1, y1, max(x1, x2) + lift, (y1 + y2) / 2, x2, y2]
        else:
            x1, x2 = (ax + aw, bx) if ax < bx else (ax, bx + bw)
            lift = min(90.0, abs(x2 - x1) / 4 + 15) * z
            pts = [x1, y1, (x1 + x2) / 2, (y1 + y2) / 2 - lift, x2, y2]
        kw = dict(smooth=True, arrow=tk.LAST, arrowshape=(10, 12, 4), fill=color, width=max(2, round(2.2 * z)), tags=("rel",))
        if dashed:
            kw["dash"] = (5, 3)
        self.canvas.create_line(*pts, **kw)

    def _draw_relations(self):
        c = self.canvas
        c.delete("rel")
        rel = self.selected
        if not self.project or rel is None or rel not in self.pos or rel not in self.project.nodes:
            return

        node = self.project.nodes[rel]
        me = self.pos[rel]

        def rep(target):
            n = self.project.nodes.get(target)
            while n is not None:
                if n.rel in self.pos:
                    return n.rel
                n = n.parent
            return None

        if node.is_dir:
            # Aggregate external/peer dependencies for this folder
            files_in_dir = self.project.files_under(rel)
            out_targets = []
            in_sources = []
            seen_out = set()
            seen_in = set()
            for f in files_in_dir:
                for t in self.project.info.get(f, {}).get("imports", []):
                    r = rep(t)
                    if r and r != rel and r not in seen_out:
                        seen_out.add(r)
                        out_targets.append(r)
                for u in self.project.imported_by.get(f, []):
                    r = rep(u)
                    if r and r != rel and r not in seen_in:
                        seen_in.add(r)
                        in_sources.append(r)
            imports_group = [(r, False) for r in out_targets[:50]]
            imported_by_group = [(r, False) for r in in_sources[:50]]
        else:
            info = self.project.info.get(rel, {})
            out_targets = []
            seen_out = set()
            for t in info.get("imports", []):
                r = rep(t)
                if r and r != rel and r not in seen_out:
                    seen_out.add(r)
                    out_targets.append((r, r != t))
            in_sources = []
            seen_in = set()
            for u in self.project.imported_by.get(rel, []):
                r = rep(u)
                if r and r != rel and r not in seen_in:
                    seen_in.add(r)
                    in_sources.append((r, r != u))
            imports_group = out_targets[:50]
            imported_by_group = in_sources[:50]

        # Draw outgoing relations in GREEN and incoming relations in ORANGE
        for group, color, outgoing in ((imports_group, GREEN, True),
                                       (imported_by_group, ORANGE, False)):
            for r, is_dashed in group:
                if r not in self.pos:
                    continue
                other = self.pos[r]
                if outgoing:
                    self._arc(me, other, color, is_dashed)
                else:
                    self._arc(other, me, color, is_dashed)
                self._rrect(other[0], other[1], other[0] + other[2], other[1] + other[3],
                            round(8 * self.zoom), fill="", outline=color, width=3, tags=("rel",))
        c.tag_raise("rel")

    # ---- view helpers ----------------------------------------------------
    def _set_view(self, left, top):
        x0, y0, x1, y1 = self._region
        self.canvas.xview_moveto(max(0.0, (left - x0) / max(1.0, x1 - x0)))
        self.canvas.yview_moveto(max(0.0, (top - y0) / max(1.0, y1 - y0)))

    def _hit(self, cx, cy):
        for rel, (x, y, w, h) in self.pos.items():
            if x <= cx <= x + w and y <= cy <= y + h:
                return rel
        return None

    # ---- events ----------------------------------------------------------
    def _on_press(self, e):
        self.canvas.scan_mark(e.x, e.y)
        self._down, self._moved = (e.x, e.y), False

    def _on_drag(self, e):
        if abs(e.x - self._down[0]) > 3 or abs(e.y - self._down[1]) > 3:
            self._moved = True
        if self._moved:
            self.canvas.configure(cursor="fleur")
            self.canvas.scan_dragto(e.x, e.y, gain=1)

    def _on_release(self, e):
        self.canvas.configure(cursor="")
        if self._moved or self.project is None:
            return
        rel = self._hit(self.canvas.canvasx(e.x), self.canvas.canvasy(e.y))
        if rel is not None:
            self._click(rel)

    def _on_motion(self, e):
        if self.project is None or len(self.pos) > 3000:
            return
        hit = self._hit(self.canvas.canvasx(e.x), self.canvas.canvasy(e.y))
        self.canvas.configure(cursor="hand2" if hit is not None else "")

    def _on_wheel(self, e):
        delta = e.delta if e.delta else (120 if e.num == 4 else -120)
        if e.state & 0x1:  # Shift + wheel = sideways pan
            self.canvas.xview_scroll(-2 if delta > 0 else 2, "units")
        else:
            # Direct wheel = smooth zoom in/out (no Ctrl key required!)
            factor = 1.15 if delta > 0 else 1 / 1.15
            self.set_zoom(self.zoom * factor)

    def _click(self, rel):
        n = self.project.nodes[rel]
        just_toggled = False
        if rel != "" and n.is_dir and n.children and not n.skipped and not n.link:
            if rel in self.expanded:
                self.expanded.discard(rel)
            else:
                self.expanded.add(rel)
            just_toggled = True
        self.selected = rel
        self.render()
        if just_toggled or rel not in self.pos:
            self.center_on(rel, include_children=True)
        self.on_select(rel)


# ==========================================================================
# AI settings dialog
# ==========================================================================
class SettingsDialog(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.master)
        self.app = app
        self.title("⚙️ CodeMap AI Settings & Agent Configuration")
        self.transient(app.master)
        self.resizable(True, True)
        self.keys = dict(app.cfg.get("keys", {}))
        self.models = dict(app.cfg.get("models", {}))
        self.cur = app.cfg.get("provider", "gemini")

        self.model_diag_var = tk.StringVar(value=app.cfg.get("model_diagrams", ""))
        self.model_voice_var = tk.StringVar(value=app.cfg.get("model_voice", ""))
        self.key_diag_var = tk.StringVar(value=app.cfg.get("key_diagrams", ""))
        self.key_voice_var = tk.StringVar(value=app.cfg.get("key_voice", ""))

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=12, pady=10)

        self.tab_general = ttk.Frame(self.nb, padding=12)
        self.tab_routing = ttk.Frame(self.nb, padding=12)
        self.tab_instructions = ttk.Frame(self.nb, padding=12)

        self.nb.add(self.tab_general, text="🔑 API & General Provider")
        self.nb.add(self.tab_routing, text="🎯 Specialized Models")
        self.nb.add(self.tab_instructions, text="📜 System Instructions & Rules")

        self._build_general_tab()
        self._build_routing_tab()
        self._build_instructions_tab()

        # Bottom buttons
        bbar = ttk.Frame(self)
        bbar.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Button(bbar, text="Save Settings", command=self._save).pack(side="right", padx=4)
        ttk.Button(bbar, text="Cancel", command=self.destroy).pack(side="right")

        self._load(self.cur)
        self.update_idletasks()
        self.minsize(680, 520)
        m = app.master
        self.geometry(f"700x560+{m.winfo_rootx() + max(0, (m.winfo_width() - 700) // 2)}+{m.winfo_rooty() + 40}")
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def _build_general_tab(self):
        t = self.tab_general
        pad = {"padx": 6, "pady": 6}

        ttk.Label(t, text="Main AI Provider for Code Explanations & Overview:",
                  font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", **pad)

        self.combo = ttk.Combobox(t, state="readonly", width=62, values=[core.PROVIDERS[k]["label"] for k in core.PROVIDER_ORDER])
        self.combo.grid(row=1, column=0, columnspan=3, sticky="w", **pad)
        if self.cur in core.PROVIDER_ORDER:
            self.combo.current(core.PROVIDER_ORDER.index(self.cur))
        else:
            self.combo.current(3)
        self.combo.bind("<<ComboboxSelected>>", self._on_change)

        ttk.Label(t, text="API Key:").grid(row=2, column=0, sticky="e", **pad)
        self.key_var = tk.StringVar()
        self.key_entry = ttk.Entry(t, textvariable=self.key_var, width=44, show="•")
        self.key_entry.grid(row=2, column=1, sticky="w", **pad)
        self.show_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(t, text="Show", variable=self.show_var, command=self._toggle_show).grid(row=2, column=2, sticky="w")

        ttk.Label(t, text="Default Model:").grid(row=3, column=0, sticky="e", **pad)
        self.model_var = tk.StringVar()
        self.model_combo = ttk.Combobox(t, textvariable=self.model_var, width=42)
        self.model_combo.grid(row=3, column=1, sticky="w", **pad)
        self.fetch_btn = ttk.Button(t, text="Fetch Models", command=self._fetch_models)
        self.fetch_btn.grid(row=3, column=2, sticky="w")

        self.hint = ttk.Label(t, text="", wraplength=580, foreground="#475569")
        self.hint.grid(row=4, column=0, columnspan=3, sticky="w", **pad)
        self.link = tk.Label(t, text="", fg="#2563eb", cursor="hand2", font=("Segoe UI", 9, "underline"))
        self.link.grid(row=5, column=0, columnspan=3, sticky="w", padx=6, pady=(0, 4))
        self.link.bind("<Button-1>", lambda e: self._url and webbrowser.open(self._url))
        self._url = None

        row = ttk.Frame(t)
        row.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(8, 4))
        self.test_btn = ttk.Button(row, text="Test Connection", command=self._test)
        self.test_btn.pack(side="left")
        self.test_lbl = ttk.Label(row, text="", wraplength=420)
        self.test_lbl.pack(side="left", padx=10)


    def _build_routing_tab(self):
        t = self.tab_routing
        pad = {"padx": 6, "pady": 5}
        t.columnconfigure(1, weight=1)

        # ── Section title ─────────────────────────────────────────────────────
        ttk.Label(t, text="Route tasks to specialized Gemini API keys & models:",
                  font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", **pad)
        ttk.Label(t, text="Leave API Key blank to share the key from 'API & General Provider' tab.",
                  foreground="#64748b", font=("Segoe UI", 8)
                  ).grid(row=1, column=0, columnspan=3, sticky="w", padx=6, pady=(0, 8))

        # ── Diagram Studio section ─────────────────────────────────────────────
        ttk.Separator(t, orient="horizontal").grid(row=2, column=0, columnspan=3, sticky="ew", pady=4)
        ttk.Label(t, text="🏗  Diagram Studio", font=("Segoe UI", 9, "bold"),
                  foreground="#1e40af").grid(row=3, column=0, columnspan=3, sticky="w", padx=6)

        ttk.Label(t, text="Gemini API Key:").grid(row=4, column=0, sticky="e", **pad)
        self.diag_key_entry = ttk.Entry(t, textvariable=self.key_diag_var, width=38, show="•")
        self.diag_key_entry.grid(row=4, column=1, sticky="ew", **pad)
        self.show_diag_key = tk.BooleanVar(value=False)
        ttk.Checkbutton(t, text="Show", variable=self.show_diag_key,
                        command=lambda: self.diag_key_entry.configure(
                            show="" if self.show_diag_key.get() else "•")
                        ).grid(row=4, column=2, sticky="w")

        ttk.Label(t, text="Model:").grid(row=5, column=0, sticky="e", **pad)
        self.diag_combo = ttk.Combobox(t, textvariable=self.model_diag_var, width=38)
        self.diag_combo.grid(row=5, column=1, sticky="ew", **pad)
        ttk.Label(t, text="Best: gemini-2.5-flash  |  For heavy diagrams: gemini-2.5-pro",
                  foreground="#64748b", font=("Segoe UI", 8)
                  ).grid(row=6, column=1, sticky="w", padx=6, pady=(0, 4))

        # ── Voice / Chat section ───────────────────────────────────────────────
        ttk.Separator(t, orient="horizontal").grid(row=7, column=0, columnspan=3, sticky="ew", pady=4)
        ttk.Label(t, text="🎙  Voice & Chat Assistant", font=("Segoe UI", 9, "bold"),
                  foreground="#065f46").grid(row=8, column=0, columnspan=3, sticky="w", padx=6)

        ttk.Label(t, text="Gemini API Key:").grid(row=9, column=0, sticky="e", **pad)
        self.voice_key_entry = ttk.Entry(t, textvariable=self.key_voice_var, width=38, show="•")
        self.voice_key_entry.grid(row=9, column=1, sticky="ew", **pad)
        self.show_voice_key = tk.BooleanVar(value=False)
        ttk.Checkbutton(t, text="Show", variable=self.show_voice_key,
                        command=lambda: self.voice_key_entry.configure(
                            show="" if self.show_voice_key.get() else "•")
                        ).grid(row=9, column=2, sticky="w")

        ttk.Label(t, text="Model:").grid(row=10, column=0, sticky="e", **pad)
        self.voice_combo = ttk.Combobox(t, textvariable=self.model_voice_var, width=38)
        self.voice_combo.grid(row=10, column=1, sticky="ew", **pad)
        ttk.Label(t, text="Best for speed: gemini-2.5-flash-lite  |  High quality: gemini-2.5-flash",
                  foreground="#64748b", font=("Segoe UI", 8)
                  ).grid(row=11, column=1, sticky="w", padx=6, pady=(0, 4))

        ttk.Label(t,
                  text="💡 Tip: Use a key from a DIFFERENT Google project for voice to avoid quota conflicts.",
                  foreground="#9333ea", font=("Segoe UI", 8, "italic"),
                  wraplength=420
                  ).grid(row=12, column=0, columnspan=3, sticky="w", padx=6, pady=(4, 2))


    def _build_instructions_tab(self):
        t = self.tab_instructions
        lbl = ttk.Label(t, text="Set custom System Instructions, policies, and behavior rules for each agent:",
                        font=("Segoe UI", 10, "bold"))
        lbl.pack(anchor="w", padx=6, pady=(4, 6))

        # Split pane for Diagram vs Voice instructions
        pw = ttk.PanedWindow(t, orient="horizontal")
        pw.pack(fill="both", expand=True, padx=6, pady=4)

        f_diag = ttk.LabelFrame(pw, text="🏗 Diagram Studio System Rules & Instructions", padding=8)
        self.txt_diag_rules = tk.Text(f_diag, wrap="word", font=("Consolas", 9), height=14)
        ys1 = ttk.Scrollbar(f_diag, orient="vertical", command=self.txt_diag_rules.yview)
        self.txt_diag_rules.configure(yscrollcommand=ys1.set)
        self.txt_diag_rules.pack(side="left", fill="both", expand=True)
        ys1.pack(side="right", fill="y")
        self.txt_diag_rules.insert("1.0", self.app.cfg.get("system_diagrams", ""))
        pw.add(f_diag, weight=1)

        f_voice = ttk.LabelFrame(pw, text="🎙 Voice Assistant System Rules & Persona", padding=8)
        self.txt_voice_rules = tk.Text(f_voice, wrap="word", font=("Consolas", 9), height=14)
        ys2 = ttk.Scrollbar(f_voice, orient="vertical", command=self.txt_voice_rules.yview)
        self.txt_voice_rules.configure(yscrollcommand=ys2.set)
        self.txt_voice_rules.pack(side="left", fill="both", expand=True)
        ys2.pack(side="right", fill="y")
        self.txt_voice_rules.insert("1.0", self.app.cfg.get("system_voice", ""))
        pw.add(f_voice, weight=1)

    def _prov(self):
        return core.PROVIDER_ORDER[self.combo.current()]

    def _toggle_show(self):
        self.key_entry.configure(show="" if self.show_var.get() else "•")

    def _store(self):
        p = self.cur
        if core.PROVIDERS[p]["kind"] == "api":
            self.keys[p] = self.key_var.get().strip()
            raw_m = self.model_var.get().strip().replace(",", ".").replace(" ", "-")
            if raw_m.startswith("models/"):
                raw_m = raw_m[len("models/"):].strip()
            self.models[p] = raw_m

    def _load(self, p):
        spec = core.PROVIDERS[p]
        is_api = spec["kind"] == "api"
        self.key_var.set(self.keys.get(p, "") if is_api else "")
        cur_m = (self.models.get(p) or spec.get("model", "")) if is_api else ""
        if cur_m.startswith("models/"):
            cur_m = cur_m[len("models/"):].strip()
        cur_m = cur_m.replace(",", ".").replace(" ", "-")
        self.model_var.set(cur_m)
        state = "normal" if is_api else "disabled"
        self.key_entry.configure(state=state)
        self.model_combo.configure(state=state)
        self.fetch_btn.configure(state=state)
        default_choices = {
            "gemini": ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro", "gemini-flash-latest"],
            "openai": ["gpt-4o-mini", "gpt-4o", "o3-mini", "gpt-4-turbo"],
            "anthropic": ["claude-3-5-sonnet-latest", "claude-3-7-sonnet-latest", "claude-3-5-haiku-latest", "claude-3-opus-latest"],
        }
        choices = default_choices.get(p, [])
        self.model_combo["values"] = choices
        # Diagram/Voice tabs always show Gemini choices (they use Gemini-specific keys)
        gemini_choices = default_choices["gemini"]
        self.diag_combo["values"] = [""] + gemini_choices
        self.voice_combo["values"] = [""] + gemini_choices

        hint = spec["hint"]
        if spec["kind"] == "cli":
            hint += "  (found on this PC)" if core.cli_path(p) else "  (NOT found on this PC - install it first)"
        self.hint.configure(text=hint)
        self._url = spec.get("url")
        self.link.configure(text=f"Get a key: {self._url}" if self._url else "")
        self.test_lbl.configure(text="")
        self.test_btn.configure(state="disabled" if spec["kind"] == "offline" else "normal")

    def _on_change(self, _e=None):
        self._store()
        self.cur = self._prov()
        self._load(self.cur)

    def _cfg_now(self):
        self._store()
        return {"provider": self.cur, "keys": dict(self.keys), "models": dict(self.models)}

    def _fetch_models(self, done_callback=None):
        p = self.cur
        spec = core.PROVIDERS[p]
        if spec["kind"] != "api":
            return
        key = self.key_var.get().strip()
        if not key:
            self.test_lbl.configure(text="Please enter an API key first.", foreground="#b91c1c")
            if done_callback:
                done_callback([], "No API key")
            return
        self.fetch_btn.configure(state="disabled")
        self.test_lbl.configure(text="Fetching available models…", foreground="#475569")

        def done(models, err):
            if not self.winfo_exists():
                return
            self.fetch_btn.configure(state="normal")
            if err:
                self.test_lbl.configure(text=f"Could not list models: {str(err)[:200]}", foreground="#b91c1c")
                if done_callback:
                    done_callback([], err)
                return
            if models:
                self.model_combo["values"] = models
                self.diag_combo["values"] = [""] + models
                self.voice_combo["values"] = [""] + models
                cur_m = self.model_var.get().strip().replace(",", ".").replace(" ", "-")
                if cur_m.startswith("models/"):
                    cur_m = cur_m[len("models/"):].strip()
                if not cur_m or cur_m not in models:
                    self.model_var.set(models[0])
                else:
                    self.model_var.set(cur_m)
                self.test_lbl.configure(text=f"Found {len(models)} available model(s).", foreground=GREEN)
            else:
                self.test_lbl.configure(text="No models returned for this key.", foreground="#475569")
            if done_callback:
                done_callback(models, None)

        self.app.run_bg(lambda: core.fetch_available_models(p, key), done)

    def _test(self):
        self._store()
        cfg = self._cfg_now()
        ok, msg = core.provider_ready(cfg)
        if not ok:
            self.test_lbl.configure(text=msg, foreground="#b91c1c")
            return

        p = cfg.get("provider")
        spec = core.PROVIDERS[p]

        if spec["kind"] == "api":
            self.test_lbl.configure(text="Fetching models & testing connection…", foreground="#475569")
            self.test_btn.configure(state="disabled")
            self.fetch_btn.configure(state="disabled")

            def on_models_fetched(models, err):
                if not self.winfo_exists():
                    return
                if models:
                    cur_m = self.model_var.get().strip()
                    if not cur_m or cur_m not in models:
                        self.model_var.set(models[0])
                    self._store()
                    cfg["models"] = dict(self.models)
                elif err and not cfg.get("models", {}).get(p):
                    self.test_btn.configure(state="normal")
                    self.fetch_btn.configure(state="normal")
                    self.test_lbl.configure(text=str(err)[:300], foreground="#b91c1c")
                    return

                def done_test(res, gen_err):
                    if not self.winfo_exists():
                        return
                    self.test_btn.configure(state="normal")
                    self.fetch_btn.configure(state="normal")
                    if gen_err:
                        self.test_lbl.configure(text=str(gen_err)[:300], foreground="#b91c1c")
                    else:
                        m_info = f" ({len(models)} models found)" if models else ""
                        self.test_lbl.configure(text=f"Works!{m_info} AI answered: {res[:50]}", foreground=GREEN)

                self.app.run_bg(lambda: core.ai_generate(cfg, "Reply with the single word OK.", timeout=60, max_tokens=30), done_test)

            self._fetch_models(done_callback=on_models_fetched)
        else:
            self.test_lbl.configure(text="Testing… (can take up to 30 seconds)", foreground="#475569")
            self.test_btn.configure(state="disabled")

            def done(res, err):
                if not self.winfo_exists():
                    return
                self.test_btn.configure(state="normal")
                if err:
                    self.test_lbl.configure(text=str(err)[:300], foreground="#b91c1c")
                else:
                    self.test_lbl.configure(text="Works! The AI answered: " + res[:60], foreground=GREEN)

            self.app.run_bg(lambda: core.ai_generate(cfg, "Reply with the single word OK.", timeout=60, max_tokens=30), done)

    def _save(self):
        cfg = self._cfg_now()
        self.app.cfg["provider"] = cfg["provider"]
        self.app.cfg["keys"] = cfg["keys"]
        self.app.cfg["models"] = cfg["models"]
        self.app.cfg["key_diagrams"] = self.key_diag_var.get().strip()
        self.app.cfg["key_voice"] = self.key_voice_var.get().strip()
        self.app.cfg["model_diagrams"] = self.model_diag_var.get().strip()
        self.app.cfg["model_voice"] = self.model_voice_var.get().strip()
        self.app.cfg["system_diagrams"] = self.txt_diag_rules.get("1.0", "end").strip()
        self.app.cfg["system_voice"] = self.txt_voice_rules.get("1.0", "end").strip()
        core.save_config(self.app.cfg)
        self.app.status_var.set("AI settings & system rules saved successfully.")
        self.destroy()
        self.app.show(self.app.selected)



# ==========================================================================
# Diagram Library / Vault Left Panel
# ==========================================================================
class DiagramLibraryPanel(ttk.Frame):
    """
    Collapsible left panel to browse, search, and visualize all files/folders ('libraries'),
    with a dedicated button to only show items that have created diagrams in the vault.
    """
    def __init__(self, master, app):
        super().__init__(master, width=280)
        self.app = app
        self.project = None
        self.vault = None
        self.only_diagrams_var = tk.BooleanVar(value=True)  # Default: only show items with diagrams
        self.search_var = tk.StringVar()
        self.selected_item = None

        self._build_ui()

    def _build_ui(self):
        # Header
        hdr = ttk.Frame(self)
        hdr.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(hdr, text="📚 Diagram Library", font=("Segoe UI", 10, "bold"), foreground="#1e293b").pack(side="left")
        ttk.Button(hdr, text="✕", width=3, command=lambda: self.app.toggle_library() if self.app else None).pack(side="right")

        # Filter bar
        flt = ttk.Frame(self)
        flt.pack(fill="x", padx=8, pady=4)

        search_box = ttk.Frame(flt)
        search_box.pack(fill="x", pady=(0, 4))
        ttk.Label(search_box, text="🔍", font=("Segoe UI", 9)).pack(side="left", padx=(0, 2))
        self.search_entry = ttk.Entry(search_box, textvariable=self.search_var)
        self.search_entry.pack(side="left", fill="x", expand=True)
        self.search_entry.bind("<KeyRelease>", lambda e: self.refresh_items())

        # Toggle Button: Only With Diagrams vs Show All
        self.filter_btn = ttk.Button(flt, text="⭐ Only With Diagrams", command=self.toggle_filter_mode)
        self.filter_btn.pack(fill="x", pady=2)

        # Content List / Tree
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=8, pady=4)

        self.tree = ttk.Treeview(tree_frame, columns=("badge",), selectmode="browse", show="tree headings")
        self.tree.heading("#0", text="Component / File", anchor="w")
        self.tree.heading("badge", text="Diagrams", anchor="center")
        self.tree.column("#0", width=180, stretch=True)
        self.tree.column("badge", width=85, stretch=False, anchor="center")

        ys = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        xs = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Button-3>", self._on_tree_context)
        self.tree.bind("<Button-2>", self._on_tree_context)

        # Bottom Bar
        bot = ttk.Frame(self)
        bot.pack(fill="x", padx=8, pady=(4, 8))
        self.status_lbl = ttk.Label(bot, text="No project loaded", font=("Segoe UI", 8), foreground="#64748b")
        self.status_lbl.pack(fill="x", pady=(0, 4))

        btn_box = ttk.Frame(bot)
        btn_box.pack(fill="x")
        ttk.Button(btn_box, text="✨ Studio", command=self.open_selected_in_studio).pack(side="left", fill="x", expand=True, padx=(0, 1))
        ttk.Button(btn_box, text="🗺 Map", command=self.reveal_selected_in_map).pack(side="left", fill="x", expand=True, padx=1)
        ttk.Button(btn_box, text="💬 Chat", command=self.open_chat).pack(side="left", fill="x", expand=True, padx=1)
        ttk.Button(btn_box, text="📂 Folder", command=self.show_in_system_folder).pack(side="left", fill="x", expand=True, padx=(1, 0))

    def set_project(self, project, vault):
        self.project = project
        self.vault = vault
        self.refresh_items()

    def toggle_filter_mode(self):
        new_val = not self.only_diagrams_var.get()
        self.only_diagrams_var.set(new_val)
        if new_val:
            self.filter_btn.configure(text="⭐ Only With Diagrams")
        else:
            self.filter_btn.configure(text="📁 Show All Files & Folders")
        self.refresh_items()

    def refresh_items(self):
        self.tree.delete(*self.tree.get_children())
        if not self.project:
            self.status_lbl.configure(text="Scan a folder to view library")
            return

        vault_items = self.vault.get_all_items_with_diagrams() if self.vault else {}
        diagram_counts = {}
        for k, cnt in vault_items.items():
            if k.startswith("@dir:"):
                diagram_counts[(k[5:], False)] = cnt
            else:
                diagram_counts[(k, True)] = cnt

        query = self.search_var.get().strip().lower()
        only_with = self.only_diagrams_var.get()

        displayed_count = 0
        total_diagram_count = sum(vault_items.values())

        if only_with:
            # ONLY show items that have diagrams created in the vault
            sorted_items = sorted(diagram_counts.keys(), key=lambda x: (x[1], x[0].lower()))
            for rel, is_file in sorted_items:
                if query and query not in rel.lower():
                    continue
                cnt = diagram_counts[(rel, is_file)]
                name = posixpath.basename(rel) if rel else f"(Root: {self.project.name})"
                icon = "📄 " if is_file else "📁 "
                item_id = f"f:{rel}" if is_file else f"d:{rel}"
                badge = f"✨ {cnt} saved"
                self.tree.insert("", "end", iid=item_id, text=f"{icon}{name}", values=(badge,))
                displayed_count += 1
            self.status_lbl.configure(text=f"{displayed_count} item(s) with diagrams ({total_diagram_count} saved)")
        else:
            # Show all files and folders in project; badge those with diagrams
            for rel, node in sorted(self.project.nodes.items(), key=lambda x: (not x[1].is_dir, x[0].lower())):
                if query and query not in rel.lower():
                    continue
                is_file = not node.is_dir
                cnt = diagram_counts.get((rel, is_file), 0)
                name = node.name if rel else f"(Root: {self.project.name})"
                icon = "📄 " if is_file else "📁 "
                item_id = f"f:{rel}" if is_file else f"d:{rel}"
                badge = f"✨ {cnt}" if cnt > 0 else ""
                self.tree.insert("", "end", iid=item_id, text=f"{icon}{name}", values=(badge,))
                displayed_count += 1
            self.status_lbl.configure(text=f"{displayed_count} total items ({len(diagram_counts)} with diagrams)")

    def _get_selected_rel_and_type(self):
        sel = self.tree.selection()
        if not sel:
            return None, False
        iid = sel[0]
        is_file = iid.startswith("f:")
        rel = iid[2:]
        return rel, is_file

    def _on_select(self, _e=None):
        rel, is_file = self._get_selected_rel_and_type()
        if rel is None:
            return
        self.selected_item = (rel, is_file)
        self.app.selected = rel
        if hasattr(self.app, "diagram_studio") and self.app.diagram_studio:
            self.app.diagram_studio.set_target(rel)
        self.app.show(rel)

    def _on_double_click(self, _e=None):
        self.open_selected_in_studio()

    def open_selected_in_studio(self):
        rel, is_file = self._get_selected_rel_and_type()
        if rel is not None:
            self.app.open_diagram_studio(rel)

    def reveal_selected_in_map(self):
        rel, is_file = self._get_selected_rel_and_type()
        if rel is not None:
            self.app.mindmap.reveal(rel)
            self.app.nb.select(self.app.mindmap)

    def open_chat(self):
        rel, is_file = self._get_selected_rel_and_type()
        if rel is not None:
            self.app.open_chat_for(rel, is_file)

    def show_in_system_folder(self):
        rel, is_file = self._get_selected_rel_and_type()
        if rel is None:
            if self.project:
                rel, is_file = "", False
            else:
                return
        if self.vault:
            self.vault.open_in_system_folder(rel, is_file)

    def _open_source_in_explorer(self, node):
        try:
            import subprocess
            subprocess.run(f'explorer /select,"{os.path.abspath(node.path)}"', shell=True)
        except Exception:
            try:
                os.startfile(node.path if node.is_dir else os.path.dirname(node.path))
            except Exception:
                pass

    def _on_tree_context(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self._on_select()
            rel, is_file = self._get_selected_rel_and_type()
            if rel is not None:
                node = self.project.nodes.get(rel) if self.project else None
                name = (node.name if node else rel) or (self.project.name if self.project else "Component")
                m = tk.Menu(self.master, tearoff=0)
                m.add_command(label=f"📂 Show Diagram in System Folder",
                              command=self.show_in_system_folder)
                if node:
                    m.add_command(label=f"📁 Open Source in Explorer",
                                  command=lambda: self._open_source_in_explorer(node))
                m.add_separator()
                m.add_command(label=f"✨ Open in Visual Studio",
                              command=self.open_selected_in_studio)
                m.add_command(label=f"💬 Chat with AI about '{name}'...",
                              command=self.open_chat)
                m.add_command(label=f"🗺 Reveal in Mind Map",
                              command=self.reveal_selected_in_map)
                m.tk_popup(event.x_root, event.y_root)


# ==========================================================================
# Visuals & Diagrams Studio Panel
# ==========================================================================
class DiagramStudioPanel(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.project = None
        self.vault = None
        self.current_rel = ""
        self.current_is_file = True
        self.current_entry = None
        self.is_fullscreen = False
        self._history_entries = []

        self._build_ui()

    def _build_ui(self):
        # Row 1: Target, Diagram Type Selector, Generate Menu, History Version Picker
        r1 = ttk.Frame(self)
        r1.pack(fill="x", padx=8, pady=(6, 2))

        self.target_lbl = ttk.Label(r1, text="Target: (Select file/folder)", font=("Segoe UI", 9, "bold"), foreground="#1e293b")
        self.target_lbl.pack(side="left", padx=(2, 8))

        ttk.Label(r1, text="Type:").pack(side="left")
        self.type_var = tk.StringVar(value=diagrams.DIAGRAM_TYPES["system"]["label"])
        self.type_combo = ttk.Combobox(r1, textvariable=self.type_var, state="readonly", width=28,
                                       values=[diagrams.DIAGRAM_TYPES[k]["label"] for k in diagrams.DIAGRAM_ORDER])
        self.type_combo.pack(side="left", padx=4)

        self.gen_btn = ttk.Menubutton(r1, text="✨ Generate Diagram ▾")
        self.gen_menu = tk.Menu(self.gen_btn, tearoff=0)
        self.gen_menu.add_command(label="✨ Generate Selected Diagram", command=self.generate)
        self.gen_menu.add_separator()
        self.gen_menu.add_command(label="⭐ Generate All Recommended Diagrams", command=lambda: self.generate_batch(recommended_only=True))
        self.gen_menu.add_command(label="🚀 Generate All Diagrams (Batch)", command=lambda: self.generate_batch(recommended_only=False))
        self.gen_btn.configure(menu=self.gen_menu)
        self.gen_btn.pack(side="left", padx=4)

        ttk.Label(r1, text="History:").pack(side="left", padx=(8, 2))
        self.history_var = tk.StringVar(value="No diagrams saved")
        self.history_combo = ttk.Combobox(r1, textvariable=self.history_var, state="readonly", width=24, values=["No diagrams saved"])
        self.history_combo.pack(side="left", padx=2, fill="x", expand=True)
        self.history_combo.bind("<<ComboboxSelected>>", self._on_history_select)

        # Row 2: Library, Browser, Export, Fullscreen, and Canvas Controls (never overflow/clip!)
        r2 = ttk.Frame(self)
        r2.pack(fill="x", padx=8, pady=(2, 4))

        self.lib_toggle_btn = ttk.Button(r2, text="📚 Library", command=self.app.toggle_library)
        self.lib_toggle_btn.pack(side="left", padx=(0, 4))

        self.browser_btn = ttk.Button(r2, text="🌐 Browser View", command=self.open_in_browser)
        self.browser_btn.pack(side="left", padx=4)

        self.export_btn = ttk.Menubutton(r2, text="💾 Export ▾")
        self.export_menu = tk.Menu(self.export_btn, tearoff=0)
        self.export_menu.add_command(label="Export Current Diagram (HTML)", command=lambda: self.export_current("html"))
        self.export_menu.add_command(label="Export Current Diagram (Mermaid .mmd)", command=lambda: self.export_current("mmd"))
        self.export_menu.add_command(label="Export Current Diagram (Markdown .md)", command=lambda: self.export_current("md"))
        self.export_menu.add_separator()
        self.export_menu.add_command(label="Export Entire Visuals Vault (Web Suite)", command=self.export_vault)
        self.export_btn.configure(menu=self.export_menu)
        self.export_btn.pack(side="left", padx=4)

        self.split_btn = ttk.Button(r2, text="⛶ Full / Split View", command=self.toggle_fullscreen)
        self.split_btn.pack(side="left", padx=4)

        # Right-aligned Canvas Tools inside Row 2
        ttk.Button(r2, text="100%", width=4, command=lambda: self.canvas_view.set_zoom(1.0)).pack(side="right", padx=1)
        ttk.Button(r2, text=" - ", width=3, command=lambda: self.canvas_view.set_zoom(self.canvas_view.zoom / 1.2)).pack(side="right", padx=1)
        ttk.Button(r2, text=" + ", width=3, command=lambda: self.canvas_view.set_zoom(self.canvas_view.zoom * 1.2)).pack(side="right", padx=1)
        ttk.Button(r2, text="⛶ Fit", width=4, command=lambda: self.canvas_view.fit_view()).pack(side="right", padx=1)
        ttk.Button(r2, text="🔄 Flip TD/LR", command=lambda: self.canvas_view.toggle_direction()).pack(side="right", padx=2)

        self.tip_lbl = ttk.Label(self, text="💡 Tip: Click any node card to trace its data flow. Drag to pan, scroll to zoom. Use '🔄 Flip TD/LR' to change orientation.",
                                 foreground="#64748b", font=("Segoe UI", 8))
        self.tip_lbl.pack(fill="x", padx=10, pady=(0, 4))

        self.vpane = ttk.PanedWindow(self, orient="vertical")
        self.vpane.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        cframe = ttk.Frame(self.vpane)
        self.canvas_view = diagrams.DiagramCanvas(cframe, app=self.app)
        self.canvas_view.pack(fill="both", expand=True)
        self.vpane.add(cframe, weight=3)

        eframe = ttk.Frame(self.vpane)
        ehdr = ttk.Frame(eframe)
        ehdr.pack(fill="x", pady=(2, 2))
        ttk.Label(ehdr, text="📘 Plain-English Explanation (For Non-Programmers):", font=("Segoe UI", 9, "bold"), foreground="#1e293b").pack(side="left")
        self.raw_btn = ttk.Button(ehdr, text="View Mermaid Code", command=self._toggle_raw)
        self.raw_btn.pack(side="right", padx=4)

        self.expl_text = tk.Text(eframe, wrap="word", font=("Segoe UI", 10), bd=0, padx=10, pady=6, height=6)
        es = ttk.Scrollbar(eframe, orient="vertical", command=self.expl_text.yview)
        self.expl_text.configure(yscrollcommand=es.set)
        self.expl_text.pack(side="left", fill="both", expand=True)
        es.pack(side="right", fill="y")
        self.vpane.add(eframe, weight=2)

    def set_project(self, project, vault):
        self.project = project
        self.vault = vault
        if hasattr(self, "canvas_view") and self.canvas_view:
            self.canvas_view.set_project(project)
        if project:
            self.set_target(self.current_rel or "")

    def set_target(self, rel):
        self.current_rel = rel
        p = self.project
        if not p or rel not in p.nodes:
            self.target_lbl.configure(text="Target: (Select file/folder)")
            self.current_is_file = True
            return

        node = p.nodes[rel]
        self.current_is_file = not node.is_dir
        icon = "📄 File" if self.current_is_file else "📁 Folder"
        name = node.name if rel else p.name
        self.target_lbl.configure(text=f"{icon}: {name}")

        # Smart Recommendation Engine (Clean & Concise labels)
        recs = diagrams.recommend_diagram_types(self.project, rel, self.current_is_file)
        top_rec_key = recs[0] if recs else None
        combo_vals = []
        if top_rec_key and top_rec_key in diagrams.DIAGRAM_TYPES:
            combo_vals.append(f"⭐ {diagrams.DIAGRAM_TYPES[top_rec_key]['label']} (Recommended)")
        for k in recs[1:2]:
            if k in diagrams.DIAGRAM_TYPES and k != top_rec_key:
                combo_vals.append(f"★ {diagrams.DIAGRAM_TYPES[k]['label']}")
        for k in diagrams.DIAGRAM_ORDER:
            if k not in recs[:2] and k in diagrams.DIAGRAM_TYPES:
                combo_vals.append(diagrams.DIAGRAM_TYPES[k]["label"])
        self.type_combo["values"] = combo_vals
        if combo_vals:
            self.type_var.set(combo_vals[0])

        top_rec = diagrams.DIAGRAM_TYPES.get(top_rec_key, {}) if top_rec_key else {}
        self.tip_lbl.configure(
            text=f"💡 Best fit for this {icon.lower()}: ⭐ {top_rec.get('label', 'System Diagram')} — {top_rec.get('desc', '')}",
            foreground="#1d4ed8"
        )
        self._refresh_history()

    def _refresh_history(self):
        if not self.vault:
            self.history_combo["values"] = ["No diagrams saved"]
            self.history_var.set("No diagrams saved")
            return

        self._history_entries = self.vault.get_diagrams(self.current_rel, self.current_is_file)
        if self._history_entries:
            vals = [f"v{len(self._history_entries) - i}: {e['title']} ({e['timestamp']})" for i, e in enumerate(self._history_entries)]
            self.history_combo["values"] = vals
            self.history_var.set(vals[0])
            self.display_entry(self._history_entries[0])
        else:
            self.history_combo["values"] = ["No diagrams saved yet"]
            self.history_var.set("No diagrams saved yet")
            self.canvas_view.display_diagram(None)
            self.expl_text.delete("1.0", "end")
            self.expl_text.insert("end", "No diagrams generated for this file/folder yet.\nSelect a diagram type above and click 'Generate Diagram', or right-click any item in the Mind Map.")

    def _on_history_select(self, _e=None):
        idx = self.history_combo.current()
        if 0 <= idx < len(self._history_entries):
            self.display_entry(self._history_entries[idx])

    def display_entry(self, entry):
        self.current_entry = entry
        if not entry:
            return
        self.canvas_view.display_diagram(entry)
        self.expl_text.delete("1.0", "end")
        self.expl_text.insert("end", entry.get("explanation", ""))

    def generate(self, diag_type=None):
        if not self.project:
            messagebox.showinfo("Scan Needed", "Please scan a project folder first.")
            return
        ok, msg = core.provider_ready(self.app.cfg)
        if not ok:
            self.app._need_ai(msg)
            return

        if not diag_type:
            raw_sel = self.type_var.get()
            clean_sel = re.sub(r"^[⭐★\s]+", "", raw_sel).replace("(Recommended)", "").replace("[Recommended]", "").strip()
            diag_type = next((k for k, v in diagrams.DIAGRAM_TYPES.items() if v["label"] == clean_sel or v["label"] in raw_sel or clean_sel in v["label"]), "system")

        rel = self.current_rel
        is_file = self.current_is_file
        target_name = (self.project.nodes[rel].name if rel else self.project.name) if rel in self.project.nodes else rel
        diag_spec = diagrams.DIAGRAM_TYPES.get(diag_type, diagrams.DIAGRAM_TYPES["system"])

        self.tip_lbl.configure(text=f"⏳ Generating {diag_spec['label']} for {target_name} using AI… (10-30 seconds)", foreground="#2563eb")
        self.gen_btn.configure(state="disabled")

        prompt = diagrams.build_diagram_prompt(self.project, rel, diag_type)
        cfg = dict(self.app.cfg)
        diag_model = cfg.get("model_diagrams", "").strip() or None
        diag_sys = cfg.get("system_diagrams", "").strip() or None
        # Use dedicated diagram API key if configured (Gemini only)
        diag_key = cfg.get("key_diagrams", "").strip()
        if diag_key and cfg.get("provider") == "gemini":
            cfg["keys"] = dict(cfg.get("keys", {}))
            cfg["keys"]["gemini"] = diag_key

        def work():
            return core.ai_generate(cfg, prompt, timeout=120, max_tokens=2200,
                                    system_instruction=diag_sys, model_override=diag_model)

        def done(res, err):
            self.gen_btn.configure(state="normal")
            if err:
                self.tip_lbl.configure(text=f"Generation problem: {str(err)[:120]}", foreground="#b91c1c")
                messagebox.showerror("Diagram Generation Failed", str(err))
                return

            mermaid_code, explanation = diagrams.extract_mermaid_and_text(res)
            model_used = diag_model or (cfg.get("models", {}).get(cfg.get("provider")) or core.PROVIDERS.get(cfg.get("provider"), {}).get("model", "AI"))
            entry = self.vault.add_diagram(rel, is_file, diag_type, diag_spec["label"], mermaid_code, explanation, model_used)

            self.tip_lbl.configure(text=f"✅ Done! Saved {diag_spec['label']} to vault. Total versions: {self.vault.get_count(rel, is_file)}", foreground=GREEN)
            self._refresh_history()
            if hasattr(self.app, "library_panel") and self.app.library_panel:
                self.app.library_panel.refresh_items()

        self.app.run_bg(work, done)

    def generate_batch(self, recommended_only=False):
        if not self.project:
            messagebox.showinfo("Scan Needed", "Please scan a project folder first.")
            return
        ok, msg = core.provider_ready(self.app.cfg)
        if not ok:
            self.app._need_ai(msg)
            return

        rel = self.current_rel
        is_file = self.current_is_file
        target_name = (self.project.nodes[rel].name if rel else self.project.name) if rel in self.project.nodes else rel

        if recommended_only:
            recs = diagrams.recommend_diagram_types(self.project, rel, is_file)
            types_to_gen = recs[:2]
        else:
            types_to_gen = list(diagrams.DIAGRAM_ORDER)

        if not types_to_gen:
            return

        total = len(types_to_gen)
        self.gen_btn.configure(state="disabled")
        cfg = dict(self.app.cfg)
        diag_model = cfg.get("model_diagrams", "").strip() or None
        diag_sys = cfg.get("system_diagrams", "").strip() or None
        # Use dedicated diagram API key if configured (Gemini only)
        diag_key = cfg.get("key_diagrams", "").strip()
        if diag_key and cfg.get("provider") == "gemini":
            cfg["keys"] = dict(cfg.get("keys", {}))
            cfg["keys"]["gemini"] = diag_key

        def work():
            results = []
            for idx, dtype in enumerate(types_to_gen):
                diag_spec = diagrams.DIAGRAM_TYPES.get(dtype, diagrams.DIAGRAM_TYPES["system"])
                self.app.master.after(0, lambda i=idx, l=diag_spec['label']: self.tip_lbl.configure(
                    text=f"⏳ Batch generating ({i+1}/{total}): {l} for {target_name}…",
                    foreground="#2563eb"
                ))
                prompt = diagrams.build_diagram_prompt(self.project, rel, dtype)
                try:
                    res = core.ai_generate(cfg, prompt, timeout=120, max_tokens=2200,
                                           system_instruction=diag_sys, model_override=diag_model)
                    mermaid_code, explanation = diagrams.extract_mermaid_and_text(res)
                    model_used = diag_model or (cfg.get("models", {}).get(cfg.get("provider")) or core.PROVIDERS.get(cfg.get("provider"), {}).get("model", "AI"))
                    entry = self.vault.add_diagram(rel, is_file, dtype, diag_spec["label"], mermaid_code, explanation, model_used)
                    results.append(entry)
                except Exception as ex:
                    print(f"[BatchGen] Error generating {dtype}: {ex}")
            return results

        def done(res, err):
            self.gen_btn.configure(state="normal")
            if err:
                self.tip_lbl.configure(text=f"Batch generation had error: {str(err)[:120]}", foreground="#b91c1c")
            else:
                count = len(res) if res else 0
                self.tip_lbl.configure(text=f"✅ Batch complete! Generated {count} diagrams for {target_name}.", foreground=GREEN)
                self._refresh_history()
                if hasattr(self.app, "library_panel") and self.app.library_panel:
                    self.app.library_panel.refresh_items()

        self.app.run_bg(work, done)

    def open_in_browser(self):
        if not self.current_entry:
            messagebox.showinfo("No Diagram", "Please generate or select a diagram first.")
            return
        diagrams.open_interactive_browser_diagram(self.current_entry)

    def export_current(self, fmt="html"):
        if not self.current_entry:
            messagebox.showinfo("No Diagram", "Please generate or select a diagram first.")
            return
        saved = diagrams.export_single_diagram(self.current_entry, fmt)
        if saved:
            self.tip_lbl.configure(text=f"💾 Saved: {os.path.basename(saved)}", foreground=GREEN)

    def export_vault(self):
        if not self.vault:
            return
        saved = diagrams.export_entire_vault_html(self.project.name, self.vault)
        if saved:
            self.tip_lbl.configure(text=f"📚 Vault exported: {os.path.basename(saved)}", foreground=GREEN)
            if messagebox.askyesno("Vault Exported", f"Successfully exported complete Visuals Vault to:\n{saved}\n\nOpen in browser now?"):
                webbrowser.open(f"file:///{urllib.parse.quote(saved.replace(chr(92), '/'))}")

    def toggle_fullscreen(self):
        self.is_fullscreen = not getattr(self, "is_fullscreen", False)
        if self.is_fullscreen:
            self.split_btn.configure(text="⛶ Split View")
            try:
                self.app.paned.sashpos(0, self.app.master.winfo_width())
            except Exception:
                pass
        else:
            self.split_btn.configure(text="⛶ Full View")
            self.app._set_sash()

    def _toggle_raw(self):
        if not self.current_entry or not self.current_entry.get("mermaid"):
            return
        w = tk.Toplevel(self)
        w.title("Raw Mermaid Code")
        w.geometry("640x480")
        t = tk.Text(w, wrap="none", font=("Consolas", 10), padx=8, pady=8)
        t.pack(fill="both", expand=True)
        t.insert("1.0", self.current_entry["mermaid"])
        t.configure(state="disabled")
        btn = ttk.Button(w, text="Copy to Clipboard", command=lambda: (self.clipboard_clear(), self.clipboard_append(self.current_entry["mermaid"]), w.destroy()))
        btn.pack(pady=8)


# ==========================================================================
# Main application
# ==========================================================================
class App:
    def __init__(self, master):
        self.master = master
        master.title("CodeMap - see how your code fits together")
        master.geometry("1320x800")
        master.minsize(940, 580)

        self.cfg = core.load_config()
        self.project = None
        self.cache = None
        self.vault = None
        self.selected = ""
        self.bgq = queue.Queue()
        self.live_fn = None
        self.working = False
        self.stop_event = threading.Event()
        self._pb_mode = None
        self._lnk = 0

        # UI Zoom State for eyesight accessibility
        self.ui_scale = 1.0
        self.base_font_sizes = {
            "TkDefaultFont": 10,
            "TkTextFont": 10,
            "TkFixedFont": 10,
            "TkMenuFont": 10,
            "TkHeadingFont": 11,
        }
        for name in list(self.base_font_sizes.keys()):
            try:
                sz = abs(tkfont.nametofont(name).cget("size"))
                if sz > 0:
                    self.base_font_sizes[name] = sz
            except Exception:
                pass

        self.path_var = tk.StringVar(value=self.cfg.get("last_path", ""))
        self.files_var = tk.BooleanVar(value=self.cfg.get("include_files", True))
        self.hidden_var = tk.BooleanVar(value=self.cfg.get("show_hidden", False))
        self.junk_var = tk.BooleanVar(value=self.cfg.get("skip_junk", True))
        self.status_var = tk.StringVar(value="Paste a folder path above, then press Scan.")

        fams = set(tkfont.families())
        self.ui_font = "Segoe UI" if "Segoe UI" in fams else tkfont.nametofont("TkDefaultFont").actual("family")
        self.mono = next((f for f in ("Consolas", "Cascadia Mono", "DejaVu Sans Mono", "Courier New") if f in fams), "TkFixedFont")

        self._build_ui()
        self._prefill()
        master.protocol("WM_DELETE_WINDOW", self._close)
        self.master.after(100, self._pump)
        self.master.after(200, self._set_sash)
        self.show(None)

        # Global Zoom keyboard shortcuts
        master.bind("<Control-plus>", lambda e: self.zoom_ui(0.15))
        master.bind("<Control-equal>", lambda e: self.zoom_ui(0.15))
        master.bind("<Control-minus>", lambda e: self.zoom_ui(-0.15))
        master.bind("<Control-0>", lambda e: self.reset_ui_zoom())

    # ---- layout --------------------------------------------------------
    def _build_ui(self):
        m = self.master
        top = ttk.Frame(m)
        top.pack(fill="x", padx=10, pady=(10, 2))
        ttk.Label(top, text="Folder path:").pack(side="left")
        self.entry = ttk.Entry(top, textvariable=self.path_var, font=(self.ui_font, 10))
        self.entry.pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(top, text="Paste", width=7, command=self.paste).pack(side="left", padx=2)
        ttk.Button(top, text="Browse…", width=9, command=self.browse).pack(side="left", padx=2)
        self.scan_btn = ttk.Button(top, text="Scan", width=10, command=self.scan)
        self.scan_btn.pack(side="left", padx=(8, 0))
        self.entry.bind("<Return>", lambda e: self.scan())

        opts = ttk.Frame(m)
        opts.pack(fill="x", padx=10, pady=2)
        ttk.Checkbutton(opts, text="Show files in Tree tab", variable=self.files_var, command=self._refresh_tree_text).pack(side="left")
        ttk.Checkbutton(opts, text="Show hidden", variable=self.hidden_var).pack(side="left", padx=12)
        ttk.Checkbutton(opts, text="Skip junk folders (node_modules, .git, venv…)", variable=self.junk_var).pack(side="left")
        self.library_btn = ttk.Button(opts, text="📚 Diagram Library", command=self.toggle_library)
        self.library_btn.pack(side="left", padx=12)
        self.details_btn = ttk.Button(opts, text="▶ Close Details", command=self.toggle_right_panel)
        self.details_btn.pack(side="left", padx=2)
        ttk.Button(opts, text="🌐 React Visualizer (JSON Crack)", command=self.open_react_visualizer).pack(side="left", padx=4)

        # Global UI Zoom controls (for eyesight accessibility)
        zoom_frame = ttk.Frame(opts)
        zoom_frame.pack(side="right", padx=(8, 2))
        ttk.Label(zoom_frame, text="Zoom:", foreground="#64748b").pack(side="left", padx=2)
        ttk.Button(zoom_frame, text="A-", width=3, command=lambda: self.zoom_ui(-0.15)).pack(side="left", padx=1)
        self.zoom_lbl = ttk.Label(zoom_frame, text="100%", width=5, anchor="center")
        self.zoom_lbl.pack(side="left")
        ttk.Button(zoom_frame, text="A+", width=3, command=lambda: self.zoom_ui(0.15)).pack(side="left", padx=1)
        ttk.Button(zoom_frame, text="Reset", command=self.reset_ui_zoom).pack(side="left", padx=2)

        ttk.Button(opts, text="AI settings…", command=self.open_settings).pack(side="right", padx=2)
        self.stop_btn = ttk.Button(opts, text="Stop", width=7, command=self.stop, state="disabled")
        self.stop_btn.pack(side="right", padx=2)

        self.paned = ttk.PanedWindow(m, orient="horizontal")
        self.paned.pack(fill="both", expand=True, padx=10, pady=6)

        self.library_open = False
        self.library_panel = DiagramLibraryPanel(self.paned, self)

        self.nb = ttk.Notebook(self.paned)
        tf = ttk.Frame(self.nb)
        self.tree_text = tk.Text(tf, wrap="none", font=(self.mono, 10), bd=0, padx=6, pady=4)
        ys = ttk.Scrollbar(tf, orient="vertical", command=self.tree_text.yview)
        xs = ttk.Scrollbar(tf, orient="horizontal", command=self.tree_text.xview)
        self.tree_text.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.tree_text.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        tf.rowconfigure(0, weight=1)
        tf.columnconfigure(0, weight=1)
        self.tree_text.bind("<Button-3>", self._on_tree_right_click)
        self.tree_text.bind("<Button-2>", self._on_tree_right_click)

        self.mindmap = MindMap(self.nb, self._on_map_select, on_context_menu=self._show_context_menu)
        self.nb.add(self.mindmap, text="   Mind Map   ")
        self.nb.add(tf, text="   Tree   ")

        # Tab 3: Visuals & Diagrams Studio
        self.diagram_studio = DiagramStudioPanel(self.nb, self)
        self.nb.add(self.diagram_studio, text="   ✨ Visuals & Diagrams   ")

        self.nb.bind("<<NotebookTabChanged>>", lambda e: self.mindmap.center_on(self.mindmap.selected or ""))
        self.paned.add(self.nb, weight=3)

        right = ttk.Frame(self.paned)
        self.right_panel = right
        self.right_open = True

        hdr = ttk.Frame(right)
        hdr.pack(fill="x", pady=(0, 4))
        self.explain_btn = ttk.Button(hdr, text="Explain with AI", command=lambda: self.explain_selected(False))
        self.explain_btn.pack(side="left")
        self.diagram_btn = ttk.Button(hdr, text="✨ Visual Studio", command=self.open_diagram_studio)
        self.diagram_btn.pack(side="left", padx=6)
        self.open_btn = ttk.Button(hdr, text="Open file", command=self.open_selected)
        self.open_btn.pack(side="left", padx=6)
        ttk.Button(hdr, text="✕", width=3, command=self.toggle_right_panel).pack(side="right", padx=(4, 0))
        dbody = ttk.Frame(right)
        dbody.pack(fill="both", expand=True)
        self.dt = tk.Text(dbody, wrap="word", font=(self.ui_font, 10), bd=0, padx=12, pady=8, cursor="arrow")
        dys = ttk.Scrollbar(dbody, orient="vertical", command=self.dt.yview)
        self.dt.configure(yscrollcommand=dys.set)
        self.dt.pack(side="left", fill="both", expand=True)
        dys.pack(side="right", fill="y")
        f = self.ui_font
        self.dt.tag_configure("h1", font=(f, 15, "bold"), spacing3=2)
        self.dt.tag_configure("h2", font=(f, 11, "bold"), foreground="#1d4ed8", spacing1=16, spacing3=2)
        self.dt.tag_configure("muted", foreground="#64748b")
        self.dt.tag_configure("ai", background="#f1f5f9", lmargin1=8, lmargin2=8, rmargin=8)
        self.dt.tag_configure("aih", background="#f1f5f9", font=(f, 10, "bold"), lmargin1=8, lmargin2=8, spacing1=6)
        self.dt.tag_configure("mono", font=(self.mono, 9))
        self.dt.tag_configure("bad", foreground="#b91c1c")
        self.paned.add(right, weight=2)

        bottom = ttk.Frame(m)
        bottom.pack(fill="x", padx=10, pady=(2, 4))
        ttk.Button(bottom, text="Copy tree", command=self.copy_tree).pack(side="left", padx=2)
        ttk.Button(bottom, text="Save tree (.txt)", command=self.save_tree).pack(side="left", padx=2)
        self.export_btn = ttk.Button(bottom, text="Export to Obsidian…", command=self.export_obsidian)
        self.export_btn.pack(side="left", padx=(14, 2))
        self.all_btn = ttk.Button(bottom, text="Explain all files with AI…", command=self.explain_all)
        self.all_btn.pack(side="left", padx=2)
        ttk.Label(bottom, textvariable=self.status_var).pack(side="right")
        self.pb = ttk.Progressbar(m, mode="determinate", maximum=100)
        self.pb.pack(fill="x", padx=10, pady=(0, 8))
        self.lockables = [self.scan_btn, self.export_btn, self.all_btn, self.explain_btn]

    def _set_sash(self):
        try:
            self.master.update_idletasks()
            total_w = self.master.winfo_width()
            panes = self.paned.panes()
            num_panes = len(panes)
            if num_panes == 3:
                self.paned.sashpos(0, max(220, int(total_w * 0.22)))
                self.paned.sashpos(1, max(460, int(total_w * 0.65)))
            elif num_panes == 2:
                if str(self.library_panel) in panes:
                    self.paned.sashpos(0, max(220, int(total_w * 0.25)))
                else:
                    self.paned.sashpos(0, int(total_w * 0.58))
        except (tk.TclError, Exception):
            pass

    def toggle_library(self):
        self.library_open = not self.library_open
        if self.library_open:
            self.paned.insert(0, self.library_panel, weight=1)
            self.library_btn.configure(text="◀ Close Library")
            if hasattr(self, "diagram_studio") and hasattr(self.diagram_studio, "lib_toggle_btn"):
                self.diagram_studio.lib_toggle_btn.configure(text="◀ Hide Library")
            self.library_panel.refresh_items()
            self.master.after(50, self._set_sash)
        else:
            self.paned.forget(self.library_panel)
            self.library_btn.configure(text="📚 Diagram Library")
            if hasattr(self, "diagram_studio") and hasattr(self.diagram_studio, "lib_toggle_btn"):
                self.diagram_studio.lib_toggle_btn.configure(text="📚 Library")
            self.master.after(50, self._set_sash)

    def toggle_right_panel(self):
        self.right_open = not self.right_open
        if self.right_open:
            self.paned.add(self.right_panel, weight=2)
            self.details_btn.configure(text="▶ Close Details")
            self.master.after(50, self._set_sash)
        else:
            self.paned.forget(self.right_panel)
            self.details_btn.configure(text="📘 Open Details")
            self.master.after(50, self._set_sash)

    def _prefill(self):
        if self.path_var.get() and os.path.isdir(self.path_var.get()):
            return
        self.path_var.set("")
        try:
            p = core.clean_path(self.master.clipboard_get())
            if p and os.path.isdir(p):
                self.path_var.set(p)
        except tk.TclError:
            pass

    def _close(self):
        self.cfg.update({"last_path": self.path_var.get(), "include_files": self.files_var.get(),
                         "show_hidden": self.hidden_var.get(), "skip_junk": self.junk_var.get()})
        core.save_config(self.cfg)
        self.master.destroy()

    # ---- background work ---------------------------------------------------
    def run_bg(self, work, done):
        def target():
            try:
                res, err = work(), None
            except Exception as e:  # noqa: BLE001
                res, err = None, e
            self.bgq.put((done, res, err))

        threading.Thread(target=target, daemon=True).start()

    def _pump(self):
        try:
            while True:
                done, res, err = self.bgq.get_nowait()
                try:
                    done(res, err)
                except Exception as e:  # noqa: BLE001
                    messagebox.showerror("Unexpected problem", f"{type(e).__name__}: {e}")
        except queue.Empty:
            pass
        if self.working and self.live_fn:
            try:
                text, frac = self.live_fn()
                self.status_var.set(text)
                self._set_progress(frac)
            except Exception:  # noqa: BLE001
                pass
        self.master.after(120, self._pump)

    def _set_progress(self, frac):
        if frac is None:
            if self._pb_mode != "ind":
                self.pb.configure(mode="indeterminate")
                self.pb.start(12)
                self._pb_mode = "ind"
        else:
            if self._pb_mode != "det":
                self.pb.stop()
                self.pb.configure(mode="determinate", maximum=100)
                self._pb_mode = "det"
            self.pb["value"] = frac * 100

    def _busy(self, on, text=None, live=None):
        self.working = on
        self.live_fn = live
        for b in self.lockables:
            b.configure(state="disabled" if on else "normal")
        self.stop_btn.configure(state="normal" if on else "disabled")
        if on:
            self.stop_event.clear()
            if text:
                self.status_var.set(text)
            self._set_progress(None)
        else:
            self.pb.stop()
            self.pb.configure(mode="determinate", maximum=100, value=0)
            self._pb_mode = "det"

    def stop(self):
        self.stop_event.set()
        self.status_var.set("Stopping…")

    # ---- input helpers -----------------------------------------------------
    def paste(self):
        try:
            self.path_var.set(core.clean_path(self.master.clipboard_get()))
        except tk.TclError:
            self.status_var.set("Clipboard is empty.")

    def browse(self):
        d = filedialog.askdirectory(title="Select the folder to map")
        if d:
            self.path_var.set(os.path.normpath(d))
            self.scan()

    def open_settings(self):
        SettingsDialog(self)

    # ---- scanning ------------------------------------------------------------
    def scan(self):
        if self.working:
            return
        path = core.clean_path(self.path_var.get())
        if not path:
            messagebox.showwarning("No path", "Please paste a folder path first.")
            return
        if not os.path.isdir(path):
            messagebox.showerror("Invalid path", f"This folder does not exist:\n\n{path}")
            return
        path = os.path.abspath(path)
        self.path_var.set(path)
        counts = {"dirs": 0, "files": 0}
        phase = {"text": None, "done": 0, "total": 1}

        def live():
            if phase["text"]:
                return f"{phase['text']} {phase['done']}/{phase['total']}", phase["done"] / max(1, phase["total"])
            return f"Scanning…  {counts['dirs']:,} folders, {counts['files']:,} files", None

        self._busy(True, "Scanning…", live)
        show_hidden, skip_junk = self.hidden_var.get(), self.junk_var.get()

        def work():
            root = core.scan_tree(path, show_hidden, skip_junk, counts, self.stop_event)
            proj = core.Project(root)
            phase["text"], phase["total"] = "Reading code…", max(1, len(proj.files))

            def prog(i, n):
                phase["done"] = i

            proj.analyze(prog)
            return proj

        self.run_bg(work, self._scan_done)

    def _scan_done(self, proj, err):
        self._busy(False)
        if err:
            messagebox.showerror("Scan failed", str(err))
            self.status_var.set("Scan failed.")
            return
        self.project = proj
        self.cache = core.ExplainCache(proj.root.path)
        self.vault = diagrams.DiagramVault(proj.root.path)
        self.diagram_studio.set_project(proj, self.vault)
        if hasattr(self, "library_panel") and self.library_panel:
            self.library_panel.set_project(proj, self.vault)
        self.cfg["last_path"] = proj.root.path
        core.save_config(self.cfg)
        self._refresh_tree_text()
        self.mindmap.set_project(proj)
        self.nb.select(self.mindmap)
        self.show("")
        edges = sum(len(i["imports"]) for i in proj.info.values())
        self.status_var.set(f"Done: {proj.root.nfiles:,} files, {edges:,} links between files found.")

    def _refresh_tree_text(self):
        self.tree_text.delete("1.0", "end")
        if self.project:
            text, _ = core.render_text_tree(self.project.root, self.files_var.get())
            self.tree_text.insert("1.0", text)

    def copy_tree(self):
        content = self.tree_text.get("1.0", "end-1c")
        if not content.strip():
            self.status_var.set("Nothing to copy yet - press Scan first.")
            return
        self.master.clipboard_clear()
        self.master.clipboard_append(content)
        self.master.update()
        self.status_var.set("Tree copied to clipboard.")

    def save_tree(self):
        content = self.tree_text.get("1.0", "end-1c")
        if not content.strip():
            self.status_var.set("Nothing to save yet - press Scan first.")
            return
        name = self.project.name if self.project else "tree"
        f = filedialog.asksaveasfilename(title="Save tree", defaultextension=".txt", initialfile=f"{name}_tree.txt",
                                         filetypes=[("Text file", "*.txt"), ("All files", "*.*")])
        if f:
            try:
                with open(f, "w", encoding="utf-8") as fh:
                    fh.write(content)
                self.status_var.set(f"Saved: {f}")
            except OSError as e:
                messagebox.showerror("Could not save", str(e))

    # ---- Global UI Zoom (for eyesight accessibility) -----------------------
    def zoom_ui(self, delta):
        new_scale = max(0.75, min(2.5, self.ui_scale + delta))
        self.set_ui_scale(new_scale)

    def reset_ui_zoom(self):
        self.set_ui_scale(1.0)

    def set_ui_scale(self, scale):
        self.ui_scale = round(scale, 2)
        for name, base in self.base_font_sizes.items():
            try:
                new_sz = max(7, round(base * self.ui_scale))
                tkfont.nametofont(name).configure(size=new_sz)
            except Exception:
                pass

        if hasattr(self, "zoom_lbl"):
            self.zoom_lbl.configure(text=f"{round(self.ui_scale * 100)}%")

        f = self.ui_font
        base_s = max(8, round(10 * self.ui_scale))
        self.dt.tag_configure("h1", font=(f, max(11, round(15 * self.ui_scale)), "bold"))
        self.dt.tag_configure("h2", font=(f, max(9, round(11 * self.ui_scale)), "bold"))
        self.dt.tag_configure("aih", font=(f, max(8, round(10 * self.ui_scale)), "bold"))
        self.dt.tag_configure("mono", font=(self.mono, max(7, round(9 * self.ui_scale))))
        self.dt.configure(font=(f, base_s), wrap="word")

        if hasattr(self, "mindmap") and self.mindmap:
            self.mindmap.render()

    # ---- Context Menu & Visual Studio --------------------------------------
    def _show_context_menu(self, event, rel):
        if not self.project:
            return
        if rel is None:
            rel = self.selected or ""
        self.navigate(rel)

        node = self.project.nodes.get(rel)
        if not node:
            return
        is_file = not node.is_dir
        name = node.name if rel else self.project.name

        menu = tk.Menu(self.master, tearoff=0)

        diag_menu = tk.Menu(menu, tearoff=0)
        for dt_id in diagrams.DIAGRAM_ORDER:
            spec = diagrams.DIAGRAM_TYPES[dt_id]
            diag_menu.add_command(
                label=f"{spec['label']}",
                command=lambda d=dt_id, r=rel: self.generate_diagram_for(r, d)
            )
        menu.add_cascade(label=f"✨ Generate Visual Diagram for '{name}'", menu=diag_menu)

        if self.vault:
            history = self.vault.get_diagrams(rel, is_file)
            if history:
                vault_menu = tk.Menu(menu, tearoff=0)
                for h in history[:12]:
                    vault_menu.add_command(
                        label=f"{h['title']} ({h['timestamp']})",
                        command=lambda entry=h, r=rel: self.open_saved_diagram(r, entry)
                    )
                menu.add_cascade(label=f"📚 Visuals Vault ({len(history)} saved)", menu=vault_menu)
            else:
                menu.add_command(label="📚 Visuals Vault (0 saved)", state="disabled")

        menu.add_separator()
        if is_file and rel and rel.lower().endswith(".json"):
            menu.add_command(label=f"👁 Open '{name}' in React JSON Crack Visualizer",
                             command=lambda: self.open_react_json_visualizer(rel))
        menu.add_command(label=f"🌐 Open in React Visual Control Center",
                         command=lambda: self.open_react_visualizer(rel))
        menu.add_separator()
        menu.add_command(label=f"💬 Chat with AI about '{name}' (Voice & Text)...",
                         command=lambda: self.open_chat_for(rel, is_file))
        menu.add_command(label="📘 Explain in Plain English (AI)", command=lambda: self.explain_selected(False))
        if is_file:
            menu.add_command(label="📂 Open File", command=self.open_selected)

        menu.tk_popup(event.x_root, event.y_root)

    def open_react_visualizer(self, rel=None):
        import codemap_react_bridge
        target_path = None
        if rel and self.project:
            node = self.project.nodes.get(rel)
            if node:
                target_path = node.path
        codemap_react_bridge.open_react_visualizer(file_path=target_path)

    def open_react_json_visualizer(self, rel):
        import codemap_react_bridge
        if not self.project:
            return
        node = self.project.nodes.get(rel)
        if node and os.path.isfile(node.path):
            codemap_react_bridge.open_react_visualizer(file_path=node.path)

    def open_chat_for(self, rel, is_file=False):
        if not self.project:
            messagebox.showinfo("Scan Needed", "Please scan a project folder first.")
            return
        import codemap_chat
        codemap_chat.FolderChatDialog(self.master, self, rel, is_file)

    def _on_tree_right_click(self, event):
        if not self.project:
            return
        try:
            idx = self.tree_text.index(f"@{event.x},{event.y}")
            line = self.tree_text.get(f"{idx} linestart", f"{idx} lineend").strip()
            clean_name = re.sub(r"^[│├└─\s]+", "", line).split("  [")[0].rstrip("/")
            for r, n in self.project.nodes.items():
                if n.name == clean_name:
                    self._show_context_menu(event, r)
                    return
        except Exception:
            pass
        self._show_context_menu(event, self.selected)

    def generate_diagram_for(self, rel, diag_type):
        self.open_diagram_studio(rel)
        self.diagram_studio.generate(diag_type)

    def open_saved_diagram(self, rel, entry):
        self.open_diagram_studio(rel)
        self.diagram_studio.display_entry(entry)

    def open_diagram_studio(self, rel=None):
        if rel is not None:
            self.navigate(rel)
        elif self.selected:
            self.diagram_studio.set_target(self.selected)
        self.nb.select(self.diagram_studio)

    # ---- details panel ---------------------------------------------------------
    def _t(self, text, *tags):
        self.dt.insert("end", text, tags)

    def _link(self, text, rel):
        self._lnk += 1
        tag = f"lnk{self._lnk}"
        self.dt.tag_configure(tag, foreground="#2563eb", underline=True)
        self.dt.tag_bind(tag, "<Button-1>", lambda e, r=rel: self.navigate(r))
        self.dt.tag_bind(tag, "<Enter>", lambda e: self.dt.configure(cursor="hand2"))
        self.dt.tag_bind(tag, "<Leave>", lambda e: self.dt.configure(cursor="arrow"))
        self.dt.insert("end", text, (tag,))

    def _link_list(self, rels, empty, show_role=False, limit=60):
        if not rels:
            self._t(f"  {empty}\n", "muted")
            return
        for r in rels[:limit]:
            self._t("  •  ")
            self._link(r, r)
            if show_role and r in self.project.info:
                self._t("   " + self.project.info[r]["role"].split(" - ")[0], "muted")
            self._t("\n")
        if len(rels) > limit:
            self._t(f"  … and {len(rels) - limit} more\n", "muted")

    def _ai_block(self, text):
        for line in text.splitlines():
            s = line.strip()
            is_head = bool(s) and s == s.upper() and any(ch.isalpha() for ch in s) and len(s) < 60 and not s.startswith("-")
            self._t(line + "\n", "aih" if is_head else "ai")

    def navigate(self, rel):
        if rel and rel.startswith("@studio:"):
            self.open_diagram_studio(rel[len("@studio:"):])
            return
        if self.project and rel in self.project.nodes:
            self.mindmap.reveal(rel)
            self.show(rel)

    def _on_map_select(self, rel):
        self.show(rel)

    def show(self, rel):
        dt = self.dt
        dt.configure(state="normal")
        dt.delete("1.0", "end")
        for t in dt.tag_names():
            if t.startswith("lnk"):
                dt.tag_delete(t)
        self._lnk = 0
        self.selected = rel
        if hasattr(self, "diagram_studio") and self.diagram_studio:
            self.diagram_studio.set_target(rel or "")
        p = self.project
        if p is None or rel is None or rel not in p.nodes:
            self._intro()
            self.explain_btn.configure(state="disabled")
            self.open_btn.configure(state="disabled")
        else:
            node = p.nodes[rel]
            if node.is_dir:
                self._show_folder(rel)
            else:
                self._show_file(rel)
            self.open_btn.configure(state="normal" if not node.is_dir else "disabled")
            if not self.working:
                self.explain_btn.configure(state="normal")
        dt.configure(state="disabled")
        dt.yview_moveto(0)

    def _intro(self):
        self._t("Welcome to CodeMap\n", "h1")
        self._t("\n1.  Paste your source-code folder path above and press ")
        self._t("Scan", "aih")
        self._t(".\n2.  On the Mind Map tab, click a folder to open it, one level at a time.\n"
                "3.  Click any file: you'll see what it is, what it uses, and what uses it. "
                "Green and orange arrows appear on the map.\n"
                "4.  Press ")
        self._t("Explain with AI", "aih")
        self._t(" for a plain-English explanation of the file, folder or whole project.\n"
                "5.  Press ")
        self._t("Export to Obsidian", "aih")
        self._t(" to get linked notes for your vault.\n\n")
        self._t("Mouse: drag the map to move it, Ctrl + wheel to zoom.\n", "muted")

    def _explain_block(self, rel, is_file):
        key = core.ExplainCache.key_for(rel, is_file)
        ai = self.cache.get(key, self.project.sig(rel)) if self.cache else None
        self._t("Plain-English explanation\n", "h2")
        if ai:
            self._ai_block(ai)
            self.explain_btn.configure(text="Re-explain with AI")
        else:
            self.explain_btn.configure(text="Explain with AI")
        return ai

    def _show_file(self, rel):
        p = self.project
        node, info = p.nodes[rel], p.info[rel]
        self._t(node.name + "\n", "h1")
        self._t(rel + "\n", "muted")
        self._t(f"{info['lang']}  ·  {info['lines']:,} lines  ·  {core.human_size(node.size)}\n", "muted")
        self._t("What kind of file is it?\n", "h2")
        self._t(info["role"] + "\n")
        ai = self._explain_block(rel, True)
        if not ai:
            self._t(info["summary"] + "\n")
            self._t("\n(This is a quick guess from code analysis. Press “Explain with AI” for a full explanation.)\n", "muted")

        # Visual Diagrams & Vault Section
        self._t("Visual Diagrams & Vault\n", "h2")
        cnt = self.vault.get_count(rel, True) if self.vault else 0
        if cnt > 0:
            self._t(f"  {cnt} diagram(s) saved in vault. ")
            self._link("Open in Visual Studio →", f"@studio:{rel}")
            self._t("\n")
        else:
            self._t("  No diagrams generated yet. ")
            self._link("✨ Generate Visual Diagram →", f"@studio:{rel}")
            self._t("\n")

        self._t("Uses  (this file depends on)\n", "h2")
        self._link_list(info["imports"], "Nothing else inside this project.")
        self._t("Used by  (these files depend on it)\n", "h2")
        self._link_list(p.imported_by.get(rel, []), "No other project file uses this one.")
        if info["external"]:
            self._t("Outside libraries it uses\n", "h2")
            self._t("  " + ", ".join(info["external"]) + "\n", "mono")
        if info["defines"]:
            self._t("What it defines\n", "h2")
            self._t("  " + ",  ".join(info["defines"][:20]) + "\n", "mono")
        if info["endpoints"]:
            self._t("Web addresses (API) in this file\n", "h2")
            self._t("  " + "\n  ".join(info["endpoints"]) + "\n", "mono")
        if info["meta"]:
            self._t("Details\n", "h2")
            for m in info["meta"]:
                self._t(f"  •  {m}\n")

    def _show_folder(self, rel):
        p = self.project
        is_root = rel == ""
        node = p.nodes[rel]
        st, fs = core.project_stats(p, rel), core.folder_summary(p, rel)
        self._t(("Project overview: " + p.name if is_root else "Folder: " + node.name) + "\n", "h1")
        self._t(node.path + "\n", "muted")
        langs = ", ".join(f"{k} {v}" for k, v in st["langs"].most_common(6))
        self._t(f"{st['files']:,} files  ·  {fs['subfolders']} sub-folders  ·  {st['edges']:,} links between files\n", "muted")
        if langs:
            self._t(langs + "\n", "muted")
        ai = self._explain_block(rel, False)
        if not ai:
            self._t("Click “Explain with AI” for a written explanation of "
                    + ("the whole project" if is_root else "this folder") + ". Below is what code analysis found:\n", "muted")

        # Visual Diagrams & Vault Section for folder
        self._t("Visual Diagrams & Vault\n", "h2")
        cnt = self.vault.get_count(rel, False) if self.vault else 0
        if cnt > 0:
            self._t(f"  {cnt} diagram(s) saved in vault. ")
            self._link("Open in Visual Studio →", f"@studio:{rel}")
            self._t("\n")
        else:
            self._t("  No diagrams generated yet. ")
            self._link("✨ Generate Architecture Diagram →", f"@studio:{rel}")
            self._t("\n")
        if is_root:
            self._t("Where the program probably starts\n", "h2")
            self._link_list(st["entry"], "No obvious entry point found.", show_role=False)
            self._t("Most-used files  (many others depend on them)\n", "h2")
            if st["hubs"]:
                for f, c in st["hubs"]:
                    self._t("  •  ")
                    self._link(f, f)
                    self._t(f"   used by {c}\n", "muted")
            else:
                self._t("  None found.\n", "muted")
            self._t("Not connected to anything\n", "h2")
            self._link_list(st["orphans"], "Every code file is connected to something.")
            if st["externals"]:
                self._t("Outside libraries used\n", "h2")
                self._t("  " + ",  ".join(f"{n} ({c})" for n, c in st["externals"]) + "\n", "mono")
            if st["endpoints"]:
                self._t("Web addresses (API) found\n", "h2")
                for e, f in st["endpoints"]:
                    self._t("  •  " + e + "   in ", "mono")
                    self._link(f, f)
                    self._t("\n")
        else:
            self._t("Key files here  (most used by others)\n", "h2")
            self._link_list(fs["top"], "No file in this folder is used by others.")
            self._t("This folder relies on files in\n", "h2")
            self._folder_links([d for d, _ in fs["out"]], fs["out"])
            self._t("This folder is used by files in\n", "h2")
            self._folder_links([d for d, _ in fs["in"]], fs["in"])
            self._t("Contents\n", "h2")
            self._link_list([c.rel for c in node.children if not c.skipped], "Empty.", limit=40)

    def _folder_links(self, names, counted):
        if not counted:
            self._t("  Nothing outside this folder.\n", "muted")
            return
        for name, c in counted:
            self._t("  •  ")
            if name in self.project.nodes:
                self._link(name, name)
            else:
                self._t(name)
            self._t(f"   {c} link(s)\n", "muted")

    def open_selected(self):
        if not self.project or self.selected not in self.project.nodes:
            return
        path = self.project.nodes[self.selected].path
        try:
            if hasattr(os, "startfile"):
                os.startfile(path)  # noqa: S606 - Windows
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Could not open", str(e))

    # ---- AI ------------------------------------------------------------------------
    def _need_ai(self, msg):
        if messagebox.askyesno("AI helper needed", f"{msg}\n\nOpen AI settings now?"):
            self.open_settings()

    def explain_selected(self, _force):
        if not self.project or self.selected is None or self.working:
            return
        ok, msg = core.provider_ready(self.cfg)
        if not ok:
            self._need_ai(msg)
            return
        rel = self.selected
        is_file = not self.project.nodes[rel].is_dir
        prompt = core.build_file_prompt(self.project, rel) if is_file else core.build_overview_prompt(self.project, rel)
        key, sig = core.ExplainCache.key_for(rel, is_file), self.project.sig(rel)
        cfg = dict(self.cfg)
        label = core.PROVIDERS[cfg["provider"]]["label"].split("(")[0].strip()
        self._busy(True, f"Asking {label}… (usually 10-40 seconds)")

        def done(res, err):
            self._busy(False)
            if err:
                self.status_var.set("The AI helper had a problem.")
                messagebox.showerror("The AI helper had a problem",
                                     f"{err}\n\nTip: open “AI settings…” to check your choice or key.")
                return
            self.cache.put(key, sig, res, cfg["provider"])
            self.status_var.set("Explanation saved (it is remembered for next time).")
            if self.selected == rel:
                self.show(rel)

        self.run_bg(lambda: core.ai_generate(cfg, prompt, max_tokens=2000 if not is_file else 1500), done)

    def explain_all(self):
        if not self.project or self.working:
            return
        ok, msg = core.provider_ready(self.cfg)
        if not ok:
            self._need_ai(msg)
            return
        p, cache = self.project, self.cache
        todo = [f for f in p.explainable_files() if not cache.get(f, p.sig(f))]
        need_overview = not cache.get(core.ExplainCache.key_for("", False), p.sig(""))
        if not todo and not need_overview:
            messagebox.showinfo("Already done", "Every file already has an explanation saved.")
            return
        cfg = dict(self.cfg)
        spec = core.PROVIDERS[cfg["provider"]]
        label = spec["label"].split("(")[0].strip()
        cost = ("It may use a small amount of API credit." if spec["kind"] == "api"
                else "Command-line tools take roughly 10-30 seconds per file.")
        if not messagebox.askyesno("Explain all files",
                                   f"This will send the text of {len(todo)} file(s) to {label}, one at a time, "
                                   f"most-important files first.\n\n{cost}\n\nYou can press Stop at any time - "
                                   f"finished explanations are kept.\n\nContinue?"):
            return
        state = {"done": 0, "total": len(todo) + (1 if need_overview else 0), "fail": 0, "err": None}
        self._busy(True, "Explaining files…",
                   lambda: (f"Explaining files…  {state['done']}/{state['total']}", state["done"] / max(1, state["total"])))

        def work():
            import time
            streak = 0
            for i, f in enumerate(todo):
                if self.stop_event.is_set() or streak >= 3:
                    return state
                if i > 0 and spec["kind"] == "api":
                    time.sleep(1.0)
                try:
                    text = core.ai_generate(cfg, core.build_file_prompt(p, f))
                    cache.put(f, p.sig(f), text, cfg["provider"])
                    streak = 0
                except core.AIError as e:
                    state["fail"] += 1
                    state["err"] = state["err"] or str(e)
                    streak += 1
                state["done"] += 1
            if need_overview and not self.stop_event.is_set() and streak < 3:
                if spec["kind"] == "api" and todo:
                    time.sleep(1.0)
                try:
                    text = core.ai_generate(cfg, core.build_overview_prompt(p, ""), max_tokens=2000)
                    cache.put(core.ExplainCache.key_for("", False), p.sig(""), text, cfg["provider"])
                except core.AIError as e:
                    state["fail"] += 1
                    state["err"] = state["err"] or str(e)
                state["done"] += 1
            return state

        def done(res, err):
            self._busy(False)
            self.show(self.selected)
            if err:
                messagebox.showerror("Problem", str(err))
                return
            msg = f"Finished {state['done']} of {state['total']} explanation(s)."
            if self.stop_event.is_set():
                msg += " (Stopped early.)"
            if state["fail"]:
                msg += f"\n\n{state['fail']} problem(s). First one:\n{state['err']}"
            self.status_var.set(msg.split("\n")[0])
            messagebox.showinfo("Explain all files", msg)

        self.run_bg(work, done)

    # ---- Obsidian ---------------------------------------------------------------------
    def export_obsidian(self):
        if not self.project or self.working:
            if not self.project:
                messagebox.showinfo("Nothing to export", "Scan a folder first.")
            return
        folder = filedialog.askdirectory(title="Choose your Obsidian vault folder (or any folder inside it)",
                                         initialdir=self.cfg.get("last_vault") or os.path.expanduser("~"))
        if not folder:
            return
        folder = os.path.normpath(folder)
        self.cfg["last_vault"] = folder
        core.save_config(self.cfg)
        p, cache = self.project, self.cache
        prog = {"i": 0, "n": max(1, len(p.files))}

        def live():
            return f"Writing notes…  {prog['i']}/{prog['n']}", prog["i"] / prog["n"]

        self._busy(True, "Writing notes…", live)

        def work():
            def cb(i, n):
                prog["i"], prog["n"] = i, max(1, n)

            return core.export_to_obsidian(p, cache, folder, cb)

        def done(res, err):
            self._busy(False)
            if err:
                messagebox.showerror("Export failed", str(err))
                return
            out, overview, n = res
            in_vault = core.find_vault_root(folder) is not None
            extra = "" if in_vault else ("\n\nNote: that folder is not inside an Obsidian vault yet. "
                                         "In Obsidian choose “Open folder as vault” and pick it.")
            self.status_var.set(f"Exported {n} notes.")
            if messagebox.askyesno("Export finished",
                                   f"Created {n} linked notes in:\n{out}{extra}\n\nOpen the overview note in Obsidian now?"):
                self._open_obsidian(overview)

        self.run_bg(work, done)

    def _open_obsidian(self, path):
        uri = "obsidian://open?path=" + urllib.parse.quote(os.path.abspath(path))
        try:
            if hasattr(os, "startfile"):
                os.startfile(uri)  # noqa: S606
            else:
                webbrowser.open(uri)
        except Exception as e:  # noqa: BLE001
            messagebox.showinfo("Open it yourself", f"Could not launch Obsidian automatically ({e}).\n"
                                                    f"Open this file from inside Obsidian:\n{path}")


def main():
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:  # noqa: BLE001
        pass
    root = tk.Tk()
    style = ttk.Style()
    for theme in ("vista", "clam"):
        try:
            style.theme_use(theme)
            break
        except tk.TclError:
            continue
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
