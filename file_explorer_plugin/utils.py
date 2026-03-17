import math
import datetime
from pathlib import Path
from typing import List, Union, Optional, TypedDict
from enum import Enum, auto
from .inspector_utils import InspectorUtils

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
        return InspectorUtils.natural_sort_key(s)
