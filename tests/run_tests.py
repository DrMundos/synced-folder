"""Simple test runner for synced-folder project."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
# Add tests directory to path
sys.path.insert(0, os.path.dirname(__file__))


def run_all_tests():
    """Run all test modules."""
    print("=" * 60)
    print("Running Synced Folder Tests")
    print("=" * 60)
    print()
    
    results = []
    
    # Test 1: Configuration
    print("Test 1: Configuration")
    print("-" * 60)
    try:
        import test_config
        results.append(test_config.test_config_imports())
    except Exception as e:
        print(f"[ERROR] Failed to run config tests: {e}")
        results.append(False)
    print()
    
    # Test 2: Server utilities
    print("Test 2: Server Utilities")
    print("-" * 60)
    try:
        import test_server_utils
        results.append(test_server_utils.test_sha256_of_file())
        results.append(test_server_utils.test_index_operations())
    except Exception as e:
        print(f"[ERROR] Failed to run server tests: {e}")
        results.append(False)
    print()
    
    # Test 3: Client utilities
    print("Test 3: Client Utilities")
    print("-" * 60)
    try:
        import test_client_utils
        results.append(test_client_utils.test_sha256_of_file())
        results.append(test_client_utils.test_state_operations())
    except Exception as e:
        print(f"[ERROR] Failed to run client tests: {e}")
        results.append(False)
    print()
    
    # Summary
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    
    if all(results):
        print("[SUCCESS] All tests passed!")
        return True
    else:
        print("[FAILURE] Some tests failed")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

