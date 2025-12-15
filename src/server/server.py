import os, json, hashlib, time, urllib.parse, logging, threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import OperationalError

from prometheus_client import start_http_server, Counter, Histogram
from config.settings import POSTGRES, SERVER_PORT, METRICS_PORT


# ==============================
# Logging
# ==============================
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("SyncServer")


# ==============================
# Metrics
# ==============================
UPLOADS   = Counter("sync_uploads_total", "Total uploaded files")
DELETES   = Counter("sync_deletes_total", "Total deleted files")
CONFLICTS = Counter("sync_conflicts_total", "Total file conflicts")
REQUESTS  = Counter("sync_requests_total", "HTTP requests", ["method", "endpoint"])
LATENCY   = Histogram("sync_request_duration_seconds", "Request latency", ["endpoint"])


# ==============================
# Paths
# ==============================
ROOT = os.path.abspath("storage")
INDEX_FILE = os.path.join(ROOT, ".index.json")


# ==============================
# DB helpers
# ==============================
def get_db(retries=10, delay=3):
    for _ in range(retries):
        try:
            return psycopg2.connect(**POSTGRES)
        except OperationalError:
            time.sleep(delay)
    raise RuntimeError("PostgreSQL unavailable")


def init_db():
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
    log.info("Database ready")


def log_event(action, path, version=None, sha=None):
    with get_db() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO files_log (action, path, version, sha) VALUES (%s, %s, %s, %s)",
            (action, path, version, sha)
        )


def conflict_already_logged(path, sha):
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT 1 FROM files_log
            WHERE action='conflict' AND path=%s AND sha=%s
            LIMIT 1
        """, (path, sha))
        return cur.fetchone() is not None


# ==============================
# Index helpers
# ==============================
def load_index():
    if not os.path.exists(INDEX_FILE):
        return {}
    with open(INDEX_FILE) as f:
        return json.load(f)


def save_index(idx):
    with open(INDEX_FILE, "w") as f:
        json.dump(idx, f, indent=2)


# ==============================
# Utilities
# ==============================
def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_path(rel_path: str) -> str:
    rel = os.path.normpath(rel_path).replace("\\", "/")
    return os.path.join(ROOT, rel)


# ==============================
# HTTP Handler
# ==============================
class Handler(BaseHTTPRequestHandler):

    def json_response(self, payload, code=200):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def track(self, method, endpoint, start):
        REQUESTS.labels(method, endpoint).inc()
        LATENCY.labels(endpoint).observe(time.time() - start)

    # -------- GET --------
    def do_GET(self):
        start = time.time()
        try:
            if self.path.startswith("/index"):
                idx = load_index()
                self.json_response({"index": idx, "ts": time.time()})
                self.track("GET", "/index", start)

            elif self.path.startswith("/download"):
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                path = qs.get("path", [""])[0]
                fp = safe_path(path)

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

                self.track("GET", "/download", start)

            elif self.path.startswith("/logs"):
                with get_db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        "SELECT * FROM files_log ORDER BY timestamp DESC LIMIT 50"
                    )
                    self.json_response({"logs": cur.fetchall()})
                self.track("GET", "/logs", start)

            else:
                self.send_error(404)

        except Exception as e:
            log.error(f"GET error: {e}")
            self.send_error(500)
        finally:
            self.track("GET", "done", start)

    # -------- POST --------
    def do_POST(self):
        start = time.time()
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)

            if self.path == "/upload":
                meta_len = int(self.headers.get("X-Meta-Length", 0))
                meta = json.loads(body[:meta_len])
                data = body[meta_len:]

                rel = os.path.normpath(meta["path"]).replace("\\", "/")
                fp = safe_path(rel)
                os.makedirs(os.path.dirname(fp), exist_ok=True)

                idx = load_index()
                existing = idx.get(rel)
                sha = sha256_bytes(data)

                if existing and existing["sha"] == sha:
                    self.json_response({"ok": True, "skipped": True})
                    return

                if existing and existing["sha"] != sha:
                    if conflict_already_logged(rel, sha):
                        self.json_response(
                            {"ok": False, "conflict": True, "reason": "already_reported"},
                            code=409
                        )
                        return

                    base, ext = os.path.splitext(rel)
                    conflict_name = f"{base} (conflict @{int(time.time())}){ext}"
                    with open(safe_path(conflict_name), "wb") as f:
                        f.write(data)

                    log_event("conflict", rel, existing["version"], sha)
                    CONFLICTS.inc()

                    self.json_response(
                        {"ok": False, "conflict": True, "file": conflict_name},
                        code=409
                    )
                    return

                with open(fp, "wb") as f:
                    f.write(data)

                version = existing["version"] + 1 if existing else 1
                idx[rel] = {
                    "sha": sha,
                    "mtime": os.stat(fp).st_mtime,
                    "version": version
                }
                save_index(idx)

                log_event("upload", rel, version, sha)
                UPLOADS.inc()

                self.json_response({"ok": True, "version": version})

            elif self.path == "/delete":
                req = json.loads(body)
                rel = os.path.normpath(req["path"]).replace("\\", "/")
                fp = safe_path(rel)

                if os.path.exists(fp):
                    os.remove(fp)

                idx = load_index()
                idx.pop(rel, None)
                save_index(idx)

                log_event("delete", rel)
                DELETES.inc()

                self.json_response({"ok": True})

            else:
                self.send_error(404)

        except Exception as e:
            log.error(f"POST error: {e}")
            self.send_error(500)
        finally:
            self.track("POST", self.path, start)


# ==============================
# Main
# ==============================
def main():
    os.makedirs(ROOT, exist_ok=True)
    save_index(load_index())
    init_db()

    threading.Thread(
        target=start_http_server,
        args=(METRICS_PORT,),
        daemon=True
    ).start()

    log.info(f"Server running on port {SERVER_PORT}")
    HTTPServer(("0.0.0.0", SERVER_PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
