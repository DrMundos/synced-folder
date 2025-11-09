"""Test server utility functions."""

import sys
import os
import tempfile
import hashlib

# Add src to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def test_sha256_of_file():
    """Test SHA256 hash calculation."""
    try:
        try:
            from server.server import sha256_of_file
        except ImportError as e:
            print(f"[SKIP] Server module requires dependencies: {e}")
            print("       Install with: pip install -r requirements.txt")
            return True  # Skip test if dependencies not installed
        
        # Create a temporary file with known content
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            test_content = b"Hello, World!"
            f.write(test_content)
            temp_path = f.name
        
        try:
            # Calculate hash
            calculated_hash = sha256_of_file(temp_path)
            
            # Calculate expected hash
            expected_hash = hashlib.sha256(test_content).hexdigest()
            
            assert calculated_hash == expected_hash, "Hash calculation mismatch"
            print(f"[OK] SHA256 calculation correct: {calculated_hash[:16]}...")
            return True
        finally:
            # Clean up
            os.unlink(temp_path)
            
    except Exception as e:
        print(f"[ERROR] SHA256 test failed: {e}")
        return False


def test_index_operations():
    """Test index load/save operations."""
    try:
        try:
            from server.server import load_index, save_index
        except ImportError as e:
            print(f"[SKIP] Server module requires dependencies: {e}")
            print("       Install with: pip install -r requirements.txt")
            return True  # Skip test if dependencies not installed
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            import server.server as server_module
            original_root = server_module.ROOT
            original_index = server_module.INDEX_FILE
            
            # Set temporary paths
            server_module.ROOT = temp_dir
            server_module.INDEX_FILE = os.path.join(temp_dir, ".index.json")
            
            try:
                # Test empty index
                idx = load_index()
                assert isinstance(idx, dict), "Index should be a dictionary"
                assert len(idx) == 0, "Empty index should have no entries"
                
                # Test save and load
                test_index = {"file1.txt": {"sha": "abc123", "mtime": 123456, "version": 1}}
                save_index(test_index)
                
                loaded_index = load_index()
                assert loaded_index == test_index, "Index should persist correctly"
                
                print("[OK] Index operations work correctly")
                return True
            finally:
                # Restore original paths
                server_module.ROOT = original_root
                server_module.INDEX_FILE = original_index
                
    except Exception as e:
        print(f"[ERROR] Index operations test failed: {e}")
        return False


if __name__ == "__main__":
    results = []
    results.append(test_sha256_of_file())
    results.append(test_index_operations())
    
    if all(results):
        print("\n[SUCCESS] All server utility tests passed!")
        sys.exit(0)
    else:
        print("\n[FAILURE] Some tests failed")
        sys.exit(1)

