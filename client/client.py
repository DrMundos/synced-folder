import os, time, json, hashlib, urllib.request, urllib.parse, logging
from config.settings import SERVER_URL, SYNC_DIR, SCAN_INTERVAL, STATE_FILE


# === Logging ===
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger("SyncClient")

# === Utilities ===
def sha256_of_file(path):
    """Return SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def local_index():
    """Build an index of all local files with hashes and modified times."""
    if not os.path.exists(SYNC_DIR):
        os.makedirs(SYNC_DIR, exist_ok=True)
        log.info(f"Created local folder: {SYNC_DIR}")
    idx = {}
    for dirpath, _, files in os.walk(SYNC_DIR):
        for fn in files:
            if fn == ".local_state.json":
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), SYNC_DIR).replace("\\", "/")
            st = os.stat(os.path.join(SYNC_DIR, rel))
            idx[rel] = {"sha": sha256_of_file(os.path.join(SYNC_DIR, rel)), "mtime": st.st_mtime}
    return idx

# === Server Communication ===
def get_server_index():
    with urllib.request.urlopen(f"{SERVER_URL}/index") as r:
        return json.loads(r.read())["index"]

def download_file(path):
    q = urllib.parse.urlencode({"path": path})
    with urllib.request.urlopen(f"{SERVER_URL}/download?{q}") as r:
        data = r.read()
    fp = os.path.join(SYNC_DIR, path)
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    with open(fp, "wb") as f:
        f.write(data)
    log.info(f"⬇ Downloaded: {path} ({len(data)} bytes)")

def upload_file(path, base_sha):
    fp = os.path.join(SYNC_DIR, path)
    with open(fp, "rb") as f:
        data = f.read()
    meta = json.dumps({"path": path, "base_sha": base_sha}).encode("utf-8")
    req = urllib.request.Request(
        f"{SERVER_URL}/upload",
        data=meta + data,
        headers={"Content-Type": "application/octet-stream", "X-Meta-Length": str(len(meta))},
        method="POST"
    )
    with urllib.request.urlopen(req) as r:
        res = json.loads(r.read())
    log.info(f"⬆ Uploaded: {path} (v{res['version']})")

def delete_on_server(path):
    req = urllib.request.Request(
        f"{SERVER_URL}/delete",
        data=json.dumps({"path": path}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    urllib.request.urlopen(req).read()
    log.info(f"🗑️ Deleted remotely: {path}")

# === State Tracking ===
def load_state():
    if os.path.exists(STATE_FILE):
        try:
            return json.load(open(STATE_FILE, "r", encoding="utf-8"))
        except Exception:
            pass
    return {"files": []}

def save_state(files_list):
    try:
        json.dump({"files": sorted(files_list)}, open(STATE_FILE, "w", encoding="utf-8"))
    except Exception:
        pass

# === Sync Logic ===
def sync_once():
    sidx = get_server_index()
    lidx = local_index()

    # Detect deleted local files and remove from server
    prev = set(load_state().get("files", []))
    curr = set(lidx.keys())
    deleted = prev - curr
    for path in deleted:
        if path in sidx:
            try:
                delete_on_server(path)
            except Exception as e:
                log.error(f"Failed to delete remotely {path}: {e}")

    # Refresh after deletions
    sidx, lidx = get_server_index(), local_index()

    # Upload new or changed files
    for path, lmeta in lidx.items():
        smeta = sidx.get(path)
        if not smeta or smeta["sha"] != lmeta["sha"]:
            upload_file(path, smeta["sha"] if smeta else None)

    # Download missing or outdated files
    sidx, lidx = get_server_index(), local_index()
    for path, meta in sidx.items():
        fp = os.path.join(SYNC_DIR, path)
        need = not os.path.exists(fp) or sha256_of_file(fp) != meta["sha"]
        if need:
            download_file(path)

    # Save updated state
    save_state(list(local_index().keys()))

# === Entrypoint ===
def main():
    log.info("🚀 Sync client started – watching for changes...")
    os.makedirs(SYNC_DIR, exist_ok=True)
    while True:
        try:
            sync_once()
        except Exception as e:
            log.error(f"Sync error: {e}")
        time.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    main()
