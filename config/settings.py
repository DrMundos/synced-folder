import os
from dotenv import load_dotenv

# Load .env if it exists
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# === PostgreSQL Configuration ===
POSTGRES = {
    "host": os.getenv("POSTGRES_HOST", "postgres"),
    "dbname": os.getenv("POSTGRES_DB", "syncdb"),
    "user": os.getenv("POSTGRES_USER", "syncuser"),
    "password": os.getenv("POSTGRES_PASSWORD", "syncpass"),
}

# === Server Configuration ===
SERVER_HOST = os.getenv("SERVER_HOST", "server")
SERVER_PORT = int(os.getenv("SERVER_PORT", 8080))
METRICS_PORT = int(os.getenv("METRICS_PORT", 8000))
SERVER_URL = os.getenv("SERVER_URL", f"http://{SERVER_HOST}:{SERVER_PORT}")

# === Client Configuration ===
SYNC_DIR = os.getenv("SYNC_DIR", os.path.abspath("synced"))
STATE_FILE = os.path.join(SYNC_DIR, ".local_state.json")
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", 3))
