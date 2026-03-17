from pathlib import Path
from typing import List, Optional, Set, Iterator, Any
from .inspector_types import FileNodeJSON, ScanConfig, FileSystemProvider, LocalFileSystemProvider
from .inspector_utils import InspectorUtils

class DirectoryInspectorCore:
    """
    Headless scanning engine. Stateless and deterministic.
    """
    def __init__(self, config: ScanConfig, fs: Optional[FileSystemProvider] = None):
        self.root_path = InspectorUtils.normalize_path(config["root_path"])
        self.max_depth = config["max_depth"]
        self.sort_by = config["sort_by"]
        self.excludes = set(config["excludes"])
        self.exclude_hidden = config["exclude_hidden"]
        self.fs = fs or LocalFileSystemProvider()
        self._visited_indices: Set[tuple] = set()

    def scan(self) -> List[FileNodeJSON]:
        """
        Perform a full scan and return a materialized list of nodes.
        
        ROOT-NODE BEHAVIOR:
        1. Normally, this method only yields direct children of the root_path (depth 0+).
        2. The root_path itself is NOT included in the results if it is readable.
        3. If the root_path IS NOT readable, exactly one node representing the root is returned with the error populated.
        """
        if not self.fs.exists(self.root_path):
            raise ValueError(f"Root path does not exist: {self.root_path}")
        if not self.fs.is_dir(self.root_path):
            raise ValueError(f"Root path is not a directory: {self.root_path}")
        
        self._visited_indices = set()
        
        # Explicitly check root readability to avoid silent empty results or missing error node
        try:
            list(self.fs.iterdir(self.root_path))
        except (PermissionError, OSError) as e:
            # Policy: Yield a single error node for the root itself ONLY if unreadable
            stat = None
            try:
                stat = self.fs.stat(self.root_path)
            except (OSError, PermissionError):
                pass
            
            return [{
                "path_absolute": str(self.root_path.resolve()),
                "name": self.root_path.name,
                "is_dir": True,
                "size_bytes": int(stat.st_size) if stat and hasattr(stat, 'st_size') else 0,
                "modified_epoch_s": float(stat.st_mtime) if stat and hasattr(stat, 'st_mtime') else 0.0,
                "extension": "",
                "depth": 0,
                "error": InspectorUtils.derive_error(e)
            }]

        return list(self._iter_scan(self.root_path, current_depth=0))

    def _iter_scan(self, path: Path, current_depth: int) -> Iterator[FileNodeJSON]:
        """
        Recursive generator for directory traversal.
        Expects 'path' to be readable (handled by parent or scan()).
        Yields direct children of 'path'.
        """
        if self.max_depth is not None and current_depth > self.max_depth:
            return

        # Deterministic cycle detection (symlink loops)
        try:
            st = self.fs.stat(path)
            identity = (st.st_dev, st.st_ino)
            if identity in self._visited_indices:
                return # Skip cycle
            self._visited_indices.add(identity)
        except (OSError, PermissionError, AttributeError):
            pass

        try:
            raw_items = list(self.fs.iterdir(path))
        except (PermissionError, OSError):
            # Already checked by parent for descendants, 
            # and by scan() for root. If we hit this, just return.
            return

        nodes: List[FileNodeJSON] = []
        for item in raw_items:
            if InspectorUtils.should_exclude(item, self.excludes):
                continue
            if self.exclude_hidden and InspectorUtils.is_hidden(item):
                continue

            is_dir = self.fs.is_dir(item)
            stat = None
            error = None
            
            try:
                stat = self.fs.stat(item)
                # Policy A: Detect directory unreadability BEFORE yielding child node
                if is_dir:
                    try:
                        list(self.fs.iterdir(item))
                    except (PermissionError, OSError) as e:
                        error = InspectorUtils.derive_error(e)
            except (OSError, PermissionError) as e:
                error = InspectorUtils.derive_error(e)
            
            node: FileNodeJSON = {
                "path_absolute": str(item.resolve()),
                "name": item.name,
                "is_dir": is_dir,
                "size_bytes": int(stat.st_size) if stat and hasattr(stat, 'st_size') else 0,
                "modified_epoch_s": float(stat.st_mtime) if stat and hasattr(stat, 'st_mtime') else 0.0,
                "extension": InspectorUtils.get_extension(item) if not is_dir else "",
                "depth": current_depth,
                "error": error
            }
            nodes.append(node)

        # Apply deterministic sorting
        nodes.sort(key=self._get_sort_key)

        for node in nodes:
            yield node
            if node["is_dir"] and not node["error"]:
                # Recursive call
                yield from self._iter_scan(Path(node["path_absolute"]), current_depth + 1)

    def _get_sort_key(self, node: FileNodeJSON):
        """
        Stable sort key implementation.
        """
        try:
            # Folders first
            is_dir_prefix = 0 if node.get("is_dir", False) else 1
            name = node.get("name", "")
            
            if node.get("error"):
                return (is_dir_prefix, 2, InspectorUtils.natural_sort_key(name))

            if self.sort_by == "size":
                return (is_dir_prefix, 0, -node.get("size_bytes", 0), InspectorUtils.natural_sort_key(name))
            elif self.sort_by == "type":
                return (is_dir_prefix, 0, node.get("extension", "").lower(), InspectorUtils.natural_sort_key(name))
            
            # Default name sort
            return (is_dir_prefix, 0, InspectorUtils.natural_sort_key(name))
        except (KeyError, TypeError, AttributeError):
            # Safe fallback if node is malformed
            return (1, 3, node.get("name", ""))
