import sys
from pathlib import Path
from typing import Optional, Generator, Union
from .utils import FileNode, ScanStatus, FileUtils
from .inspector_utils import InspectorUtils

class DirectoryInspector:
    """
    Legacy core logic for directory scanning, filtering, and sorting.
    (Kept for compatibility or simpler use cases).
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
        return InspectorUtils.should_exclude(path, self.excludes)

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
