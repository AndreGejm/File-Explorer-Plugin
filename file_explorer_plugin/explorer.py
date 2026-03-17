import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from pathlib import Path
from typing import Optional, List, Generator, Union, Tuple, Callable
import threading
import queue
import shutil
import zipfile
import platform
import _tkinter
import json
import datetime
import subprocess

from .utils import FileNode, ScanStatus, FileUtils
from .themes import ThemeEngine
from .legacy_engine import DirectoryInspector
from .inspector_core import DirectoryInspectorCore
from .inspector_types import ScanConfig

class HeadlessInspectorAdapter:
    """
    Adapter that bridges the new DirectoryInspectorCore with the legacy FileNode system.
    """
    def __init__(self, root_path: Path, sort_by: str = "name", max_depth: Optional[int] = None, item_count_threshold: int = 1000):
        self.root_path = root_path
        self.sort_by = sort_by
        self.max_depth = max_depth
        self.item_count_threshold = item_count_threshold
        self._cancel_flag = False

    def cancel(self):
        self._cancel_flag = True

    def scan_dir_generator(self, path: Path, query: str = "", max_peek_depth: int = 2, current_depth: int = 0) -> Generator[Union[FileNode, ScanStatus], None, None]:
        path = path.resolve()
        if not path.exists():
            yield ScanStatus.IO_ERROR
            return

        config: ScanConfig = {
            "root_path": str(path),
            "max_depth": 0,
            "sort_by": self.sort_by if self.sort_by in ("name", "size", "type") else "name", # type: ignore
            "excludes": ["__pycache__", ".git", ".venv", "node_modules"],
            "exclude_hidden": False
        }
        
        core = DirectoryInspectorCore(config)
        try:
            results = core.scan()
            count = 0
            for r in results:
                if self._cancel_flag: break
                
                node: FileNode = {
                    "path": Path(r["path_absolute"]),
                    "name": r["name"],
                    "is_dir": bool(r["is_dir"]),
                    "size_bytes": r["size_bytes"],
                    "modified_epoch": r["modified_epoch_s"],
                    "extension": r["extension"],
                    "depth": current_depth,
                    "error": r["error"]["message"] if r["error"] else None
                }

                if query:
                    q = query.lower()
                    err_msg = node["error"].lower() if node["error"] else ""
                    if q in node["name"].lower() or q in err_msg:
                        yield node
                        count += 1
                    elif node["is_dir"] and self.has_match_deep(node["path"], q, 1, max_peek_depth):
                        yield node
                        count += 1
                else:
                    yield node
                    count += 1
            
            yield ScanStatus.SUCCESS
        except Exception as e:
            yield ScanStatus.IO_ERROR

    def has_match_deep(self, path: Path, query: str, current_depth: int, max_depth: int) -> bool:
        """Helper to mimic legacy recursive search peeking."""
        if current_depth > max_depth: return False
        try:
            for item in path.iterdir():
                if query in item.name.lower(): return True
                if item.is_dir() and self.has_match_deep(item, query, current_depth+1, max_depth): return True
        except: pass
        return False

    def scan(self) -> Generator[FileNode, None, None]:
        """Legacy materialization delegate for recursive CLI/Export."""
        config: ScanConfig = {
            "root_path": str(self.root_path),
            "max_depth": self.max_depth,
            "sort_by": self.sort_by if self.sort_by in ("name", "size", "type") else "name", # type: ignore
            "excludes": ["__pycache__", ".git", ".venv", "node_modules"],
            "exclude_hidden": False
        }
        core = DirectoryInspectorCore(config)
        for r in core.scan():
            if self._cancel_flag: break
            node: FileNode = {
                "path": Path(r["path_absolute"]),
                "name": r["name"],
                "is_dir": r["is_dir"],
                "size_bytes": r["size_bytes"],
                "modified_epoch": r["modified_epoch_s"],
                "extension": r["extension"],
                "depth": r["depth"],
                "error": r["error"]["message"] if r["error"] else None
            }
            yield node

    def export_to_file(self, output_file="folder_contents.txt"):
        """Exports the current structure to a file using the new core."""
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                for n in self.scan():
                    indent = "    " * n["depth"]
                    if n["is_dir"]:
                        f.write(f"{indent}{n['name']}/\n")
                    else:
                        f.write(f"{indent}{n['name']}\n")
            print(f"Exported to {output_file} (New Engine)")
        except Exception as e: print(f"Export failed: {e}")

    def export_to_json(self):
        """Prints the entire scan result as a JSON array to stdout."""
        try:
            results = list(self.scan())
            serializable = []
            for n in results:
                n_copy = n.copy()
                n_copy["path"] = str(n_copy["path"])
                serializable.append(n_copy)
            print(json.dumps(serializable, indent=2))
        except Exception as e:
            print(json.dumps({"error": str(e)}))

    def run_cli(self):
        """Prints the structure to console using the new core."""
        for n in self.scan():
            indent = "    " * n["depth"]
            if n["is_dir"]:
                print(f"{indent}{n['name']}/")
            else:
                print(f"{indent}{n['name']}")

    @staticmethod
    def open_path(path: Path): DirectoryInspector.open_path(path)
    def rename_node(self, old_path: Path, new_name: str): pass
    def delete_node(self, path: Path): pass
    def create_zip(self, path: Path): pass

class ExplorerComponent(ttk.Frame):
    """
    A reusable, highly-hardened directory explorer component for Tkinter.
    """
    def __init__(self, parent, root_path: Optional[Path] = None, inspector: Optional[DirectoryInspector] = None):
        super().__init__(parent, style="Explorer.TFrame")
        self.inspector = inspector or DirectoryInspector()
        self._event_callbacks = {"select": [], "open": []}
        
        self._state_lock = threading.Lock()
        self.current_scan_id = 0
        self._active_nodes = {}
        self._current_palette = ThemeEngine.DEFAULT_DARK
        
        self.root_path: Optional[Path] = None
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *args: self.apply_filter())
        self.filter_after_id = None
        self.max_peek_depth = 2
        self.max_depth_var = tk.StringVar(value="")
        self._skip_warning_paths = set()
        self._clipboard: Optional[Tuple[str, Path]] = None
        
        self.scan_queue = queue.Queue()
        self._icons = {}
        self._load_icons()
        
        self._setup_ui()
        self._setup_context_menu()
        self._process_queue_loop()
        self.set_theme(ThemeEngine.DEFAULT_DARK)
        
        if root_path: self.set_root(Path(root_path))

    def _load_icons(self):
        """Loads PNG icons and resizes them for the treeview."""
        icon_map = {"folder": "folder.png", "file": "file.png", "code": "code.png", "zip": "zip.png", "image": "image.png"}
        # Resolve assets path relative to the script's root (one level up from package)
        base_dir = Path(__file__).parent.parent
        assets_dir = base_dir / "assets"
        
        for key, filename in icon_map.items():
            try:
                path = assets_dir / filename
                if path.exists():
                    img = tk.PhotoImage(file=str(path))
                    w, h = img.width(), img.height()
                    factor = max(1, w // 16)
                    self._icons[key] = img.subsample(x=factor, y=factor)
                else: self._icons[key] = ""
            except Exception as e:
                print(f"[UI ERROR] Failed to load icon {filename}: {e}", flush=True)
                self._icons[key] = ""

    def _get_icon_for_node(self, node: FileNode):
        if node["is_dir"]: return self._icons.get("folder", "")
        ext = node["extension"].lower()
        if ext in (".py", ".js", ".html", ".css", ".cpp", ".c", ".h", ".ts", ".go", ".rs"): return self._icons.get("code", "")
        if ext in (".zip", ".rar", ".7z", ".tar", ".gz"): return self._icons.get("zip", "")
        if ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp"): return self._icons.get("image", "")
        return self._icons.get("file", "")

    def _setup_ui(self):
        self.breadcrumb_frame = ttk.Frame(self, style="Explorer.TFrame")
        self.breadcrumb_frame.pack(fill='x', padx=5, pady=(0, 5))

        ctrl_frame = ttk.Frame(self, style="Explorer.TFrame")
        ctrl_frame.pack(fill='x', pady=(0, 5))
        
        filter_frame = ttk.Frame(ctrl_frame, style="Explorer.TFrame")
        filter_frame.pack(side='left', padx=5)
        ttk.Label(filter_frame, text="Filter:", style="Explorer.TLabel").pack(side='left')
        ttk.Entry(filter_frame, textvariable=self.filter_var, width=15, style="Explorer.TEntry").pack(side='left', padx=5)
        
        depth_frame = ttk.Frame(ctrl_frame, style="Explorer.TFrame")
        depth_frame.pack(side='left', padx=5)
        ttk.Label(depth_frame, text="Depth:", style="Explorer.TLabel").pack(side='left')
        ttk.Entry(depth_frame, textvariable=self.max_depth_var, width=3, style="Explorer.TEntry").pack(side='left', padx=5)
        self.max_depth_var.trace_add("write", lambda *args: self.apply_depth())

        sort_frame = ttk.Frame(ctrl_frame, style="Explorer.TFrame")
        sort_frame.pack(side='left', padx=5)
        self.cmb_sort = ttk.Combobox(sort_frame, values=["name", "type", "size"], width=6, state="readonly")
        self.cmb_sort.set(self.inspector.sort_by)
        self.cmb_sort.pack(side='left', padx=5)
        self.cmb_sort.bind("<<ComboboxSelected>>", self.on_sort_change)

        self.show_details_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(ctrl_frame, text="Det", variable=self.show_details_var, command=self.toggle_details).pack(side='right', padx=5)

        tree_container = ttk.Frame(self, style="Explorer.TFrame")
        tree_container.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(tree_container, columns=("size", "date"), show="tree headings", style="Explorer.Treeview")
        self.tree.heading("#0", text="Name"); self.tree.heading("size", text="Size"); self.tree.heading("date", text="Modified")
        self.tree.column("#0", minwidth=150, width=400, stretch=True)
        self.tree.column("size", width=100, minwidth=80, stretch=False, anchor='e')
        self.tree.column("date", width=150, minwidth=120, stretch=False, anchor='w')
        self.tree.pack(side='left', fill='both', expand=True)
        
        self.tree.bind("<Configure>", self._on_tree_resize)
        
        sb = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        sb.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=sb.set)
        
        self.tree.tag_configure("item", foreground=self._current_palette["tree_fg"])
        self.tree.tag_configure("matching", foreground=self._current_palette["accent"], font=("Segoe UI", 9, "bold"))
        
        self.tree.bind("<<TreeviewOpen>>", self.on_expand)
        self.tree.bind("<<TreeviewSelect>>", self._internal_on_select)
        self.tree.bind("<Double-1>", self._internal_on_double_click)
        self.tree.bind("<Return>", self._internal_on_double_click)

    def _setup_context_menu(self):
        self._context_menu = tk.Menu(self, tearoff=0)
        self._context_menu.add_command(label="Open", command=self.ctx_open)
        self._context_menu.add_command(label="Open in Terminal", command=self.ctx_open_terminal)
        self._context_menu.add_command(label="Open With...", command=self.ctx_open_with)
        self._context_menu.add_separator()
        self._context_menu.add_command(label="Copy as Path", command=self.ctx_copy_path)
        self._context_menu.add_separator()
        self._context_menu.add_command(label="Cut", command=lambda: self.ctx_clipboard('cut'))
        self._context_menu.add_command(label="Copy", command=lambda: self.ctx_clipboard('copy'))
        self._context_menu.add_command(label="Paste", command=self.ctx_paste)
        self._context_menu.add_separator()
        self._context_menu.add_command(label="Rename", command=self.ctx_rename)
        self._context_menu.add_command(label="Delete", command=self.ctx_delete)
        self._context_menu.add_separator()
        self._context_menu.add_command(label="Compress to ZIP", command=self.ctx_zip)
        self._context_menu.add_separator()
        self._context_menu.add_command(label="Properties", command=self.ctx_properties)
        self.tree.bind("<Button-3>", self._show_context_menu)
        if platform.system() == "Darwin": self.tree.bind("<Button-2>", self._show_context_menu)

    def _show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self._context_menu.post(event.x_root, event.y_root)

    def ctx_open(self):
        path = self.get_selection()
        if path:
            if path.is_dir(): self.set_root(path)
            else: DirectoryInspector.open_path(path)

    def ctx_open_terminal(self):
        path = self.get_selection()
        if not path: return
        target = path if path.is_dir() else path.parent
        try:
            if platform.system() == "Windows":
                subprocess.Popen(['powershell.exe'], cwd=str(target))
            elif platform.system() == "Darwin":
                subprocess.Popen(['open', '-a', 'Terminal', str(target)])
            else:
                subprocess.Popen(['x-terminal-emulator'], cwd=str(target))
        except Exception as e: messagebox.showerror("Error", f"Could not open terminal: {e}")

    def ctx_open_with(self):
        path = self.get_selection()
        if not path or path.is_dir(): return
        try:
            if platform.system() == "Windows":
                subprocess.Popen(['rundll32.exe', 'shell32.dll,OpenAs_RunDLL', str(path)])
            elif platform.system() == "Darwin":
                subprocess.Popen(['open', '-a', 'TextEdit', str(path)])
            else:
                subprocess.Popen(['xdg-open', str(path)])
        except Exception as e: messagebox.showerror("Error", f"Open With failed: {e}")

    def ctx_copy_path(self):
        path = self.get_selection()
        if path:
            self.clipboard_clear()
            self.clipboard_append(str(path.absolute()))
            self.update()

    def ctx_clipboard(self, mode):
        path = self.get_selection()
        if path: self._clipboard = (mode, path)

    def ctx_paste(self):
        if not self._clipboard: return
        mode, src = self._clipboard
        dest_dir = self.get_selection()
        if not dest_dir: dest_dir = self.root_path
        elif not dest_dir.is_dir(): dest_dir = dest_dir.parent
        if not dest_dir: return

        dest = dest_dir / src.name
        if dest.exists() and not messagebox.askyesno("Overwrite", f"'{dest.name}' already exists. Overwrite?"):
            return

        def _do_paste():
            try:
                if mode == 'copy':
                    if src.is_dir(): shutil.copytree(src, dest, dirs_exist_ok=True)
                    else: shutil.copy2(src, dest)
                else: # cut
                    shutil.move(str(src), str(dest))
                    with self._state_lock: self._clipboard = None
                self.after(10, self.refresh)
            except Exception as e:
                self.after(10, lambda: messagebox.showerror("Error", f"Paste failed: {e}"))

        threading.Thread(target=_do_paste, daemon=True).start()

    def ctx_rename(self):
        path = self.get_selection()
        if not path: return
        new_name = simpledialog.askstring("Rename", "New name:", initialvalue=path.name)
        if new_name and new_name != path.name:
            try:
                dest = path.parent / new_name
                path.rename(dest)
                self.refresh()
            except Exception as e: messagebox.showerror("Error", f"Rename failed: {e}")

    def ctx_delete(self):
        path = self.get_selection()
        if not path: return
        if messagebox.askyesno("Delete", f"Are you sure you want to delete '{path.name}'?"):
            try:
                if path.is_dir(): shutil.rmtree(path)
                else: path.unlink()
                self.refresh()
            except Exception as e: messagebox.showerror("Error", f"Delete failed: {e}")

    def ctx_zip(self):
        path = self.get_selection()
        if not path: return
        def _do_zip():
            try:
                if path.is_dir(): shutil.make_archive(str(path), 'zip', path.parent, path.name)
                else:
                    zip_path = path.with_suffix(path.suffix + ".zip")
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
                        z.write(path, path.name)
                self.after(10, self.refresh)
            except Exception as e:
                self.after(10, lambda: messagebox.showerror("Error", f"ZIP failed: {e}"))
        threading.Thread(target=_do_zip, daemon=True).start()

    def ctx_properties(self):
        path = self.get_selection()
        if not path: return
        try:
            stat = path.stat()
            created = FileUtils.format_time(stat.st_ctime)
            modified = FileUtils.format_time(stat.st_mtime)
            size = FileUtils.format_size(stat.st_size)
            msg = f"Name: {path.name}\nType: {'Folder' if path.is_dir() else 'File'}\nPath: {path.absolute()}\n\nSize: {size}\nCreated: {created}\nModified: {modified}"
            messagebox.showinfo("Properties", msg)
        except Exception as e: messagebox.showerror("Error", f"Properties failed: {e}")

    def set_root(self, path: Path):
        if not path.exists() or not path.is_dir():
            messagebox.showerror("Error", f"Invalid path: {path}")
            return
        with self._state_lock:
            self.current_scan_id += 1
            sid = self.current_scan_id
        self.root_path = path.resolve()
        root_iid = str(self.root_path).lower()
        
        self.tree.delete(*self.tree.get_children())
        try:
            stat = self.root_path.stat()
            node = self.tree.insert("", "end", iid=root_iid, text=str(self.root_path), 
                                   values=("<DIR>", FileUtils.format_time(stat.st_mtime)), open=True, image=self._icons.get("folder", ""))
            self.populate_node(node, self.root_path, sid=sid)
        except Exception as e:
            print(f"[UI ERROR] Failed to set root: {e}", flush=True)
        self._update_breadcrumbs()

    def get_selection(self) -> Optional[Path]:
        sel = self.tree.selection()
        if not sel: return None
        try:
            p = Path(sel[0])
            return p
        except Exception: return None

    def refresh(self):
        if self.root_path: self.set_root(self.root_path)

    def bind_event(self, event_type: str, callback: Callable[[Path], None]):
        if event_type in self._event_callbacks:
            self._event_callbacks[event_type].append(callback)

    def set_theme(self, palette: dict):
        self._current_palette = palette
        ThemeEngine.apply(self, palette)
        self.configure(style="Explorer.TFrame")
        self._context_menu.configure(bg=palette["bg"], fg=palette["fg"], activebackground=palette["accent"], activeforeground=palette["bg"])
        if hasattr(self, 'tree'):
            self.tree.tag_configure("item", foreground=palette["tree_fg"])
            self.tree.tag_configure("matching", foreground=palette["accent"])
        self._set_widget_styles(self, palette)
        self._update_breadcrumbs()

    def _on_tree_resize(self, event):
        tw = event.width
        if tw < 300: return
        size_w = 100
        date_w = 150
        name_w = max(150, tw - size_w - date_w - 20)
        self.tree.column("#0", width=name_w)
        self.tree.column("size", width=size_w)
        self.tree.column("date", width=date_w)

    def _set_widget_styles(self, parent, palette):
        for child in parent.winfo_children():
            if isinstance(child, (ttk.Frame, tk.Frame)):
                try: child.configure(style="Explorer.TFrame")
                except: pass
                self._set_widget_styles(child, palette)
            elif isinstance(child, ttk.Label): child.configure(style="Explorer.TLabel")
            elif isinstance(child, ttk.Entry): child.configure(style="Explorer.TEntry")
            elif isinstance(child, ttk.Treeview): child.configure(style="Explorer.Treeview")

    def _update_breadcrumbs(self):
        for child in self.breadcrumb_frame.winfo_children(): child.destroy()
        if not self.root_path: return
        parts = self.root_path.parts
        full = Path(parts[0])
        for i, part in enumerate(parts):
            if i > 0: full = full / part
            p = Path(full)
            if not p.exists(): continue
            btn = tk.Button(self.breadcrumb_frame, text=part, command=lambda p=p: self.set_root(p),
                            relief="flat", bg=self._current_palette["bg"],
                            fg=self._current_palette["accent"],
                            activeforeground=self._current_palette["accent"],
                            activebackground=self._current_palette["bg"],
                            font=("Segoe UI", 9), cursor="hand2")
            btn.pack(side='left')
            if i < len(parts) - 1: ttk.Label(self.breadcrumb_frame, text=" > ", style="Explorer.TLabel").pack(side='left')

    def populate_node(self, node, path: Path, level=0, sid=None):
        if self.inspector.max_depth is not None and level > self.inspector.max_depth: return
        with self._state_lock:
            if sid is None: sid = self.current_scan_id
        if str(path) not in self._skip_warning_paths:
            try:
                if sum(1 for _ in path.iterdir()) > self.inspector.item_count_threshold:
                    if messagebox.askyesno("Large Folder", f"Continue with >{self.inspector.item_count_threshold} items?"):
                        self._skip_warning_paths.add(str(path))
                    else:
                        self.tree.insert(node, "end", text="[Load Cancelled]"); return
            except PermissionError: pass
        if node and not self.tree.exists(node): return
        self.tree.insert(node, "end", iid=f"{node}_scanning", text="[Scanning...]")
        filter_text = self.filter_var.get()
        threading.Thread(target=self._scan_worker, args=(node, path, level, sid, filter_text), daemon=True).start()

    def _scan_worker(self, node, path: Path, level, sid, filter_text):
        with self._state_lock:
            if sid != self.current_scan_id: return
        batch = []
        generator = self.inspector.scan_dir_generator(path, query=filter_text, max_peek_depth=self.max_peek_depth, current_depth=level)
        try:
            for result in generator:
                with self._state_lock:
                    if sid != self.current_scan_id: break
                if isinstance(result, dict):
                    sz = "[Error]" if result["error"] else ("<DIR>" if result["is_dir"] else FileUtils.format_size(result["size_bytes"]))
                    normalized_iid = str(result["path"]).lower()
                    batch.append({"iid": normalized_iid, "name": result["name"], 
                                 "values": (sz, FileUtils.format_time(result["modified_epoch"])), "is_dir": result["is_dir"], 
                                 "icon": self._get_icon_for_node(result)})
                    if len(batch) >= 40:
                        self.scan_queue.put(("items", node, batch, sid)); batch = []
                else:
                    if batch: self.scan_queue.put(("items", node, batch, sid))
                    self.scan_queue.put(("status", node, result, sid))
        except Exception as e:
            print(f"[WORKER ERROR] Scan failed for {path}: {e}", flush=True)
            self.scan_queue.put(("status", node, ScanStatus.IO_ERROR, sid))
        finally:
            try: generator.close()
            except: pass

    def _process_queue_loop(self):
        start = datetime.datetime.now()
        try:
            while True:
                msg_type, node, data, sid = self.scan_queue.get_nowait()
                with self._state_lock:
                    if sid != self.current_scan_id: continue
                if msg_type == "items":
                    q = self.filter_var.get()
                    if node and not self.tree.exists(node): continue
                    for item in data:
                        iid = item["iid"]
                        tags = ("matching", "item") if q and q.lower() in item["name"].lower() else ("item",)
                        try:
                            if not self.tree.exists(iid):
                                n = self.tree.insert(node, "end", iid=iid, text=item["name"], 
                                                   values=item["values"], open=bool(q), tags=tags, image=item["icon"])
                                if item["is_dir"] and not q:
                                    try: self.tree.insert(n, "end", text="dummy")
                                    except _tkinter.TclError: pass
                        except _tkinter.TclError: pass
                elif msg_type == "status":
                    try:
                        ph = f"{node}_scanning"
                        if self.tree.exists(ph):
                            if data == ScanStatus.SUCCESS: self.tree.delete(ph)
                            elif data == ScanStatus.ACCESS_DENIED: self.tree.item(ph, text="[Permission Denied]")
                            elif data == ScanStatus.IO_ERROR: self.tree.item(ph, text="[IO Error]")
                    except _tkinter.TclError: pass
                
                if (datetime.datetime.now() - start).total_seconds() > 0.05: break
        except queue.Empty: pass
        finally: self.after(10, self._process_queue_loop)

    def on_expand(self, event):
        item = self.tree.focus()
        if not item: return
        path = Path(item)
        if not path.exists(): return
        if self.tree.get_children(item) and self.tree.item(self.tree.get_children(item)[0], "text") == "dummy":
            self.tree.delete(self.tree.get_children(item)[0])
            self.populate_node(item, path)

    def _internal_on_select(self, event):
        path = self.get_selection()
        if path:
            for cb in self._event_callbacks["select"]: cb(path)

    def _internal_on_double_click(self, event):
        path = self.get_selection()
        if path and path.exists():
            if path.is_dir(): self.set_root(path)
            else:
                for cb in self._event_callbacks["open"]: cb(path)

    def toggle_details(self):
        show = self.show_details_var.get()
        cols = ("size", "date") if show else ()
        self.tree.configure(displaycolumns=cols)

    def on_sort_change(self, event):
        self.inspector.sort_by = self.cmb_sort.get()
        self.refresh()

    def apply_filter(self):
        if self.filter_after_id: self.after_cancel(self.filter_after_id)
        self.filter_after_id = self.after(400, self.refresh)

    def apply_depth(self):
        val = self.max_depth_var.get()
        try:
            self.inspector.max_depth = int(val) if val else None
            self.refresh()
        except ValueError: pass
