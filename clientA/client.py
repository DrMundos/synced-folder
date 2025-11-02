import os, time, json, hashlib, urllib.request, urllib.parse, logging

# === הגדרות כלליות ===
SERVER = "http://127.0.0.1:8080"
LOCAL = os.path.abspath("synced")   # תיקיית סנכרון מקומית
SCAN_INTERVAL = 3                   # כל כמה שניות לבדוק שינויים
STATE_FILE = os.path.join(LOCAL, ".local_state.json")

# === Logger ===
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger("SyncClient")

# === עזר ===
def sha256_of_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

def local_index():
    idx = {}
    if not os.path.exists(LOCAL):
        os.makedirs(LOCAL, exist_ok=True)
        log.info(f"Created local folder: {LOCAL}")
    for dirpath, _, files in os.walk(LOCAL):
        for fn in files:
            if fn == ".local_state.json":  # לא לספור את state
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), LOCAL).replace("\\", "/")
            fp = os.path.join(LOCAL, rel)
            st = os.stat(fp)
            idx[rel] = {"sha": sha256_of_file(fp), "mtime": st.st_mtime}
    return idx

def get_server_index():
    with urllib.request.urlopen(SERVER + "/index") as r:
        return json.loads(r.read())["index"]

def download_file(path):
    q = urllib.parse.urlencode({"path": path})
    with urllib.request.urlopen(SERVER + "/download?" + q) as r:
        data = r.read()
    os.makedirs(os.path.dirname(os.path.join(LOCAL, path)), exist_ok=True)
    with open(os.path.join(LOCAL, path), "wb") as f:
        f.write(data)
    log.info(f"⬇ Downloaded: {path} ({len(data)} bytes)")

def upload_file(path, base_sha):
    fp = os.path.join(LOCAL, path)
    with open(fp, "rb") as f:
        data = f.read()
    meta = json.dumps({"path": path, "base_sha": base_sha}).encode("utf-8")
    req = urllib.request.Request(
        SERVER + "/upload",
        method="POST",
        data=meta + data,
        headers={"Content-Type": "application/octet-stream", "X-Meta-Length": str(len(meta))}
    )
    with urllib.request.urlopen(req) as r:
        result = json.loads(r.read())
    log.info(f"⬆ Uploaded: {path} (v{result['version']})")

def delete_on_server(path):
    req = urllib.request.Request(
        SERVER + "/delete",
        method="POST",
        data=json.dumps({"path": path}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    urllib.request.urlopen(req).read()
    log.info(f"🗑️ Deleted remotely: {path}")

def load_state():
    try:
        if os.path.exists(STATE_FILE):
            return json.load(open(STATE_FILE, "r", encoding="utf-8"))
    except Exception:
        pass
    return {"files": []}

def save_state(files_list):
    try:
        json.dump({"files": sorted(files_list)}, open(STATE_FILE, "w", encoding="utf-8"))
    except Exception:
        pass

def sync_once():
    # --- שלב 1: אינדקסים ---
    sidx = get_server_index()
    lidx = local_index()

    # --- שלב 2: מחיקות מקומיות מכוונות (לפני הורדות!) ---
    prev_files = set(load_state().get("files", []))
    curr_files = set(lidx.keys())
    locally_deleted = prev_files - curr_files

    for path in locally_deleted:
        if path in sidx:
            try:
                delete_on_server(path)
                log.info(f"🗑️ Deleted remotely due to local deletion: {path}")
            except Exception as e:
                log.error(f"Failed to delete remotely {path}: {e}")

    # --- שלב 3: ריענון אינדקס אחרי מחיקות ---
    sidx = get_server_index()
    lidx = local_index()

    # --- שלב 4: העלאות (קבצים חדשים / שונו) ---
    for path, lmeta in lidx.items():
        smeta = sidx.get(path)
        if not smeta or smeta["sha"] != lmeta["sha"]:
            base_sha = smeta["sha"] if smeta else None
            upload_file(path, base_sha)

    # --- שלב 5: הורדות (רק אחרי מחיקות והעלאות) ---
    sidx = get_server_index()
    lidx = local_index()
    for path, meta in sidx.items():
        lp = os.path.join(LOCAL, path)
        need = (not os.path.exists(lp))
        if not need:
            try:
                need = (sha256_of_file(lp) != meta["sha"])
            except FileNotFoundError:
                need = True
        if need and meta.get("sha"):
            download_file(path)

    # --- שלב 6: שמירת מצב נוכחי ---
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
