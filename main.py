import sys
import argparse
import platform
import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog

# Import from our new package
from file_explorer_plugin import (
    ExplorerComponent, 
    ThemeEngine, 
    HeadlessInspectorAdapter, 
    DirectoryInspector,
    ScanStatus,
    FileUtils
)

class InspectorApp:
    """
    Demo Application for the File Explorer Plugin.
    """
    def __init__(self, root_path=None, inspector=None):
        self.root = tk.Tk()
        self.root.title("File Explorer Plugin - Demo")
        self.root.geometry("1100x750")
        
        # Initial Palette
        self.is_dark = True
        p = ThemeEngine.DEFAULT_DARK
        self.root.configure(bg=p["bg"])
        
        top = ttk.Frame(self.root, padding="10", style="Explorer.TFrame")
        top.pack(fill='x')
        
        ttk.Button(top, text="Select Folder", command=self.select_dir, style="Explorer.TButton").pack(side='left', padx=5)
        
        self.lbl_path = ttk.Label(top, text=str(root_path) if root_path else "---", style="Explorer.TLabel")
        self.lbl_path.pack(side='left', padx=15)
        
        ttk.Button(top, text="Toggle Theme", command=self.toggle_theme, style="Explorer.TButton").pack(side='right', padx=5)
        
        # The Plugin Component
        self.explorer = ExplorerComponent(self.root, root_path=root_path, inspector=inspector)
        self.explorer.bind_event("select", self.update_status)
        self.explorer.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.lbl_status = ttk.Label(self.root, text="Ready", relief="sunken", anchor="w", padding=(5, 2), style="Explorer.TLabel")
        self.lbl_status.pack(side='bottom', fill='x')
        
        # Apply initial theme
        self.explorer.set_theme(p)

    def toggle_theme(self):
        self.is_dark = not self.is_dark
        p = ThemeEngine.DEFAULT_DARK if self.is_dark else ThemeEngine.DEFAULT_LIGHT
        self.root.configure(bg=p["bg"])
        self.explorer.set_theme(p)
        self.lbl_path.configure(foreground=p["accent"] if not self.is_dark else p["fg"])
        self.lbl_status.configure(foreground=p["fg"])

    def select_dir(self):
        path = filedialog.askdirectory()
        if path:
            p = Path(path)
            self.lbl_path.config(text=str(p))
            self.explorer.set_root(p)

    def update_status(self, path):
        try:
            if not path.exists():
                self.lbl_status.config(text=" [Deleted or Moved] ")
                return
            st = path.stat()
            sz = FileUtils.format_size(st.st_size) if path.is_file() else "[Dir]"
            self.lbl_status.config(text=f" {path.name}  |  {sz}  |  Updated: {FileUtils.format_time(st.st_mtime)}")
        except Exception as e:
            self.lbl_status.config(text=f"Metadata error: {type(e).__name__}")

    def run(self):
        self.root.mainloop()

def main():
    parser = argparse.ArgumentParser(description="File Explorer Plugin Demo")
    parser.add_argument("path", nargs="?", default=".", help="Directory to inspect")
    parser.add_argument("--gui", action="store_true", help="Launch the GUI demo")
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode")
    parser.add_argument("--json", action="store_true", help="Output results as JSON to stdout")
    parser.add_argument("--depth", type=int, help="Maximum scan depth")
    parser.add_argument("--sort", choices=["name", "type", "size"], default="name", help="Sort order")
    parser.add_argument("--new-engine", action="store_true", help="Use the high-performance scanning engine")
    
    args = parser.parse_args()
    path = Path(args.path).resolve()
    
    if not path.exists():
        print(f"Error: Path does not exist: {path}")
        sys.exit(1)
    
    # Initialize appropriate inspector
    if args.new_engine:
        inspector = HeadlessInspectorAdapter(path, sort_by=args.sort, max_depth=args.depth)
    else:
        inspector = DirectoryInspector(path, max_depth=args.depth, sort_by=args.sort)
    
    # Execution Logic
    if args.gui or (not args.cli and not args.json and (platform.system() == "Windows" or 'DISPLAY' in os.environ)):
        app = InspectorApp(path, inspector=inspector)
        app.run()
    elif args.json:
        if hasattr(inspector, 'export_to_json'):
            inspector.export_to_json()
        else:
            print("Error: JSON export not supported by this engine.")
    elif args.cli:
        inspector.run_cli()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
