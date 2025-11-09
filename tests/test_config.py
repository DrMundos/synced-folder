"""Test configuration loading."""

import sys
import os

# Add src to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def test_config_imports():
    """Test that configuration can be imported."""
    try:
        from config.settings import (
            POSTGRES, SERVER_PORT, METRICS_PORT,
            SERVER_URL, SYNC_DIR, SCAN_INTERVAL
        )
        assert SERVER_PORT > 0, "SERVER_PORT must be positive"
        assert METRICS_PORT > 0, "METRICS_PORT must be positive"
        assert SERVER_URL.startswith("http"), "SERVER_URL must be valid"
        assert isinstance(SCAN_INTERVAL, int), "SCAN_INTERVAL must be integer"
        assert isinstance(POSTGRES, dict), "POSTGRES must be a dictionary"
        print("[OK] Configuration imports and validation successful")
        return True
    except Exception as e:
        print(f"[ERROR] Configuration test failed: {e}")
        return False


if __name__ == "__main__":
    success = test_config_imports()
    sys.exit(0 if success else 1)

