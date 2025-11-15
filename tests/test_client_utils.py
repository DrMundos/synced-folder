"""Test client utility functions."""

import sys
import os
import tempfile
import hashlib

# Add src to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def test_sha256_of_file():
    """Test SHA256 hash calculation in client."""
    try:
        from client.client import sha256_of_file
        
        # Create a temporary file with known content
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            test_content = b"Test file content for client"
            f.write(test_content)
            temp_path = f.name
        
        try:
            # Calculate hash
            calculated_hash = sha256_of_file(temp_path)
            
            # Calculate expected hash
            expected_hash = hashlib.sha256(test_content).hexdigest()
            
            assert calculated_hash == expected_hash, "Hash calculation mismatch"
            print(f"[OK] Client SHA256 calculation correct: {calculated_hash[:16]}...")
            return True
        finally:
            # Clean up
            os.unlink(temp_path)
            
    except Exception as e:
        print(f"[ERROR] Client SHA256 test failed: {e}")
        return False


def test_state_operations():
    """Test state load/save operations."""
    try:
        from client.client import load_state, save_state
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            import client.client as client_module
            original_state = client_module.STATE_FILE
            
            # Set temporary state file
            client_module.STATE_FILE = os.path.join(temp_dir, ".local_state.json")
            
            try:
                # Test empty state
                state = load_state()
                assert isinstance(state, dict), "State should be a dictionary"
                assert "files" in state, "State should have 'files' key"
                
                # Test save and load
                test_files = ["file1.txt", "file2.txt", "file3.txt"]
                save_state(test_files)
                
                loaded_state = load_state()
                assert "files" in loaded_state, "Loaded state should have 'files' key"
                assert len(loaded_state["files"]) == len(test_files), "File count should match"
                
                print("[OK] State operations work correctly")
                return True
            finally:
                # Restore original state file
                client_module.STATE_FILE = original_state
                
    except Exception as e:
        print(f"[ERROR] State operations test failed: {e}")
        return False


if __name__ == "__main__":
    results = []
    results.append(test_sha256_of_file())
    results.append(test_state_operations())
    
    if all(results):
        print("\n[SUCCESS] All client utility tests passed!")
        sys.exit(0)
    else:
        print("\n[FAILURE] Some tests failed")
        sys.exit(1)

