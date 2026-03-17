import unittest
from pathlib import Path
from inspector_core import DirectoryInspectorCore
from inspector_types import ScanConfig
from tests.mock_fs import MockFileSystem

class TestCoreWithMock(unittest.TestCase):
    def setUp(self):
        self.mock_fs = MockFileSystem()
        self.config: ScanConfig = {
            "root_path": "C:/mock_root",
            "max_depth": 5,
            "sort_by": "name",
            "excludes": [],
            "exclude_hidden": False
        }

    def test_cycle_detection(self):
        # Setup: A -> B -> A (cycle)
        root = "C:/mock_root"
        dir_a = "C:/mock_root/A"
        dir_b = "C:/mock_root/A/B"
        
        self.mock_fs.add_directory(root, dev=1, ino=1)
        self.mock_fs.add_directory(dir_a, dev=1, ino=2)
        self.mock_fs.add_directory(dir_b, dev=1, ino=2) # SAME AS A (Cycle)
        
        # We inject the mock_fs directly
        inspector = DirectoryInspectorCore(self.config, fs=self.mock_fs)
        results = inspector.scan()
        
        # Should have: A and B, but B's children (A again) should be skipped
        names = [r["name"] for r in results]
        self.assertEqual(len(names), 2)
        self.assertIn("A", names)
        self.assertIn("B", names)
        # Verify B has error or is just skipped. 
        # In our current impl, we return from _iter_scan if cycle detected.

    def test_exclude_hidden(self):
        root = "C:/mock_root"
        hidden_file = "C:/mock_root/.hidden"
        visible_file = "C:/mock_root/visible.txt"
        
        self.mock_fs.add_directory(root)
        self.mock_fs.add_file(hidden_file)
        self.mock_fs.add_file(visible_file)
        
        # Test with exclude_hidden = True
        self.config["exclude_hidden"] = True
        inspector = DirectoryInspectorCore(self.config, fs=self.mock_fs)
        results = inspector.scan()
        
        names = [r["name"] for r in results]
        self.assertEqual(names, ["visible.txt"])
        self.assertNotIn(".hidden", names)

if __name__ == "__main__":
    unittest.main()
