import os
import sys
import argparse
import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
import subprocess
import platform
import math
import threading
import queue
import re
import shutil
import zipfile
from enum import Enum, auto
from typing import Optional, List, Generator, Tuple, Union, TypedDict, Callable

class ScanStatus(Enum):
    """Status codes for background directory scanning operations."""
    SUCCESS = auto()
    PARTIAL = auto()
    ACCESS_DENIED = auto()
    IO_ERROR = auto()
    CANCELLED = auto()

class FileNode(TypedDict):
    """
    Deterministic data model for file system entries.
    """
    path: Path
    name: str
    is_dir: bool
    size_bytes: int
    modified_epoch: float
    extension: str
    depth: int
    error: Optional[str]

class FileUtils:
    """Pure utility layer for formatting and system operations."""
    
    @staticmethod
    def format_size(size_bytes: int) -> str:
        """Converts bytes to a human-readable string (KB, MB, etc.)."""
        if size_bytes <= 0: return "0 B"
        units = ("B", "KB", "MB", "GB", "TB")
        try:
            i = int(math.floor(math.log(size_bytes, 1024)))
            p = math.pow(1024, i)
            s = round(float(size_bytes / p), 2)
            return f"{s} {units[i]}"
        except (ValueError, OverflowError):
            return f"{size_bytes} B"

    @staticmethod
    def format_time(seconds: float) -> str:
        """Converts Unix epoch to YYYY-MM-DD HH:MM string."""
        try:
            return datetime.datetime.fromtimestamp(seconds).strftime("%Y-%m-%d %H:%M")
        except (ValueError, OSError, OverflowError):
            return "Unknown"

    @staticmethod
    def natural_sort_key(s: str) -> List[Union[int, str]]:
        """
        Generates a key for natural sorting (e.g., '2.txt' < '10.txt').
        """
        try:
            return [int(text) if text.isdigit() else text.lower()
                    for text in re.split(r'(\d+)', s)]
        except Exception:
            return [s.lower()]

class DirectoryInspector:
    """
    Core logic for directory scanning, filtering, and sorting.
    """
    def __init__(self, root_path=None, max_depth=None, item_count_threshold=1000, sort_by="name"):
        self.root_path = Path(root_path).resolve() if root_path else None
        self._max_depth = self._validate_depth(max_depth)
        self.item_count_threshold = item_count_threshold
        self.sort_by = sort_by
        self.excludes = {'__pycache__', '.git', '.venv', 'node_modules'}

    @property
    def max_depth(self):
        return self._max_depth

    @max_depth.setter
    def max_depth(self, value):
        self._max_depth = self._validate_depth(value)

    def _validate_depth(self, depth: Optional[int]) -> Optional[int]:
        """Ensures depth invariant: 0 <= depth <= INT_MAX."""
        if depth is None: return None
        try:
            d = int(depth)
            return max(0, min(d, sys.maxsize))
        except (ValueError, TypeError):
            return None

    def should_exclude(self, path: Path) -> bool:
        """Determines if a path should be skipped based on exclusion rules."""
        if path.name in self.excludes: return True
        if path.suffix.lower() == '.pyc': return True
        return False

    def get_sort_key(self, node: FileNode):
        """Returns a stable sort key for FileNode ordering."""
        is_dir_prefix = 0 if node["is_dir"] else 1
        
        if node["error"]:
            return (is_dir_prefix, 2, FileUtils.natural_sort_key(node["name"]))

        try:
            if self.sort_by == "size":
                return (is_dir_prefix, 0, -node["size_bytes"], FileUtils.natural_sort_key(node["name"]))
            elif self.sort_by == "type":
                return (is_dir_prefix, 0, node["extension"].lower(), FileUtils.natural_sort_key(node["name"]))
        except Exception: pass
        
        return (is_dir_prefix, 0, FileUtils.natural_sort_key(node["name"]))

    def scan_dir_generator(self, path: Path, query: str = "", max_peek_depth: int = 2, current_depth: int = 0) -> Generator[Union[FileNode, ScanStatus], None, None]:
        """Yields FileNode objects for a directory."""
        if not path.exists() or not path.is_dir():
            yield ScanStatus.IO_ERROR
            return

        try:
            raw_items = list(path.iterdir())
            processed_nodes = []
            
            for item in raw_items:
                if self.should_exclude(item): continue
                
                is_dir = item.is_dir()
                try:
                    stat = item.stat()
                    node: FileNode = {
                        "path": item,
                        "name": item.name,
                        "is_dir": is_dir,
                        "size_bytes": stat.st_size,
                        "modified_epoch": stat.st_mtime,
                        "extension": item.suffix if not is_dir else "",
                        "depth": current_depth,
                        "error": None
                    }
                except (PermissionError, OSError) as e:
                    node: FileNode = {
                        "path": item, "name": item.name, "is_dir": is_dir,
                        "size_bytes": 0, "modified_epoch": 0.0,
                        "extension": item.suffix if not is_dir else "",
                        "depth": current_depth, "error": str(e)
                    }
                
                if query:
                    q = query.lower()
                    if q in node["name"].lower(): processed_nodes.append(node)
                    elif node["is_dir"] and self.has_match_deep(item, q, 1, max_peek_depth):
                        processed_nodes.append(node)
                else: processed_nodes.append(node)

            processed_nodes.sort(key=self.get_sort_key)
            
            for node in processed_nodes:
                yield node
                
            yield ScanStatus.SUCCESS

        except PermissionError: yield ScanStatus.ACCESS_DENIED
        except Exception: yield ScanStatus.IO_ERROR

    def has_match_deep(self, path: Path, query: str, current_depth: int, max_depth: int) -> bool:
        """Recursive check for matches in subdirectories (peeking)."""
        if current_depth > max_depth: return False
        try:
            for item in path.iterdir():
                if self.should_exclude(item): continue
                if query in item.name.lower(): return True
                if item.is_dir() and self.has_match_deep(item, query, current_depth + 1, max_depth): return True
        except (PermissionError, OSError): pass
        return False

    def get_structure_lines(self, path=None, level=0):
        """Generates formatted strings for text-based views."""
        target_path = Path(path or self.root_path) if (path or self.root_path) else None
        if not target_path or (self.max_depth is not None and level > self.max_depth): return
        
        indent = ' ' * 4 * level
        yield f"{indent}{target_path.name}/"
        if self.max_depth is not None and level == self.max_depth: return

        for result in self.scan_dir_generator(target_path, current_depth=level):
            if isinstance(result, dict): # FileNode
                if result["is_dir"]:
                    yield from self.get_structure_lines(result["path"], level + 1)
                else:
                    yield f"{' ' * 4 * (level + 1)}{result['name']}"
            elif result in (ScanStatus.ACCESS_DENIED, ScanStatus.IO_ERROR):
                yield f"{indent}    [{result.name.replace('_', ' ').title()}]"

    def export_to_file(self, output_file="folder_contents.txt"):
        """Exports the current structure to a file."""
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                for line in self.get_structure_lines(): f.write(line + "\n")
            print(f"Exported to {output_file}")
        except Exception as e: print(f"Export failed: {e}")

    def run_cli(self):
        """Prints the structure to console."""
        for line in self.get_structure_lines(): print(line)

    @staticmethod
    def open_path(path: Union[Path, str]):
        """Platform-agnostic file opening."""
        p = str(path)
        system = platform.system()
        try:
            if system == "Windows":
                # Use os.startfile on Windows safely
                if hasattr(os, 'startfile'):
                    os.startfile(p)
                else:
                    subprocess.run(['explorer', p], check=False)
            elif system == "Darwin": subprocess.run(["open", p], check=True)
            else: subprocess.run(["xdg-open", p], check=True)
        except Exception as e: print(f"Failed to open '{p}': {e}")

class ThemeEngine:
    """Manages UI color palettes and styling."""
    DEFAULT_DARK = {
        "bg": "#11111b", "fg": "#f5f5f5", "accent": "#89b4fa",
        "tree_bg": "#11111b", "tree_fg": "#f5f5f5", "tree_sel_bg": "#313244",
        "tree_sel_fg": "#ffffff", "field_bg": "#181825", "field_fg": "#f5f5f5",
        "btn_bg": "#313244", "btn_fg": "#f5f5f5", "border": "#313244"
    }
    DEFAULT_LIGHT = {
        "bg": "#ffffff", "fg": "#11111b", "accent": "#0056b3",
        "tree_bg": "#ffffff", "tree_fg": "#11111b", "tree_sel_bg": "#e0e0e0",
        "tree_sel_fg": "#000000", "field_bg": "#f5f5f5", "field_fg": "#11111b",
        "btn_bg": "#e0e0e0", "btn_fg": "#11111b", "border": "#cccccc"
    }

    @staticmethod
    def apply(widget, palette):
        """Applies a color palette to ttk styles."""
        style = ttk.Style(widget)
        # Force clam theme for consistent cross-platform coloring (headers/borders)
        if platform.system() == "Windows" or platform.system() == "Darwin":
            if 'clam' in style.theme_names(): style.theme_use('clam')
            
        style.configure("Explorer.TFrame", background=palette["bg"])
        style.configure("Explorer.TLabel", background=palette["bg"], foreground=palette["fg"])
        style.configure("Explorer.TButton", background=palette["btn_bg"], foreground=palette["btn_fg"])
        style.map("Explorer.TButton", background=[('active', palette["accent"]), ('pressed', palette["accent"])])
        style.configure("Breadcrumb.TLabel", background=palette["bg"], foreground=palette["accent"], font=("Segoe UI", 9, "bold"))
        style.configure("Breadcrumb.TButton", background=palette["bg"], foreground=palette["fg"], borderwidth=0, relief="flat", font=("Segoe UI", 9))
        style.map("Breadcrumb.TButton", foreground=[('hover', palette["accent"])])
        style.configure("Explorer.TEntry", fieldbackground=palette["field_bg"], foreground=palette["field_fg"], insertcolor=palette["fg"])
        style.configure("Explorer.Treeview", background=palette["tree_bg"], foreground=palette["tree_fg"], fieldbackground=palette["tree_bg"], borderwidth=0)
        style.map("Explorer.Treeview", background=[('selected', palette["tree_sel_bg"])], foreground=[('selected', palette["tree_sel_fg"])])
        style.configure("Explorer.Treeview.Heading", background=palette["btn_bg"], foreground=palette["btn_fg"], relief="flat")

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
        for key, filename in icon_map.items():
            try:
                if os.path.exists(filename):
                    img = tk.PhotoImage(file=filename)
                    # Simple resize using subsample if too large (assuming original is ~256-512)
                    # We want ~16x16. If original is 512, subsample(32, 32).
                    # Since generate_image makes large ones, we'll try a generic subsample.
                    w, h = img.width(), img.height()
                    factor = max(1, w // 16)
                    self._icons[key] = img.subsample(x=factor, y=factor)
                else: self._icons[key] = ""
            except Exception: self._icons[key] = ""

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
        self.tree.column("#0", minwidth=150, width=250, stretch=True); self.tree.column("size", width=80, anchor='e'); self.tree.column("date", width=120, anchor='w')
        self.tree.pack(side='left', fill='both', expand=True)
        
        sb = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        sb.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=sb.set)
        
        # Accessibility Hardening: Ensure tags are used for consistent high-contrast text
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
        self.tree.delete(*self.tree.get_children())
        try:
            stat = self.root_path.stat()
            node = self.tree.insert("", "end", iid=str(self.root_path), text=str(self.root_path), 
                                   values=("<DIR>", FileUtils.format_time(stat.st_mtime)), open=True, image=self._icons.get("folder", ""))
            self.populate_node(node, self.root_path, sid=sid)
        except Exception: pass
        self._update_breadcrumbs()

    def get_selection(self) -> Optional[Path]:
        sel = self.tree.selection()
        if not sel: return None
        try: return Path(sel[0])
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
        # Update Treeview tags for immediate contrast change
        if hasattr(self, 'tree'):
            self.tree.tag_configure("item", foreground=palette["tree_fg"])
            self.tree.tag_configure("matching", foreground=palette["accent"])
        self._set_widget_styles(self, palette)

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
        self.tree.insert(node, "end", iid=f"{node}_scanning", text="[Scanning...]")
        filter_text = self.filter_var.get()
        threading.Thread(target=self._scan_worker, args=(node, path, level, sid, filter_text), daemon=True).start()

    def _scan_worker(self, node, path: Path, level, sid, filter_text):
        batch = []
        generator = self.inspector.scan_dir_generator(path, query=filter_text, max_peek_depth=self.max_peek_depth, current_depth=level)
        try:
            for result in generator:
                with self._state_lock:
                    if sid != self.current_scan_id: break
                if isinstance(result, dict):
                    sz = "[Error]" if result["error"] else ("<DIR>" if result["is_dir"] else FileUtils.format_size(result["size_bytes"]))
                    batch.append({"iid": str(result["path"]), "name": result["name"], 
                                 "values": (sz, FileUtils.format_time(result["modified_epoch"])), "is_dir": result["is_dir"], 
                                 "icon": self._get_icon_for_node(result)})
                    if len(batch) >= 40:
                        self.scan_queue.put(("items", node, batch, sid)); batch = []
                else:
                    if batch: self.scan_queue.put(("items", node, batch, sid))
                    self.scan_queue.put(("status", node, result, sid))
        finally: generator.close()

    def _process_queue_loop(self):
        start = datetime.datetime.now()
        try:
            while True:
                msg_type, node, data, sid = self.scan_queue.get_nowait()
                with self._state_lock:
                    if sid != self.current_scan_id: continue
                if msg_type == "items":
                    q = self.filter_var.get().lower()
                    for item in data:
                        if not self.tree.exists(item["iid"]):
                            tags = ("item",)
                            if q and q in item["name"].lower(): tags = ("matching",)
                            n = self.tree.insert(node, "end", iid=item["iid"], text=item["name"], 
                                               values=item["values"], open=bool(q), tags=tags, image=item["icon"])
                            if item["is_dir"] and not q: self.tree.insert(n, "end", text="dummy")
                elif msg_type == "status":
                    ph = f"{node}_scanning"
                    if self.tree.exists(ph):
                        if data == ScanStatus.SUCCESS: self.tree.delete(ph)
                        elif data == ScanStatus.ACCESS_DENIED: self.tree.item(ph, text="[Permission Denied]")
                        elif data == ScanStatus.IO_ERROR: self.tree.item(ph, text="[IO Error]")
                if (datetime.datetime.now() - start).total_seconds() > 0.045: break
        except queue.Empty: pass
        self.after(50, self._process_queue_loop)

    def on_expand(self, event):
        node = self.tree.focus(); children = self.tree.get_children(node)
        if len(children) == 1 and self.tree.item(children[0], "text") == "dummy":
            self.tree.delete(children[0])
            lvl = 0; curr = node
            while self.tree.parent(curr): lvl += 1; curr = self.tree.parent(curr)
            # node iid is the absolute path string
            self.populate_node(node, Path(node), level=lvl)

    def _internal_on_select(self, event):
        p = self.get_selection()
        if p:
            for cb in self._event_callbacks["select"]: cb(p)

    def _internal_on_double_click(self, event):
        p = self.get_selection()
        if p:
            if p.is_dir(): self.set_root(p)
            else:
                if self._event_callbacks["open"]:
                    for cb in self._event_callbacks["open"]: cb(p)
                else: DirectoryInspector.open_path(p)

    def apply_filter(self):
        if self.filter_after_id: self.after_cancel(self.filter_after_id)
        self.filter_after_id = self.after(500, self._perform_filter)
    def _perform_filter(self):
        self.filter_after_id = None
        if self.root_path: self.set_root(self.root_path)

    def apply_depth(self):
        try: self.inspector.max_depth = int(self.max_depth_var.get())
        except ValueError: self.inspector.max_depth = None
        if self.root_path: self.set_root(self.root_path)

    def on_sort_change(self, event):
        self.inspector.sort_by = self.cmb_sort.get()
        if self.root_path: self.set_root(self.root_path)

    def toggle_details(self):
        if self.show_details_var.get(): self.tree["displaycolumns"] = ("size", "date")
        else: self.tree["displaycolumns"] = ()

class InspectorApp:
    def __init__(self, root_path=None, inspector=None):
        self.root = tk.Tk(); self.root.title("SIL 2 Professional Explorer"); self.root.geometry("1100x750")
        self.root.configure(bg=ThemeEngine.DEFAULT_DARK["bg"])
        top = ttk.Frame(self.root, padding="10", style="Explorer.TFrame")
        top.pack(fill='x')
        ttk.Button(top, text="Select Folder", command=self.select_dir, style="Explorer.TButton").pack(side='left', padx=5)
        self.lbl_path = ttk.Label(top, text=str(root_path) if root_path else "---", style="Explorer.TLabel")
        self.lbl_path.pack(side='left', padx=15)
        self.is_dark = True
        ttk.Button(top, text="Toggle Theme", command=self.toggle_theme, style="Explorer.TButton").pack(side='right', padx=5)
        self.explorer = ExplorerComponent(self.root, root_path=root_path, inspector=inspector)
        self.explorer.bind_event("select", self.update_status)
        self.explorer.pack(fill='both', expand=True, padx=10, pady=5)
        self.lbl_status = ttk.Label(self.root, text="Ready", relief="sunken", anchor="w", padding=(5, 2), style="Explorer.TLabel")
        self.lbl_status.pack(side='bottom', fill='x')

    def toggle_theme(self):
        self.is_dark = not self.is_dark
        p = ThemeEngine.DEFAULT_DARK if self.is_dark else ThemeEngine.DEFAULT_LIGHT
        self.root.configure(bg=p["bg"]); self.explorer.set_theme(p)
        self.lbl_path.configure(foreground=p["accent"])
        self.lbl_status.configure(foreground=p["fg"])

    def select_dir(self):
        path = filedialog.askdirectory()
        if path: self.lbl_path.config(text=path); self.explorer.set_root(Path(path))

    def update_status(self, path):
        try:
            st = path.stat()
            sz = FileUtils.format_size(st.st_size) if path.is_file() else "[Dir]"
            self.lbl_status.config(text=f" {path.name}  |  {sz}  |  Updated: {FileUtils.format_time(st.st_mtime)}")
        except Exception: self.lbl_status.config(text="Metadata error")

    def run(self): self.root.mainloop()

def main():
    parser = argparse.ArgumentParser(description="Professional Directory Inspector")
    parser.add_argument("path", nargs="?", default=".", help="Directory to inspect")
    parser.add_argument("--gui", action="store_true"); parser.add_argument("--cli", action="store_true")
    parser.add_argument("--export", metavar="FILE"); parser.add_argument("--depth", type=int)
    parser.add_argument("--threshold", type=int, default=1000); parser.add_argument("--sort", choices=["name", "type", "size"], default="name")
    args = parser.parse_args(); path = Path(args.path).resolve()
    if not path.exists(): sys.exit(1)
    inspector = DirectoryInspector(path, max_depth=args.depth, item_count_threshold=args.threshold, sort_by=args.sort)
    if args.gui or (not args.cli and not args.export and ('DISPLAY' in os.environ or platform.system() == "Windows")):
        InspectorApp(path, inspector=inspector).run()
    elif args.export: inspector.export_to_file(args.export)
    else: inspector.run_cli()

if __name__ == "__main__": main()
