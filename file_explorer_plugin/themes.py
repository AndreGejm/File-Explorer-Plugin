import tkinter as tk
from tkinter import ttk

class ThemeEngine:
    """Centralized styling and theme management for the explorer."""
    
    DEFAULT_DARK = {
        "bg": "#1e1e1e", "fg": "#d4d4d4", "tree_bg": "#252526", "tree_fg": "#cccccc",
        "select_bg": "#37373d", "select_fg": "#ffffff", "accent": "#007acc", "match": "#4ec9b0",
        "btn_bg": "#333333", "btn_hover": "#444444", "status_bg": "#007acc", "border": "#333333"
    }
    
    DEFAULT_LIGHT = {
        "bg": "#ffffff", "fg": "#333333", "tree_bg": "#f3f3f3", "tree_fg": "#333333",
        "select_bg": "#007acc", "select_fg": "#ffffff", "accent": "#007acc", "match": "#d73a49",
        "btn_bg": "#eeeeee", "btn_hover": "#dddddd", "status_bg": "#007acc", "border": "#cccccc"
    }

    @staticmethod
    def apply(parent, palette: dict):
        """Applies a theme palette to the root/parent and its children."""
        style = ttk.Style(parent)
        style.theme_use("clam")
        
        style.configure("Explorer.TFrame", background=palette["bg"])
        style.configure("Explorer.TLabel", background=palette["bg"], foreground=palette["fg"], font=("Segoe UI", 9))
        style.configure("Explorer.Treeview", background=palette["tree_bg"], foreground=palette["tree_fg"], 
                        fieldbackground=palette["tree_bg"], borderwidth=0, font=("Segoe UI", 9))
        style.map("Explorer.Treeview", background=[('selected', palette["select_bg"])], 
                  foreground=[('selected', palette["select_fg"])])
        
        style.configure("Explorer.TButton", padding=5, background=palette["btn_bg"], foreground=palette["fg"])
        style.map("Explorer.TButton", background=[('active', palette["btn_hover"])])
        
        # Heading adjustments
        style.configure("Treeview.Heading", background=palette["btn_bg"], foreground=palette["fg"], font=("Segoe UI", 9, "bold"))
