import unittest
import subprocess
import json
import sys
from pathlib import Path

class TestHeadlessCLI(unittest.TestCase):
    def setUp(self):
        self.script_path = str(Path("headless_inspector.py").resolve())
        self.test_dir = Path("test_cli_sandbox").resolve()
        self.test_dir.mkdir(exist_ok=True)
        (self.test_dir / "alpha.txt").write_text("a")

    def tearDown(self):
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_cli_success_json(self):
        cmd = [sys.executable, self.script_path, str(self.test_dir)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "alpha.txt")

    def test_cli_invalid_path_json(self):
        cmd = [sys.executable, self.script_path, "non_existent_path_12345"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 1)
        data = json.loads(result.stdout)
        self.assertEqual(data["status"], "error")
        self.assertEqual(data["error_code"], "PATH_NOT_FOUND")

    def test_cli_invalid_depth_json(self):
        cmd = [sys.executable, self.script_path, str(self.test_dir), "--max-depth", "-5"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 1)
        data = json.loads(result.stdout)
        self.assertEqual(data["status"], "error")
        self.assertEqual(data["error_code"], "INVALID_INPUT")

if __name__ == "__main__":
    unittest.main()
