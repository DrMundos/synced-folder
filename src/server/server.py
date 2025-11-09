import os, json, hashlib, time, urllib.parse, logging, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import OperationalError
from prometheus_client import start_http_server, Counter, Histogram

# === Import global settings ===
from config.settings import POSTGRES, SERVER_PORT, METRICS_PORT

# === Prometheus metrics ===
UPLOADS = Counter("sync_uploads_total", "Total uploaded files")
DELETES = Counter("sync_deletes_total", "Total deleted files")
REQUESTS = Counter("sync_requests_total", "HTTP requests by method and endpoint", ["method", "endpoint"])
LATENCY = Histogram("sync_request_duration_seconds", "Request latency (s)", ["endpoint"])

# === Logger ===
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("SyncServer")

# === Paths ===
ROOT = os.path.abspath("storage")
INDEX_FILE = os.path.join(ROOT, ".index.json")

# === Database connection ===
def get_db(retries=10, delay=3):
    """Connect to PostgreSQL with retry logic."""
    for attempt in range(1, retries + 1):
        try:
            return psycopg2.connect(**POSTGRES)
        except OperationalError as e:
            log.warning(f"⏳ Waiting for DB ({attempt}/{retries}): {e}")
            time.sleep(delay)
    raise RuntimeError("❌ Could not connect to PostgreSQL after multiple attempts.")

def init_db():
    """Ensure the files_log table exists."""
    try:
        with get_db() as conn, conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS files_log (
                    id SERIAL PRIMARY KEY,
                    action VARCHAR(20),
                    path TEXT,
                    version INT,
                    sha TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
        log.info("✅ Database ready (table 'files_log' ensured).")
    except Exception as e:
        log.error(f"❌ DB init failed: {e}")

def log_to_db(action, path, version=None, sha=None):
    """Insert sync events into PostgreSQL."""
    try:
        with get_db() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO files_log (action, path, version, sha) VALUES (%s, %s, %s, %s)",
                (action, path, version, sha)
            )
    except Exception as e:
        log.error(f"DB log error: {e}")

# === File Utilities ===
def sha256_of_file(path):
    """Return SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def load_index():
    os.makedirs(ROOT, exist_ok=True)
    if not os.path.exists(INDEX_FILE):
        return {}
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_index(idx):
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(idx, f, indent=2, ensure_ascii=False)

def refresh_index(idx):
    """Rebuild or update the in-memory file index."""
    for dirpath, _, files in os.walk(ROOT):
        for fn in files:
            if fn == ".index.json":
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), ROOT).replace("\\", "/")
            fp = os.path.join(ROOT, rel)
            st = os.stat(fp)
            new_sha = sha256_of_file(fp)
            if rel not in idx or idx[rel]["sha"] != new_sha:
                idx[rel] = {"sha": new_sha, "mtime": st.st_mtime, "version": idx.get(rel, {}).get("version", 0) + 1}
    return idx

# === HTTP Handler ===
class Handler(BaseHTTPRequestHandler):
    def _send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _track(self, method, endpoint, start):
        REQUESTS.labels(method, endpoint).inc()
        LATENCY.labels(endpoint).observe(time.time() - start)

    def do_GET(self):
        start = time.time()
        try:
            if self.path.startswith("/index"):
                idx = refresh_index(load_index())
                save_index(idx)
                self._send_json({"index": idx, "ts": time.time()})
                log.info(f"📄 Sent index ({len(idx)} files)")
                self._track("GET", "/index", start)

            elif self.path.startswith("/download"):
                q = urllib.parse.urlparse(self.path).query
                path = urllib.parse.parse_qs(q).get("path", [""])[0]
                fp = os.path.join(ROOT, os.path.normpath(path).replace("\\", "/"))
                if not fp.startswith(ROOT) or not os.path.exists(fp):
                    self.send_error(404)
                    return
                with open(fp, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                log.info(f"⬇ Sent: {path} ({len(data)} bytes)")
                self._track("GET", "/download", start)

            elif self.path.startswith("/logs"):
                with get_db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT * FROM files_log ORDER BY timestamp DESC LIMIT 50;")
                    self._send_json({"logs": cur.fetchall()})
                self._track("GET", "/logs", start)

            else:
                self.send_error(404)
                self._track("GET", "unknown", start)

        except Exception as e:
            log.error(f"GET error: {e}")
            self.send_error(500)
            self._track("GET", "error", start)

    def do_POST(self):
        start = time.time()
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)

        try:
            if self.path == "/upload":
                meta_len = int(self.headers.get("X-Meta-Length", "0"))
                meta = json.loads(body[:meta_len].decode())
                data = body[meta_len:]
                rel = os.path.normpath(meta["path"]).replace("\\", "/")
                fp = os.path.join(ROOT, rel)
                os.makedirs(os.path.dirname(fp), exist_ok=True)

                idx = load_index()
                existing = idx.get(rel)
                # Conflict detection
                if existing and existing["sha"] != meta.get("base_sha"):
                    base, ext = os.path.splitext(rel)
                    conflict = f"{base} (conflict @{int(time.time())}){ext}"
                    with open(os.path.join(ROOT, conflict), "wb") as f:
                        f.write(data)
                    log.warning(f"⚠️ Conflict: saved as {conflict}")

                with open(fp, "wb") as f:
                    f.write(data)
                sha = hashlib.sha256(data).hexdigest()
                ver = (existing["version"] + 1) if existing else 1
                idx[rel] = {"sha": sha, "mtime": os.stat(fp).st_mtime, "version": ver}
                save_index(idx)
                log_to_db("upload", rel, ver, sha)
                UPLOADS.inc()
                log.info(f"⬆ Uploaded: {rel} (v{ver})")
                self._send_json({"ok": True, "version": ver, "sha": sha})
                self._track("POST", "/upload", start)

            elif self.path == "/delete":
                req = json.loads(body.decode())
                rel = os.path.normpath(req["path"]).replace("\\", "/")
                fp = os.path.join(ROOT, rel)
                idx = load_index()

                if os.path.exists(fp):
                    os.remove(fp)
                    log.info(f"🗑️ Deleted: {rel}")
                idx.pop(rel, None)
                save_index(idx)
                log_to_db("delete", rel)
                DELETES.inc()
                self._send_json({"ok": True})
                self._track("POST", "/delete", start)

            else:
                self.send_error(404)
                self._track("POST", "unknown", start)

        except Exception as e:
            log.error(f"POST error: {e}")
            self.send_error(500)
            self._track("POST", "error", start)

# === Entrypoint ===
def main():
    os.makedirs(ROOT, exist_ok=True)
    save_index(refresh_index(load_index()))
    init_db()

    threading.Thread(target=start_http_server, args=(METRICS_PORT,), daemon=True).start()
    log.info(f"📊 Prometheus metrics running at :{METRICS_PORT}/metrics")
    log.info(f"🚀 Sync Server started on port {SERVER_PORT}")

    try:
        HTTPServer(("0.0.0.0", SERVER_PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        log.info("🛑 Server stopped manually.")

if __name__ == "__main__":
    main()
