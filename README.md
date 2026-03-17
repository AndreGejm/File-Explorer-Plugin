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
from pathlib import Path
from file_explorer_plugin import ExplorerComponent, ThemeEngine

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

## Headless Integration (JSON API)

For applications that want to use the scanning engine without the Tkinter UI (e.g., a Rust backend, a web service, or a CLI tool), the plugin provides a dedicated JSON output mode.

### Usage via CLI (Headless)

The scanning engine can be invoked directly as a module for machine-readable JSON output:

```bash
# Scan current directory and output JSON
python -m file_explorer_plugin.headless_inspector .

# Limit scan depth and sort by size
python -m file_explorer_plugin.headless_inspector /path/to/scan --max-depth 2 --sort-by size

# Exclude specific patterns
python -m file_explorer_plugin.headless_inspector . --exclude "__pycache__" --exclude ".git"
```

### Integration Pattern (e.g., Rust/Node.js)

1. **Spawn**: Call `python -m file_explorer_plugin.headless_inspector <path>` as a subprocess.
2. **Capture**: Read the content of `stdout`.
3. **Parse**: Deserialize the JSON string into your language's native data structures.

### JSON Schema

The output is a JSON array of objects, where each object represents a file or directory:

```json
[
  {
    "path_absolute": "C:\\Dev\\Project\\file.txt",
    "name": "file.txt",
    "is_dir": false,
    "size_bytes": 1024,
    "modified_epoch_s": 1710684000.0,
    "extension": ".txt",
    "depth": 0,
    "error": null
  },
  {
    "path_absolute": "C:\\Dev\\Project\\locked_folder",
    "name": "locked_folder",
    "is_dir": true,
    "size_bytes": 0,
    "modified_epoch_s": 1710684000.0,
    "extension": "",
    "depth": 0,
    "error": {
      "code": "ACCESS_DENIED",
      "message": "Permission denied"
    }
  }
]
```

| Field | Type | Description |
| :--- | :--- | :--- |
| `path_absolute` | `string` | Normalized absolute path to the item. |
| `name` | `string` | Name of the file or directory. |
| `is_dir` | `boolean` | `true` if it's a directory, `false` otherwise. |
| `size_bytes` | `integer` | Size in bytes. |
| `modified_epoch_s` | `float` | Last modified timestamp in Unix epoch seconds. |
| `extension` | `string` | File extension (empty for directories). |
| `depth` | `integer` | Depth relative to the scan root. |
| `error` | `object|null` | Structured error if the item was unreadable. |

## Requirements

- Python 3.8+
- Tkinter (usually included with Python)
- `assets/` folder containing icons (`folder.png`, `file.png`, etc.) in the same directory as `main.py`.

## Directory Structure

- `main.py`: Demo launcher for both GUI and CLI modes.
- `file_explorer_plugin/`: The official plugin package.
    - `__init__.py`: Public API (import `ExplorerComponent` here).
    - `explorer.py`: UI Component and adapters.
    - `headless_inspector.py`: **Stable JSON CLI entrypoint.**
    - `inspector_core.py`: Core scanning engine logic.
    - `themes.py`: Built-in dark/light theme engines.
- `assets/`: UI icons and images.
- `tests/`: Reliability and contract verification tests.
