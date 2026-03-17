import sys
import json
import argparse
from pathlib import Path
from typing import List
from .inspector_types import ScanConfig, ErrorResponse, FileNodeJSON, FileSystemProvider, LocalFileSystemProvider
from .inspector_validation import InspectorValidation
from .inspector_core import DirectoryInspectorCore

def run_headless():
    """
    Main entry point for the headless JSON CLI.
    """
    parser = argparse.ArgumentParser(description="Headless Directory Inspector")
    parser.add_argument("path", help="Directory to inspect")
    parser.add_argument("--max-depth", type=int, default=None, help="Maximum recursion depth")
    parser.add_argument("--sort-by", choices=["name", "size", "type"], default="name", help="Sort order")
    parser.add_argument("--exclude", action="append", help="Names to exclude")
    
    args = parser.parse_args()
    
    config: ScanConfig = {
        "root_path": args.path,
        "max_depth": args.max_depth,
        "sort_by": args.sort_by,
        "excludes": args.exclude if args.exclude else ["__pycache__", ".git", ".venv", "node_modules"],
        "exclude_hidden": False
    }

    # 0. FS Provider
    fs = LocalFileSystemProvider()

    # 1. Validate
    is_valid, error = InspectorValidation.validate_inputs(config, fs)
    if not is_valid and error:
        print(json.dumps(error))
        sys.exit(1)

    # 2. Scan
    try:
        inspector = DirectoryInspectorCore(config, fs)
        results: List[FileNodeJSON] = inspector.scan()
        
        # 3. Output JSON
        print(json.dumps(results))
        sys.exit(0)
        
    except ValueError as e:
        # Semantic mapping for config/path errors raised by scan()
        print(json.dumps({
            "status": "error",
            "code": "INVALID_CONFIG",
            "message": str(e),
            "target_path": args.path
        }))
        sys.exit(1)
    except (OSError, PermissionError) as e:
        # Runtime I/O issues during scan
        print(json.dumps({
            "status": "error",
            "code": "IO_ERROR",
            "message": f"I/O error during scan: {str(e)}",
            "target_path": args.path
        }))
        sys.exit(1)
    except Exception as e:
        # Logic errors or unhandled system failures
        print(json.dumps({
            "status": "error",
            "code": "INTERNAL_ERROR",
            "message": f"Unexpected error during scan: {str(e)}",
            "target_path": args.path
        }))
        sys.exit(1)

if __name__ == "__main__":
    run_headless()
