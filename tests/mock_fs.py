import os
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Iterator, Set
from dataclasses import dataclass

@dataclass
class MockStat:
    st_size: int = 0
    st_mtime: float = 0.0
    st_dev: int = 0
    st_ino: int = 0
    is_dir: bool = False

class MockFileSystem:
    """
    A simple virtual file system for testing DirectoryInspectorCore.
    Note: This is a standalone mock, not a global monkeypatch.
    Tests should use this to verify logic by mocking InspectorUtils calls.
    """
    def __init__(self):
        self.entries: Dict[str, MockStat] = {}
        self.children: Dict[str, List[str]] = {}
        self.unreadable_paths: Set[str] = set()
        self._next_ino = 1

    def add_dir(self, path: str, **kwargs):
        """Alias for add_directory"""
        self.add_directory(path, **kwargs)

    def add_directory(self, path: str, size: int = 0, mtime: float = 0.0, dev: int = 0, ino: Optional[int] = None):
        # Use resolve() for consistency with InspectorUtils
        p = str(Path(path).resolve())
        if ino is None:
            ino = self._next_ino
            self._next_ino += 1
        self.entries[p] = MockStat(st_size=size, st_mtime=mtime, st_dev=dev, st_ino=ino, is_dir=True)
        if p not in self.children:
            self.children[p] = []
        
        parent = str(Path(p).parent)
        if parent in self.children and p not in self.children[parent]:
            self.children[parent].append(p)

    def add_file(self, path: str, size: int = 100, mtime: float = 0.0, dev: int = 0, ino: Optional[int] = None):
        p = str(Path(path).resolve())
        if ino is None:
            ino = self._next_ino
            self._next_ino += 1
        self.entries[p] = MockStat(st_size=size, st_mtime=mtime, st_dev=dev, st_ino=ino, is_dir=False)
        
        parent = str(Path(p).parent)
        if parent in self.children and p not in self.children[parent]:
            self.children[parent].append(p)

    def set_unreadable(self, path: str):
        self.unreadable_paths.add(str(Path(path).resolve()))

    def get_stat(self, path: Path) -> Optional[MockStat]:
        p = str(path.resolve())
        return self.entries.get(p)

    def list_dir(self, path: Path) -> List[Path]:
        p = str(path.resolve())
        if p in self.unreadable_paths:
            raise PermissionError(f"Mock Access Denied: {p}")
        return [Path(c) for c in self.children.get(p, [])]

    # FileSystemProvider realization
    def exists(self, path: Path) -> bool:
        return str(path.resolve()) in self.entries

    def is_dir(self, path: Path) -> bool:
        stat = self.get_stat(path)
        return stat.is_dir if stat else False

    def iterdir(self, path: Path) -> Iterator[Path]:
        for p in self.list_dir(path):
            yield p

    def stat(self, path: Path) -> Any:
        # Note: stat usually works even if directory is unreadable (but not always)
        # For our tests, we want stat to work but iterdir to fail for Policy A.
        stat = self.get_stat(path)
        if not stat:
            raise FileNotFoundError(f"Mock path not found: {path}")
        return stat
