import os, json, hashlib, time, urllib.parse, logging, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import OperationalError
from prometheus_client import start_http_server, Counter, Histogram

# === Prometheus Metrics ===
UPLOAD_COUNTER = Counter("sync_uploads_total", "Total number of uploaded files")
DELETE_COUNTER = Counter("sync_deletes_total", "Total number of deleted files")
REQUEST_COUNTER = Counter("sync_requests_total", "Total HTTP requests by method and endpoint", ["method", "endpoint"])
REQUEST_LATENCY = Histogram("sync_request_duration_seconds", "Request latency in seconds", ["endpoint"])

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

# === DB Config ===
DB_HOST = os.getenv("POSTGRES_HOST", os.getenv("DB_HOST", "postgres"))
DB_USER = os.getenv("POSTGRES_USER", os.getenv("DB_USER", "syncuser"))
DB_PASS = os.getenv("POSTGRES_PASSWORD", os.getenv("DB_PASS", "syncpass"))
DB_NAME = os.getenv("POSTGRES_DB", os.getenv("DB_NAME", "syncdb"))

# === DB Connection with Retry ===
def get_db_connection(retries=10, delay=3):
    for attempt in range(1, retries + 1):
        try:
            return psycopg2.connect(
                host=DB_HOST,
                user=DB_USER,
                password=DB_PASS,
                dbname=DB_NAME
            )
        except OperationalError as e:
            log.warning(f"⏳ Waiting for DB (attempt {attempt}/{retries}): {e}")
            time.sleep(delay)
    raise RuntimeError("❌ Could not connect to PostgreSQL after multiple attempts.")

def init_db():
    """Ensure files_log table exists."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
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
        conn.commit()
        cur.close()
        conn.close()
        log.info("✅ Database ready (table 'files_log' ensured).")
    except Exception as e:
        log.error(f"❌ Failed to init database: {e}")

def log_to_db(action, path, version=None, sha=None):
    """Insert upload/delete events into PostgreSQL."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO files_log (action, path, version, sha) VALUES (%s, %s, %s, %s)",
            (action, path, version, sha)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        log.error(f"DB error: {e}")

# === File Utilities ===
def sha256_of_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def load_index():
    if not os.path.exists(ROOT):
        os.makedirs(ROOT, exist_ok=True)
        log.info("📁 Created storage folder.")
    if not os.path.exists(INDEX_FILE):
        return {}
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_index(idx):
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)

def refresh_index_from_disk(idx):
    for dirpath, _, files in os.walk(ROOT):
        for fn in files:
            if fn == ".index.json":
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), ROOT).replace("\\", "/")
            fp = os.path.join(ROOT, rel)
            st = os.stat(fp)
            if rel not in idx:
                idx[rel] = {"sha": sha256_of_file(fp), "mtime": st.st_mtime, "version": 1}
            else:
                new_sha = sha256_of_file(fp)
                if new_sha != idx[rel]["sha"]:
                    idx[rel]["sha"] = new_sha
                    idx[rel]["mtime"] = st.st_mtime
    return idx

# === HTTP Handler ===
class Handler(BaseHTTPRequestHandler):
    def _send_json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, format, *args):
        log.info("%s - %s" % (self.address_string(), format % args))

    def _track_request(self, method, endpoint, start_time):
        REQUEST_COUNTER.labels(method=method, endpoint=endpoint).inc()
        REQUEST_LATENCY.labels(endpoint=endpoint).observe(time.time() - start_time)

    def do_GET(self):
        start = time.time()
        if self.path.startswith("/index"):
            idx = refresh_index_from_disk(load_index())
            save_index(idx)
            log.info(f"Client requested index ({len(idx)} files)")
            self._send_json({"index": idx, "ts": time.time()})
            self._track_request("GET", "/index", start)

        elif self.path.startswith("/download"):
            q = urllib.parse.urlparse(self.path).query
            path = urllib.parse.parse_qs(q).get("path", [""])[0]
            safe = os.path.normpath(path).replace("\\", "/")
            fp = os.path.join(ROOT, safe)
            if not fp.startswith(ROOT) or not os.path.exists(fp):
                log.warning(f"Client requested missing file: {path}")
                self.send_error(404)
                return
            with open(fp, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            log.info(f"Sent file: {path} ({len(data)} bytes)")
            self._track_request("GET", "/download", start)

        elif self.path.startswith("/logs"):
            try:
                conn = get_db_connection()
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute("SELECT * FROM files_log ORDER BY timestamp DESC LIMIT 50;")
                rows = cur.fetchall()
                cur.close()
                conn.close()
                self._send_json({"logs": rows})
            except Exception as e:
                log.error(f"Failed to fetch logs: {e}")
                self._send_json({"error": str(e)}, code=500)
            self._track_request("GET", "/logs", start)

        else:
            self.send_error(404)
            log.warning(f"Unknown GET path: {self.path}")
            self._track_request("GET", "unknown", start)

    def do_POST(self):
        start = time.time()
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)

        if self.path == "/upload":
            meta_len = int(self.headers.get("X-Meta-Length", "0"))
            meta = json.loads(body[:meta_len].decode("utf-8"))
            data = body[meta_len:]
            rel = os.path.normpath(meta["path"]).replace("\\", "/")
            fp = os.path.join(ROOT, rel)
            os.makedirs(os.path.dirname(fp), exist_ok=True)

            idx = load_index()
            server_rec = idx.get(rel)

            if server_rec and server_rec["sha"] != meta.get("base_sha") and meta.get("base_sha"):
                base, ext = os.path.splitext(rel)
                conflict_rel = f"{base} (conflict @{int(time.time())}){ext}"
                with open(os.path.join(ROOT, conflict_rel), "wb") as f:
                    f.write(data)
                log.warning(f"⚠️ Conflict detected: saved copy as '{conflict_rel}'")

            with open(fp, "wb") as f:
                f.write(data)
            sha = hashlib.sha256(data).hexdigest()
            st = os.stat(fp)
            ver = (server_rec["version"] + 1) if server_rec else 1
            idx[rel] = {"sha": sha, "mtime": st.st_mtime, "version": ver}
            save_index(idx)
            log_to_db("upload", rel, ver, sha)
            UPLOAD_COUNTER.inc()
            log.info(f"⬆ Uploaded: {rel} (version {ver})")
            self._send_json({"ok": True, "version": ver, "sha": sha})
            self._track_request("POST", "/upload", start)

        elif self.path == "/delete":
            req = json.loads(body.decode("utf-8"))
            rel = os.path.normpath(req["path"]).replace("\\", "/")
            fp = os.path.join(ROOT, rel)
            idx = load_index()

            if os.path.exists(fp):
                os.remove(fp)
                log.info(f"🗑️ Deleted: {rel}")
            if rel in idx:
                del idx[rel]
                save_index(idx)
            log_to_db("delete", rel)
            DELETE_COUNTER.inc()
            self._send_json({"ok": True})
            self._track_request("POST", "/delete", start)

        else:
            self.send_error(404)
            log.warning(f"Unknown POST path: {self.path}")
            self._track_request("POST", "unknown", start)

# === Entrypoint ===
def main():
    os.makedirs(ROOT, exist_ok=True)
    save_index(refresh_index_from_disk(load_index()))
    init_db()

    # Prometheus runs on 8000 in background
    threading.Thread(target=start_http_server, args=(8000,), daemon=True).start()
    log.info("📊 Prometheus metrics available on port 8000 (/metrics)")

    log.info("🚀 Server started on port 8080 – waiting for clients...")
    try:
        HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
    except KeyboardInterrupt:
        log.info("🛑 Server stopped manually (Ctrl+C).")

if __name__ == "__main__":
    main()
