import os
import sys
from pathlib import Path
from typing import Optional, List, Generator, Tuple, Union, TypedDict, Callable
from enum import Enum, auto

# Mock or Import the required classes
# Since they are in the same dir, we can just import them
sys.path.append(os.getcwd())

from main import HeadlessInspectorAdapter, ScanStatus

def test_scan(target_path: str):
    path = Path(target_path).resolve()
    print(f"Testing scan of: {path}")
    
    adapter = HeadlessInspectorAdapter(path)
    generator = adapter.scan_dir_generator(path)
    
    count = 0
    errors = []
    for result in generator:
        if isinstance(result, dict):
            print(f"  Node: {result['name']} | IID: {result['path']} | is_dir: {result['is_dir']}")
            count += 1
        elif isinstance(result, ScanStatus):
            print(f"  Status: {result.name}")
        else:
            print(f"  Unknown result: {result}")
            
    print(f"Total nodes: {count}")

if __name__ == "__main__":
    test_scan(".")
