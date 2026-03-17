# File Explorer Plugin

A professional, highly-hardened directory explorer component for Tkinter applications. This plugin provides a robust Treeview-based interface with asynchronous scanning, theme support, and a wide range of file system operations via a built-in context menu.

## Features

- **Asynchronous Scanning**: Non-blocking directory population using background threads.
- **Dynamic Theme Support**: Easily switch between dark and light modes with full consistency.
- **Hardened Reliability**: Built-in protection against race conditions, IID collisions, and missing file system entries.
- **Rich Context Menu**: Open files, copy paths, rename, delete, and compress to ZIP directly from the UI.
- **Adaptive Layout**: Intelligent resizing that prioritizes the file/folder name column.

## How to Use as a Plugin

You can easily embed the `ExplorerComponent` into any Tkinter application.

### Basic Integration Example

```python
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from main import ExplorerComponent, ThemeEngine

def on_file_select(path):
    print(f"Selected: {path}")

def on_file_open(path):
    print(f"Opening: {path}")

root = tk.Tk()
root.title("My App with Explorer")
root.geometry("800x600")

# 1. Initialize the component
explorer = ExplorerComponent(root, root_path=Path("."))
explorer.pack(fill='both', expand=True, padx=10, pady=10)

# 2. Bind to events
explorer.bind_event("select", on_file_select)
explorer.bind_event("open", on_file_open)

# 3. (Optional) Set a theme
explorer.set_theme(ThemeEngine.DEFAULT_DARK)

root.mainloop()
```

### Component API

| Method | Description |
| :--- | :--- |
| `__init__(parent, root_path=None, inspector=None)` | Initializes the explorer. `root_path` sets the initial directory. |
| `set_root(path: Path)` | Changes the current root directory of the explorer. |
| `get_selection() -> Optional[Path]` | Returns the currently selected path in the Treeview. |
| `bind_event(event_type: str, callback: Callable[[Path], None])` | Binds a callback to `"select"` or `"open"` events. |
| `set_theme(palette: dict)` | Applies a theme palette (use `ThemeEngine.DEFAULT_DARK` or `DEFAULT_LIGHT`). |
| `refresh()` | Reloads the current directory structure. |

## Requirements

- Python 3.8+
- Tkinter (usually included with Python)
- `assets/` folder containing icons (`folder.png`, `file.png`, etc.) in the same directory as `main.py`.

## Directory Structure

- `main.py`: Entry point and `ExplorerComponent` definition.
- `assets/`: UI icons.
- `inspector_core.py`: Backend scanning engine.
- `inspector_utils.py`: File system and string utilities.
- `inspector_types.py`: Type definitions and models.
