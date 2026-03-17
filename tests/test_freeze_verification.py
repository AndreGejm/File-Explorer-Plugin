from pathlib import Path
from inspector_core import DirectoryInspectorCore
from tests.mock_fs import MockFileSystem

def test_unreadable_descendant_policy_a():
    """
    POLICY A VERIFICATION:
    If a child directory is unreadable, it should be yielded EXACLTY ONCE 
    by its parent with the error populated, and recursion should stop.
    """
    mfs = MockFileSystem()
    mfs.add_dir("root")
    mfs.add_dir("root/readable")
    mfs.add_file("root/readable/file.txt", size=1024)
    mfs.add_dir("root/restricted")
    
    # Simulate unreadability
    mfs.set_unreadable("root/restricted")
    
    config = {
        "root_path": "root",
        "max_depth": 5,
        "sort_by": "name",
        "excludes": [],
        "exclude_hidden": False
    }
    
    inspector = DirectoryInspectorCore(config, mfs)
    results = inspector.scan()
    
    # Expected nodes: 'readable', 'readable/file.txt', 'restricted'
    # Total = 3
    assert len(results) == 3, f"Expected 3 nodes, got {len(results)}: {[n['name'] for n in results]}"
    
    # Find restricted node
    restricted = next((r for r in results if r["name"] == "restricted"), None)
    assert restricted is not None, "Could not find 'restricted' node"
    assert restricted["error"] is not None, "Restricted node should have error"
    assert restricted["error"]["code"] == "ACCESS_DENIED", f"Expected ACCESS_DENIED, got {restricted['error']['code']}"
    
    # Ensure no duplicate path for restricted
    paths = [r["path_absolute"] for r in results]
    assert len(paths) == len(set(paths)), f"Duplicates found in paths: {paths}"

def test_unreadable_root_emission():
    """
    VERIFY: If the root itself is unreadable, scan() returns exactly one 
    node representing the root with the error.
    """
    mfs = MockFileSystem()
    mfs.add_dir("restricted_root")
    mfs.set_unreadable("restricted_root")
    
    config = {
        "root_path": "restricted_root",
        "max_depth": 5,
        "sort_by": "name",
        "excludes": [],
        "exclude_hidden": False
    }
    
    inspector = DirectoryInspectorCore(config, mfs)
    results = inspector.scan()
    
    # Should yield exactly one node for the root itself
    assert len(results) == 1
    assert results[0]["name"] == "restricted_root"
    assert results[0]["error"] is not None
    assert results[0]["error"]["code"] == "ACCESS_DENIED"

def test_structured_error_contract():
    """
    VERIFY: Errors are dictionary objects with 'code' and 'message'.
    """
    mfs = MockFileSystem()
    mfs.add_dir("root")
    mfs.add_file("root/error.txt", size=1024)
    # Simulate file read/stat error (though core usually only catches it if it fails)
    # We'll just check a directory one since that's where we force the check in Policy A.
    mfs.add_dir("root/locked_dir")
    mfs.set_unreadable("root/locked_dir")
    
    config = {
        "root_path": "root",
        "max_depth": 1,
        "sort_by": "name",
        "excludes": [],
        "exclude_hidden": False
    }
    
    inspector = DirectoryInspectorCore(config, mfs)
    results = inspector.scan()
    
    locked_node = next(r for r in results if r["name"] == "locked_dir")
    err = locked_node["error"]
    assert isinstance(err, dict)
    assert "code" in err
    assert "message" in err
    assert err["code"] == "ACCESS_DENIED"
