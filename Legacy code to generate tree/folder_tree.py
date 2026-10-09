"""
Folder Tree Generator
---------------------
Paste any folder path, click Generate, and get a complete tree of
folders, sub-folders and files. Copy it or save it as a .txt file.

Requires only Python 3.8+ (tkinter is included with the normal installer).
"""

import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

BRANCH = "├── "
LAST = "└── "
PIPE = "│   "
SPACE = "    "

FILE_ATTRIBUTE_HIDDEN = 0x2
FILE_ATTRIBUTE_REPARSE_POINT = 0x400


# --------------------------------------------------------------------------
# Tree building logic
# --------------------------------------------------------------------------
def clean_path(raw: str) -> str:
    """Strip quotes/spaces (Windows 'Copy as path' adds quotes) and expand ~ and %VARS%."""
    p = raw.strip().strip('"').strip("'").strip()
    return os.path.expandvars(os.path.expanduser(p))


def _attrs(entry):
    try:
        return entry.stat(follow_symlinks=False).st_file_attributes  # Windows only
    except (AttributeError, OSError):
        return 0


def is_hidden(entry) -> bool:
    return entry.name.startswith(".") or bool(_attrs(entry) & FILE_ATTRIBUTE_HIDDEN)


def is_link(entry) -> bool:
    """Symlinks / junctions - listed but never entered (avoids infinite loops)."""
    try:
        return entry.is_symlink() or bool(_attrs(entry) & FILE_ATTRIBUTE_REPARSE_POINT)
    except OSError:
        return False


def walk(path, prefix, lines, counts, include_files, show_hidden, stop_event):
    if stop_event.is_set():
        return

    try:
        with os.scandir(path) as it:
            entries = list(it)
    except PermissionError:
        lines.append(f"{prefix}{LAST}[Access denied]")
        return
    except OSError as e:
        lines.append(f"{prefix}{LAST}[Error: {e.strerror or e}]")
        return

    if not show_hidden:
        entries = [e for e in entries if not is_hidden(e)]

    folders, files = [], []
    for e in entries:
        try:
            (folders if e.is_dir(follow_symlinks=False) else files).append(e)
        except OSError:
            files.append(e)

    def sort_key(e):
        return e.name.lower()

    folders.sort(key=sort_key)
    files.sort(key=sort_key)

    items = [(e, True) for e in folders]
    if include_files:
        items += [(e, False) for e in files]
    else:
        counts["files"] += len(files)  # still count them, just don't list

    for i, (entry, is_dir) in enumerate(items):
        if stop_event.is_set():
            return
        last = i == len(items) - 1
        connector = LAST if last else BRANCH

        if is_dir:
            counts["dirs"] += 1
            if is_link(entry):
                lines.append(f"{prefix}{connector}{entry.name}/  [link - not followed]")
            else:
                lines.append(f"{prefix}{connector}{entry.name}/")
                walk(
                    entry.path,
                    prefix + (SPACE if last else PIPE),
                    lines, counts, include_files, show_hidden, stop_event,
                )
        else:
            counts["files"] += 1
            lines.append(f"{prefix}{connector}{entry.name}")


# --------------------------------------------------------------------------
# GUI
# --------------------------------------------------------------------------
class App:
    def __init__(self, master: tk.Tk):
        self.master = master
        master.title("Folder Tree Generator")
        master.geometry("920x680")
        master.minsize(660, 440)

        self.path_var = tk.StringVar()
        self.files_var = tk.BooleanVar(value=True)
        self.hidden_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Paste a folder path above, then press Generate.")

        self.q = queue.Queue()
        self.stop_event = threading.Event()
        self.counts = {"dirs": 0, "files": 0}
        self.running = False
        self.current_root = ""

        self._build_ui()
        self._prefill_from_clipboard()
        self.entry.focus_set()

    # ---- layout -----------------------------------------------------------
    def _build_ui(self):
        pad = {"padx": 10, "pady": 5}

        top = ttk.Frame(self.master)
        top.pack(fill="x", **pad)
        ttk.Label(top, text="Folder path:").pack(side="left")
        self.entry = ttk.Entry(top, textvariable=self.path_var, font=("Segoe UI", 10))
        self.entry.pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(top, text="Paste", width=7, command=self.paste).pack(side="left", padx=2)
        ttk.Button(top, text="Browse…", width=9, command=self.browse).pack(side="left", padx=2)

        opts = ttk.Frame(self.master)
        opts.pack(fill="x", **pad)
        ttk.Checkbutton(opts, text="Include files", variable=self.files_var).pack(side="left")
        ttk.Checkbutton(opts, text="Show hidden", variable=self.hidden_var).pack(side="left", padx=15)
        self.stop_btn = ttk.Button(opts, text="Stop", width=8, command=self.stop, state="disabled")
        self.stop_btn.pack(side="right", padx=2)
        self.gen_btn = ttk.Button(opts, text="Generate Tree", width=16, command=self.generate)
        self.gen_btn.pack(side="right", padx=2)

        mid = ttk.Frame(self.master)
        mid.pack(fill="both", expand=True, padx=10, pady=5)
        self.text = tk.Text(mid, wrap="none", font=("Consolas", 10), undo=False)
        ys = ttk.Scrollbar(mid, orient="vertical", command=self.text.yview)
        xs = ttk.Scrollbar(mid, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        mid.rowconfigure(0, weight=1)
        mid.columnconfigure(0, weight=1)

        bottom = ttk.Frame(self.master)
        bottom.pack(fill="x", **pad)
        ttk.Button(bottom, text="Copy Tree", command=self.copy_tree).pack(side="left", padx=2)
        ttk.Button(bottom, text="Save as .txt", command=self.save_tree).pack(side="left", padx=2)
        ttk.Button(bottom, text="Clear", command=self.clear).pack(side="left", padx=2)
        ttk.Label(bottom, textvariable=self.status_var).pack(side="right")

        self.progress = ttk.Progressbar(self.master, mode="indeterminate")
        self.progress.pack(fill="x", padx=10, pady=(0, 8))

        self.entry.bind("<Return>", lambda e: self.generate())

    # ---- helpers ----------------------------------------------------------
    def _prefill_from_clipboard(self):
        try:
            p = clean_path(self.master.clipboard_get())
            if p and os.path.isdir(p):
                self.path_var.set(p)
        except tk.TclError:
            pass

    def paste(self):
        try:
            self.path_var.set(clean_path(self.master.clipboard_get()))
        except tk.TclError:
            self.status_var.set("Clipboard is empty.")

    def browse(self):
        folder = filedialog.askdirectory(title="Select a folder")
        if folder:
            self.path_var.set(os.path.normpath(folder))
            self.generate()

    def clear(self):
        self.text.delete("1.0", "end")
        self.status_var.set("Cleared.")

    def copy_tree(self):
        content = self.text.get("1.0", "end-1c")
        if not content.strip():
            self.status_var.set("Nothing to copy yet.")
            return
        self.master.clipboard_clear()
        self.master.clipboard_append(content)
        self.master.update()
        self.status_var.set("Tree copied to clipboard.")

    def save_tree(self):
        content = self.text.get("1.0", "end-1c")
        if not content.strip():
            self.status_var.set("Nothing to save yet.")
            return
        name = os.path.basename(self.current_root.rstrip("\\/")) or "root"
        file = filedialog.asksaveasfilename(
            title="Save tree",
            defaultextension=".txt",
            initialfile=f"{name}_tree.txt",
            filetypes=[("Text file", "*.txt"), ("All files", "*.*")],
        )
        if file:
            try:
                with open(file, "w", encoding="utf-8") as f:
                    f.write(content)
                self.status_var.set(f"Saved: {file}")
            except OSError as e:
                messagebox.showerror("Could not save", str(e))

    # ---- generation -------------------------------------------------------
    def generate(self):
        if self.running:
            return
        root = clean_path(self.path_var.get())
        if not root:
            messagebox.showwarning("No path", "Please paste a folder path first.")
            return
        if not os.path.isdir(root):
            messagebox.showerror("Invalid path", f"This folder does not exist:\n\n{root}")
            return

        root = os.path.abspath(root)
        self.path_var.set(root)
        self.current_root = root
        self.text.delete("1.0", "end")
        self.counts = {"dirs": 0, "files": 0}
        self.stop_event.clear()
        self.running = True
        self.gen_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.progress.start(12)

        args = (root, self.files_var.get(), self.hidden_var.get())
        threading.Thread(target=self._work, args=args, daemon=True).start()
        self.master.after(100, self._poll)

    def _work(self, root, include_files, show_hidden):
        try:
            lines = [root]
            walk(root, "", lines, self.counts, include_files, show_hidden, self.stop_event)
            self.q.put(("done", "\n".join(lines)))
        except Exception as e:  # noqa: BLE001
            self.q.put(("error", str(e)))

    def _poll(self):
        try:
            kind, payload = self.q.get_nowait()
        except queue.Empty:
            self.status_var.set(
                f"Scanning…  {self.counts['dirs']:,} folders, {self.counts['files']:,} files"
            )
            self.master.after(100, self._poll)
            return

        self.running = False
        self.progress.stop()
        self.gen_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

        if kind == "error":
            messagebox.showerror("Error", payload)
            self.status_var.set("Failed.")
            return

        self.text.insert("1.0", payload)
        stopped = " (stopped early)" if self.stop_event.is_set() else ""
        self.status_var.set(
            f"Done{stopped}: {self.counts['dirs']:,} folders, {self.counts['files']:,} files"
        )

    def stop(self):
        self.stop_event.set()
        self.status_var.set("Stopping…")


def main():
    # Sharper text on high-DPI Windows screens
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:  # noqa: BLE001
        pass

    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
