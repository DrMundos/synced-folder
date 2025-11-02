import os, time, json, hashlib, urllib.request, urllib.parse, logging

# === General Settings ===
SERVER = "http://127.0.0.1:8080"
LOCAL = os.path.abspath("synced")   # Local sync folder
SCAN_INTERVAL = 3                   # Interval (seconds) between sync cycles
STATE_FILE = os.path.join(LOCAL, ".local_state.json")

# === Logger ===
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger("SyncClient")

# === Helper Functions ===
def sha256_of_file(p):
    """Compute SHA256 hash of a file"""
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def local_index():
    """Return a dictionary of local files with their SHA and modification time"""
    idx = {}
    if not os.path.exists(LOCAL):
        os.makedirs(LOCAL, exist_ok=True)
        log.info(f"Created local folder: {LOCAL}")

    for dirpath, _, files in os.walk(LOCAL):
        for fn in files:
            if fn == ".local_state.json":
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), LOCAL).replace("\\", "/")
            fp = os.path.join(LOCAL, rel)
            st = os.stat(fp)
            idx[rel] = {"sha": sha256_of_file(fp), "mtime": st.st_mtime}
    return idx

def get_server_index():
    """Fetch the server's file index (includes sha and mtime)"""
    with urllib.request.urlopen(SERVER + "/index") as r:
        return json.loads(r.read())["index"]

def download_file(path):
    """Download a file from the server"""
    q = urllib.parse.urlencode({"path": path})
    with urllib.request.urlopen(SERVER + "/download?" + q) as r:
        data = r.read()
    os.makedirs(os.path.dirname(os.path.join(LOCAL, path)), exist_ok=True)
    with open(os.path.join(LOCAL, path), "wb") as f:
        f.write(data)
    log.info(f"⬇ Downloaded: {path} ({len(data)} bytes)")

def upload_file(path, base_sha):
    """Upload a file to the server"""
    fp = os.path.join(LOCAL, path)
    with open(fp, "rb") as f:
        data = f.read()
    meta = json.dumps({"path": path, "base_sha": base_sha}).encode("utf-8")
    req = urllib.request.Request(
        SERVER + "/upload",
        method="POST",
        data=meta + data,
        headers={
            "Content-Type": "application/octet-stream",
            "X-Meta-Length": str(len(meta))
        }
    )
    with urllib.request.urlopen(req) as r:
        result = json.loads(r.read())
    log.info(f"⬆ Uploaded: {path} (v{result['version']})")

def delete_on_server(path):
    """Delete a file on the server"""
    req = urllib.request.Request(
        SERVER + "/delete",
        method="POST",
        data=json.dumps({"path": path}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    urllib.request.urlopen(req).read()
    log.info(f"🗑️ Deleted remotely: {path}")

def load_state():
    """Load previous sync state (list of known files)"""
    try:
        if os.path.exists(STATE_FILE):
            return json.load(open(STATE_FILE, "r", encoding="utf-8"))
    except Exception:
        pass
    return {"files": []}

def save_state(files_list):
    """Save current list of files to state file"""
    try:
        json.dump({"files": sorted(files_list)}, open(STATE_FILE, "w", encoding="utf-8"))
    except Exception:
        pass

# === Core Sync Logic (timestamp-based) ===
def sync_once():
    # --- Step 1: Get indexes ---
    sidx = get_server_index()
    lidx = local_index()

    # --- Step 2: Load previous state ---
    prev_state = load_state()
    prev_files = set(prev_state.get("files", []))
    curr_files = set(lidx.keys())

    # --- Step 3: Handle local deletions ---
    locally_deleted = prev_files - curr_files
    for path in locally_deleted:
        if path in sidx:
            try:
                delete_on_server(path)
                log.info(f"🗑️ Deleted remotely due to local deletion: {path}")
            except Exception as e:
                log.error(f"Failed to delete remotely {path}: {e}")

    # --- Step 4: Refresh indexes ---
    sidx = get_server_index()
    lidx = local_index()

    # --- 🔥 Step 5: Handle remote deletions (important fix) ---
    for path in list(lidx.keys()):
        if path not in sidx:
            # The server no longer has this file — delete locally
            try:
                os.remove(os.path.join(LOCAL, path))
                log.info(f"🗑️ Deleted locally (server no longer has): {path}")
            except FileNotFoundError:
                pass

    # --- Step 6: Uploads and Updates (with timestamp comparison) ---
    for path, lmeta in local_index().items():
        smeta = sidx.get(path)

        if not smeta:
            # File doesn't exist on the server -> upload it
            upload_file(path, None)
            continue

        if smeta["sha"] != lmeta["sha"]:
            server_mtime = smeta.get("mtime", 0)
            local_mtime = lmeta["mtime"]

            if local_mtime > server_mtime + 1:
                upload_file(path, smeta["sha"])
                log.info(f"⬆ Updated on server (newer local): {path}")
            elif server_mtime > local_mtime + 1:
                download_file(path)
                log.info(f"⬇ Updated locally (newer server): {path}")
            else:
                log.info(f"⚖️ Skipped (similar timestamps): {path}")

    # --- Step 7: Download missing files (added on server) ---
    for path, smeta in sidx.items():
        if path not in local_index():
            download_file(path)
            log.info(f"⬇ Added missing local file: {path}")

    # --- Step 8: Save current state ---
    save_state(list(local_index().keys()))


def main():
    log.info("Client started – watching for changes...")
    os.makedirs(LOCAL, exist_ok=True)

    while True:
        try:
            sync_once()
        except Exception as e:
            log.error(f"Sync error: {e}")
        time.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    main()
