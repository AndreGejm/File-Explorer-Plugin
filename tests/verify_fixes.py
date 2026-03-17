import sys
import os
from pathlib import Path

# Fix PYTHONPATH
sys.path.append(os.getcwd())

from inspector_validation import InspectorValidation
from inspector_types import ScanConfig
from tests.mock_fs import MockFileSystem

def test_validate_file_node_json_regressions():
    print("Testing validate_file_node_json regressions...")
    
    # Valid node with structured error
    valid_node = {
        "path_absolute": str(Path("root/file.txt").resolve()),
        "name": "file.txt",
        "is_dir": False,
        "size_bytes": 100,
        "modified_epoch_s": 123456789.0,
        "extension": ".txt",
        "depth": 1,
        "error": {"code": "IO_ERROR", "message": "Disk failure"}
    }
    assert InspectorValidation.validate_file_node_json(valid_node) is True
    
    # Invalid node with string error (should be rejected now)
    invalid_node = valid_node.copy()
    invalid_node["error"] = "Internal error"
    assert InspectorValidation.validate_file_node_json(invalid_node) is False
    print("PASSED: validate_file_node_json correctly rejects string errors and accepts dict errors.")

def test_validate_inputs_regressions():
    print("Testing validate_inputs regressions...")
    
    mfs = MockFileSystem()
    root = Path("restricted_dir").resolve()
    mfs.add_directory(str(root))
    mfs.set_unreadable(str(root))
    
    config = {
        "root_path": str(root),
        "max_depth": 1,
        "sort_by": "name",
        "excludes": [],
        "exclude_hidden": False
    }
    
    is_valid, error_resp = InspectorValidation.validate_inputs(config, mfs)
    
    assert is_valid is False
    assert error_resp is not None
    assert isinstance(error_resp["message"], str), f"Expected string message, got {type(error_resp['message'])}"
    assert "Mock Access Denied" in error_resp["message"]
    print("PASSED: validate_inputs correctly returns a string message for ErrorResponse.")

if __name__ == "__main__":
    try:
        test_validate_file_node_json_regressions()
        test_validate_inputs_regressions()
        print("\nALL CONTRACT REGRESSION TESTS PASSED")
        sys.exit(0)
    except AssertionError as e:
        print(f"FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
