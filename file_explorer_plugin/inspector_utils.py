import os
import re
from pathlib import Path
from typing import List, Union, Set, Optional, Any
from .inspector_types import NodeErrorCode, NodeErrorJSON

class InspectorUtils:
    """
    Pure utilities for the headless inspector.
    """

    @staticmethod
    def derive_error(e: Exception) -> 'NodeErrorJSON':
        """
        Derives a consistent NodeErrorJSON object from an exception.
        """
        code: NodeErrorCode = "IO_ERROR"
        if isinstance(e, PermissionError):
            code = "ACCESS_DENIED"
        elif isinstance(e, FileNotFoundError):
            code = "PATH_NOT_FOUND"
        elif isinstance(e, OSError):
            # General fallback for other OSErrors
            pass
        
        return {
            "code": code,
            "message": str(e)
        }


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

    @staticmethod
    def normalize_path(path: Union[str, Path]) -> Path:
        """
        Returns an absolute, resolved Path object.
        Ensures consistent behavior on Windows with long paths if necessary.
        """
        p = Path(path)
        try:
            return p.resolve()
        except (OSError, RuntimeError):
            # Fallback to absolute if resolve fails (e.g. symlink loop or invalid path)
            return p.absolute()

    @staticmethod
    def get_extension(path: Path) -> str:
        """
        Returns the lowercase extension (including dot).
        """
        return path.suffix.lower()

    @staticmethod
    def should_exclude(path: Path, excludes: Set[str]) -> bool:
        """
        Checks if a path should be excluded based on name or specific extensions.
        """
        if path.name in excludes:
            return True
        if path.suffix.lower() == '.pyc':
            return True
        return False

    @staticmethod
    def is_hidden(path: Path) -> bool:
        """
        Checks if a path is hidden (starts with . or has hidden attribute on Windows).
        """
        if path.name.startswith('.'):
            return True
        if os.name == 'nt':
            try:
                import ctypes
                attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
                # FILE_ATTRIBUTE_HIDDEN = 2
                return attrs != -1 and bool(attrs & 2)
            except (AttributeError, ImportError, OSError):
                return False
        return False
