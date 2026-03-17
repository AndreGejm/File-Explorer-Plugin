import unittest
from pathlib import Path
from inspector_core import DirectoryInspectorCore
from inspector_types import ScanConfig
from inspector_validation import InspectorValidation

class TestInspectorCore(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("test_sandbox").resolve()
        self.test_dir.mkdir(exist_ok=True)
        (self.test_dir / "file2.txt").write_text("content")
        (self.test_dir / "file1.txt").write_text("content")
        (self.test_dir / "subfolder").mkdir(exist_ok=True)
        (self.test_dir / "subfolder" / "nested.txt").write_text("content")

    def tearDown(self):
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_deterministic_sorting(self):
        config: ScanConfig = {
            "root_path": str(self.test_dir),
            "max_depth": 1,
            "sort_by": "name",
            "excludes": []
        }
        inspector = DirectoryInspectorCore(config)
        results = inspector.scan()
        
        # Expecting: subfolder (is_dir=True), file1.txt, file2.txt
        names = [r["name"] for r in results if r["depth"] == 0]
        self.assertEqual(names, ["subfolder", "file1.txt", "file2.txt"])

        # Schema Validation
        for node in results:
            self.assertTrue(InspectorValidation.validate_file_node_json(node), f"Schema invalid for node: {node}")

    def test_max_depth(self):
        config: ScanConfig = {
            "root_path": str(self.test_dir),
            "max_depth": 0,
            "sort_by": "name",
            "excludes": []
        }
        inspector = DirectoryInspectorCore(config)
        results = inspector.scan()
        
        # depth 0 nodes only
        depths = [r["depth"] for r in results]
        self.assertTrue(all(d == 0 for d in depths))
        self.assertIn("subfolder", [r["name"] for r in results])
        self.assertNotIn("nested.txt", [r["name"] for r in results])

    def test_exclude_behavior(self):
        config: ScanConfig = {
            "root_path": str(self.test_dir),
            "max_depth": 2,
            "sort_by": "name",
            "excludes": ["subfolder"]
        }
        inspector = DirectoryInspectorCore(config)
        results = inspector.scan()
        
        names = [r["name"] for r in results]
        self.assertNotIn("subfolder", names)
        self.assertNotIn("nested.txt", names)

if __name__ == "__main__":
    unittest.main()
