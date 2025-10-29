import os, json, hashlib, time, urllib.parse, logging
from http.server import HTTPServer, BaseHTTPRequestHandler

# === Logger Setup ===
logging.basicConfig(
    level=logging.INFO,  # אפשר לשנות ל DEBUG אם רוצים פירוט מלא
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger("SyncServer")

ROOT = os.path.abspath("storage")
INDEX_FILE = os.path.join(ROOT, ".index.json")

def sha256_of_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

def load_index():
    if not os.path.exists(ROOT):
        os.makedirs(ROOT, exist_ok=True)
        log.info("Created storage folder.")
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
            if fn == ".index.json": continue
            rel = os.path.relpath(os.path.join(dirpath, fn), ROOT).replace("\\", "/")
            fp = os.path.join(ROOT, rel)
            st = os.stat(fp)
            if rel not in idx:
                idx[rel] = {"sha": sha256_of_file(fp), "mtime": st.st_mtime, "version": 1}
    return idx

class Handler(BaseHTTPRequestHandler):
    def _send_json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, format, *args):
        # משתיק את הלוגים הרגילים של HTTPServer ומעביר אותם ללוג שלנו
        log.info("%s - %s" % (self.address_string(), format % args))

    def do_GET(self):
        if self.path.startswith("/index"):
            idx = refresh_index_from_disk(load_index())
            save_index(idx)
            log.info("Client requested index (%d files)" % len(idx))
            self._send_json({"index": idx, "ts": time.time()})

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

        else:
            log.warning(f"Unknown GET path: {self.path}")
            self.send_error(404)

    def do_POST(self):
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

            # קונפליקט
            if server_rec and server_rec["sha"] != meta.get("base_sha") and meta.get("base_sha"):
                base, ext = os.path.splitext(rel)
                conflict_rel = f'{base} (conflict @{int(time.time())}){ext}'
                with open(os.path.join(ROOT, conflict_rel), "wb") as f:
                    f.write(data)
                log.warning(f"Conflict detected: saved copy {conflict_rel}")

            with open(fp, "wb") as f:
                f.write(data)
            sha = hashlib.sha256(data).hexdigest()
            st = os.stat(fp)
            ver = (server_rec["version"] + 1) if server_rec else 1
            idx[rel] = {"sha": sha, "mtime": st.st_mtime, "version": ver}
            save_index(idx)
            log.info(f"File uploaded: {rel} (version {ver})")
            self._send_json({"ok": True, "version": ver, "sha": sha})

        elif self.path == "/delete":
            req = json.loads(body.decode("utf-8"))
            rel = os.path.normpath(req["path"]).replace("\\", "/")
            fp = os.path.join(ROOT, rel)
            idx = load_index()
            if os.path.exists(fp):
                os.remove(fp)
                log.info(f"File deleted: {rel}")
            if rel in idx:
                del idx[rel]
                save_index(idx)
            self._send_json({"ok": True})

        else:
            log.warning(f"Unknown POST path: {self.path}")
            self.send_error(404)

def main():
    os.makedirs(ROOT, exist_ok=True)
    save_index(refresh_index_from_disk(load_index()))
    log.info("Server started on port 8080 – waiting for clients...")
    try:
        HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
    except KeyboardInterrupt:
        log.info("Server stopped manually (Ctrl+C).")

if __name__ == "__main__":
    main()
