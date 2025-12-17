import os
import time
import hashlib
import threading
import requests
import socket

"""
Client-side file synchronization module.

This module monitors a local directory for file changes and synchronizes
them with a central server using an event-based mechanism.

The client operates using two background threads:
1. Local filesystem watcher (produces events)
2. Sync loop (replays events received from the server)

The server is treated as the single source of truth.
"""

# -------------------------------
# Configuration
# -------------------------------

SYNC_DIR = "./synced"
SERVER = os.getenv("SERVER", "http://localhost:8000")
CLIENT_ID = socket.gethostname()

# -------------------------------
# Runtime State
# -------------------------------

last_event_id = 0              # Last applied server event ID
fs_lock = threading.Lock()     # Prevent concurrent FS modifications

# State reconstructed only from server events
current_state = {}             # path -> sha256 hash
deleted_paths = set()          # Paths currently marked as deleted

# Events sent by this client but not yet acknowledged via sync
# Used to prevent circular updates
pending_events = set()


# -------------------------------
# Utility Functions
# -------------------------------

def hash_file(path):
    """
    Calculate SHA-256 hash of a file.

    Used to detect content changes and avoid unnecessary synchronization.
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()


def send_event(path, file_hash=None, deleted=False, content=None):
    """
    Send a file change event to the server.

    Events sent by this client are temporarily tracked in order to
    avoid re-applying them when they are returned from the server
    during synchronization.
    """
    try:
        response = requests.post(
            f"{SERVER}/event",
            json={
                "client": CLIENT_ID,
                "path": path,
                "hash": file_hash,
                "deleted": deleted,
                "content": content
            },
            timeout=5
        )
        response.raise_for_status()

        # Track the event to prevent circular updates
        event_key = (path, file_hash, deleted)
        pending_events.add(event_key)

        # Remove from pending after a short delay
        def remove_pending():
            time.sleep(5)
            pending_events.discard(event_key)

        threading.Thread(target=remove_pending, daemon=True).start()

        print(f"[CLIENT] Sent event: {path} (deleted={deleted})")

    except requests.exceptions.RequestException as e:
        print(f"[CLIENT ERROR] Failed to send event for {path}: {e}")


# -------------------------------
# Synchronization Loop
# -------------------------------

def sync_loop():
    """
    Continuously fetch and apply events from the server.

    The client requests all events newer than the last applied event ID
    and applies them locally in strict order.
    """
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

                # Skip events created by this client (already applied locally)
                if event_client == CLIENT_ID:
                    event_key = (path, e.get("hash"), e.get("deleted", False))
                    if event_key in pending_events:
                        last_event_id = max(last_event_id, event_id)
                        continue

                local_path = os.path.join(SYNC_DIR, path)

                try:
                    if e.get("deleted", False):
                        # Apply deletion
                        deleted_paths.add(path)
                        current_state.pop(path, None)

                        if os.path.exists(local_path):
                            os.remove(local_path)
                            print(f"[CLIENT] [DELETE] {path} from {event_client}")

                    else:
                        file_hash = e.get("hash")

                        # Skip if already at the same version
                        if current_state.get(path) == file_hash:
                            last_event_id = max(last_event_id, event_id)
                            continue

                        deleted_paths.discard(path)
                        current_state[path] = file_hash

                        # Ensure directory exists
                        os.makedirs(os.path.dirname(local_path), exist_ok=True)

                        with open(local_path, "w", encoding="utf-8") as f:
                            f.write(e.get("content", ""))

                        print(f"[CLIENT] [UPDATE] {path} from {event_client}")

                    last_event_id = max(last_event_id, event_id)

                except Exception as ex:
                    print(f"[CLIENT ERROR] Failed to apply event for {path}: {ex}")

        time.sleep(3)


# -------------------------------
# Local Filesystem Watcher
# -------------------------------

def watch_local():
    """
    Monitor the local sync directory for changes.

    This loop detects file creation, modification, and deletion,
    and generates corresponding events sent to the server.
    """
    known = {}

    while True:
        try:
            with fs_lock:
                current = {}

                os.makedirs(SYNC_DIR, exist_ok=True)

                for root, _, files in os.walk(SYNC_DIR):
                    for f in files:
                        abs_path = os.path.join(root, f)
                        rel = os.path.relpath(abs_path, SYNC_DIR)

                        # Ignore files currently marked as deleted
                        if rel in deleted_paths:
                            continue

                        # Ignore hidden files
                        if rel.startswith('.'):
                            continue

                        h = hash_file(abs_path)
                        current[rel] = h

                        # Detect new or modified files
                        if rel not in known or known[rel] != h:
                            if current_state.get(rel) != h:
                                try:
                                    with open(abs_path, "r", encoding="utf-8") as fh:
                                        content = fh.read()

                                    send_event(rel, h, False, content)
                                    current_state[rel] = h
                                    known[rel] = h

                                except Exception as e:
                                    print(f"[CLIENT ERROR] Failed to read {rel}: {e}")

                # Detect deletions
                for rel in known:
                    if rel not in current and rel not in deleted_paths:
                        send_event(rel, deleted=True)
                        deleted_paths.add(rel)
                        current_state.pop(rel, None)

                known = current

        except Exception as e:
            print(f"[CLIENT ERROR] Local watch failed: {e}")

        time.sleep(2)


# -------------------------------
# Entry Point
# -------------------------------

if __name__ == "__main__":
    os.makedirs(SYNC_DIR, exist_ok=True)

    threading.Thread(target=sync_loop, daemon=True).start()
    threading.Thread(target=watch_local, daemon=True).start()

    print(f"[CLIENT {CLIENT_ID}] running")

    while True:
        time.sleep(60)
