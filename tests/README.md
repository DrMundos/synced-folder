# Tests

Simple tests for the synced-folder project.

## Running Tests

Run all tests:

```bash
python tests/run_tests.py
```

Or run individual test files:

```bash
python tests/test_config.py
python tests/test_server_utils.py
python tests/test_client_utils.py
```

## Test Files

- `test_config.py` - Tests configuration loading and validation
- `test_server_utils.py` - Tests server utility functions (SHA256, index operations)
- `test_client_utils.py` - Tests client utility functions (SHA256, state operations)
- `run_tests.py` - Test runner that executes all tests

## Note

Some tests may be skipped if dependencies are not installed. Install dependencies with:

```bash
pip install -r requirements.txt
```

