import os
import time
import hashlib
import threading
import requests
import socket

SYNC_DIR = "./synced"
SERVER = os.getenv("SERVER", "http://localhost:8000")
CLIENT_ID = socket.gethostname()

last_event_id = 0
fs_lock = threading.Lock()

# מצב סופי שנבנה רק מה־events
current_state = {}  # path -> hash
deleted_paths = set()
pending_events = set()  # Track events we sent to avoid circular updates


def hash_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()


def send_event(path, file_hash=None, deleted=False, content=None):
    """Send event to server and track it to avoid circular updates."""
    try:
        response = requests.post(f"{SERVER}/event", json={
            "client": CLIENT_ID,
            "path": path,
            "hash": file_hash,
            "deleted": deleted,
            "content": content
        }, timeout=5)
        response.raise_for_status()
        
        # Track this event to avoid applying it when it comes back
        event_key = (path, file_hash, deleted)
        pending_events.add(event_key)
        
        # Remove from pending after a delay (events should be processed by then)
        def remove_pending():
            time.sleep(5)
            pending_events.discard(event_key)
        threading.Thread(target=remove_pending, daemon=True).start()
        
        print(f"[CLIENT] Sent event: {path} (deleted={deleted})")
    except requests.exceptions.RequestException as e:
        print(f"[CLIENT ERROR] Failed to send event for {path}: {e}")


# -------------------------------
# 🔁 SYNC LOOP – Event Replay
# -------------------------------
def sync_loop():
    global last_event_id

    while True:
        try:
            r = requests.get(
                f"{SERVER}/sync",
                params={"since_id": last_event_id},
                timeout=10
            )
            r.raise_for_status()
            events = r.json()
        except requests.exceptions.RequestException as e:
            print(f"[CLIENT ERROR] Failed to sync: {e}")
            time.sleep(3)
            continue

        with fs_lock:
            for e in events:
                path = e.get("path")
                if not path:
                    continue
                    
                event_client = e.get("client", "UNKNOWN")
                event_id = e.get("event_id") or e.get("id", 0)
                
                # Skip events we created ourselves to prevent circular updates
                if event_client == CLIENT_ID:
                    event_key = (path, e.get("hash"), e.get("deleted", False))
                    if event_key in pending_events:
                        print(f"[CLIENT] Skipping own event: {path} (event_id={event_id})")
                        # Still update last_event_id to avoid reprocessing
                        last_event_id = max(last_event_id, event_id)
                        continue
                
                local_path = os.path.join(SYNC_DIR, path)

                try:
                    if e.get("deleted", False):
                        deleted_paths.add(path)
                        current_state.pop(path, None)

                        if os.path.exists(local_path):
                            os.remove(local_path)
                            print(f"[CLIENT] [DELETE] {path} from {event_client}")

                    else:
                        # Check if file content actually changed
                        file_hash = e.get("hash")
                        if current_state.get(path) == file_hash:
                            # File already at this version, skip
                            print(f"[CLIENT] Skipping unchanged file: {path} (hash={file_hash})")
                            last_event_id = max(last_event_id, event_id)
                            continue
                        
                        deleted_paths.discard(path)
                        current_state[path] = file_hash

                        # Ensure directory exists
                        dir_path = os.path.dirname(local_path)
                        if dir_path:
                            os.makedirs(dir_path, exist_ok=True)
                        
                        with open(local_path, "w", encoding="utf-8") as f:
                            f.write(e.get("content", ""))
                        
                        print(f"[CLIENT] [UPDATE] {path} from {event_client} (hash={file_hash})")

                    last_event_id = max(last_event_id, event_id)
                except Exception as ex:
                    print(f"[CLIENT ERROR] Failed to apply event for {path}: {ex}")
                    import traceback
                    traceback.print_exc()

        time.sleep(3)


# --------------------------------
# 👀 WATCH LOCAL – רק יוצר events
# --------------------------------
def watch_local():
    known = {}

    while True:
        try:
            with fs_lock:
                current = {}

                if not os.path.exists(SYNC_DIR):
                    os.makedirs(SYNC_DIR, exist_ok=True)

                for root, _, files in os.walk(SYNC_DIR):
                    for f in files:
                        abs_path = os.path.join(root, f)
                        rel = os.path.relpath(abs_path, SYNC_DIR)

                        # Skip if file is marked as deleted (being processed)
                        if rel in deleted_paths:
                            continue
                        
                        # Skip hidden/system files
                        if rel.startswith('.'):
                            continue

                        try:
                            h = hash_file(abs_path)
                            if h:
                                current[rel] = h

                                # Only send event if file is new or hash changed
                                # Also check against current_state to avoid sending if we just received it
                                if rel not in known or known[rel] != h:
                                    # Double-check: if current_state says this hash, we might have just received it
                                    if current_state.get(rel) != h:
                                        try:
                                            with open(abs_path, "r", encoding="utf-8") as fh:
                                                content = fh.read()
                                            send_event(
                                                rel,
                                                h,
                                                False,
                                                content
                                            )
                                            # Update current_state immediately to prevent re-sending
                                            current_state[rel] = h
                                            known[rel] = h  # Also update known to prevent immediate re-send
                                        except Exception as e:
                                            print(f"[CLIENT ERROR] Failed to read {rel}: {e}")
                        except Exception as e:
                            print(f"[CLIENT ERROR] Failed to process {rel}: {e}")

                # Check for deleted files
                for rel in known:
                    if rel not in current:
                        # Only send delete event if file was actually deleted (not just being synced)
                        if rel not in deleted_paths:
                            send_event(rel, deleted=True)
                            deleted_paths.add(rel)
                            current_state.pop(rel, None)

                known = current
        except Exception as e:
            print(f"[CLIENT ERROR] Watch local failed: {e}")

        time.sleep(2)


if __name__ == "__main__":
    os.makedirs(SYNC_DIR, exist_ok=True)

    threading.Thread(target=sync_loop, daemon=True).start()
    threading.Thread(target=watch_local, daemon=True).start()

    print(f"[CLIENT {CLIENT_ID}] running")
    while True:
        time.sleep(60)
