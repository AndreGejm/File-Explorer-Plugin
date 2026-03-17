"""
File Explorer Plugin
A professional, highly-hardened directory explorer component for Tkinter.
"""

from .explorer import ExplorerComponent, HeadlessInspectorAdapter
from .themes import ThemeEngine
from .legacy_engine import DirectoryInspector
from .utils import ScanStatus, FileNode, FileUtils

__all__ = [
    'ExplorerComponent',
    'HeadlessInspectorAdapter',
    'ThemeEngine',
    'DirectoryInspector',
    'ScanStatus',
    'FileNode',
    'FileUtils'
]
