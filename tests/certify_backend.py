import sys
import os
from pathlib import Path

# Fix PYTHONPATH
sys.path.append(os.getcwd())

from tests.test_freeze_verification import (
    test_unreadable_descendant_policy_a,
    test_unreadable_root_emission,
    test_structured_error_contract
)

def run_tests():
    print("Starting Freeze Certification Tests...")
    try:
        print("1. Testing Policy A (Unreadable descendant)...", end=" ")
        test_unreadable_descendant_policy_a()
        print("PASSED")
        
        print("2. Testing Unreadable Root Emission...", end=" ")
        test_unreadable_root_emission()
        print("PASSED")
        
        print("3. Testing Structured Error Contract...", end=" ")
        test_structured_error_contract()
        print("PASSED")
        
        print("\nALL BACKEND FREEZE TESTS PASSED")
        sys.exit(0)
    except AssertionError as e:
        print(f"FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
