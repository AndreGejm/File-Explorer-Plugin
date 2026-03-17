from pathlib import Path
from typing import TypedDict, Optional, List, Literal, Iterator, Protocol, Any

class FileSystemProvider(Protocol):
    """Protocol for file system operations to enable dependency injection."""
    def exists(self, path: Path) -> bool: ...
    def is_dir(self, path: Path) -> bool: ...
    def iterdir(self, path: Path) -> Iterator[Path]: ...
    def stat(self, path: Path) -> Any: ...

class LocalFileSystemProvider:
    """Default provider using real OS calls."""
    def exists(self, path: Path) -> bool: return path.exists()
    def is_dir(self, path: Path) -> bool: return path.is_dir()
    def iterdir(self, path: Path) -> Iterator[Path]: return path.iterdir()
    def stat(self, path: Path) -> Any: return path.stat()


class FileNodeJSON(TypedDict):
    """
    Stateless transport contract for a single file system node.
    """
    path_absolute: str
    name: str
    is_dir: bool
    size_bytes: int
    modified_epoch_s: float
    extension: str
    depth: int
    error: Optional['NodeErrorJSON']

class NodeErrorJSON(TypedDict):
    """
    Structured error information for a specific node.
    """
    code: 'NodeErrorCode'
    message: str

NodeErrorCode = Literal["ACCESS_DENIED", "PATH_NOT_FOUND", "IO_ERROR", "SYMLINK_LOOP", "BUSY"]

class ErrorResponse(TypedDict):
    """
    Structured error response for the headless boundary.
    """
    status: Literal["error"]
    code: str
    message: str
    target_path: str

class ScanConfig(TypedDict):
    """
    Configuration for a scan operation.
    """
    root_path: str
    max_depth: Optional[int]
    sort_by: Literal["name", "size", "type"]
    excludes: List[str]
    exclude_hidden: bool

def validate_scan_config(config: ScanConfig) -> Optional[str]:
    """
    Basic validation for scan configuration.
    Returns an error message if invalid, else None.
    """
    depth = config.get("max_depth")
    if depth is not None:
        if not isinstance(depth, int):
            return "max_depth must be an integer"
        if depth < 0:
            return "max_depth must be non-negative"
    if config["sort_by"] not in ("name", "size", "type"):
        return f"Invalid sort_by: {config['sort_by']}"
    return None
