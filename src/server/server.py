import json
import os
import time
import hashlib
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import psycopg2
from psycopg2.extras import RealDictCursor

from config.settings import POSTGRES, SERVER_PORT, STORAGE_DIR

"""
Server-side synchronization service.

This module implements a simple HTTP server that acts as the
single source of truth for file synchronization.

Responsibilities:
- Persist synchronization events in a database
- Expose HTTP endpoints for clients (/event, /sync)
- Maintain a server-side storage directory
- Detect and record changes made directly in server storage
"""


# -------------------------------
# Database Utilities
# -------------------------------

def get_db():
    """
    Create and return a database connection.

    The connection details are loaded from the configuration.
    """
    try:
        return psycopg2.connect(
            host=POSTGRES["host"],
            port=POSTGRES["port"],
            user=POSTGRES["user"],
            password=POSTGRES["password"],
            dbname=POSTGRES["dbname"]
        )
    except psycopg2.OperationalError as e:
        print(f"[DB ERROR] Connection failed: {e}")
        raise


def hash_file(path):
    """
    Calculate SHA-256 hash of a file on disk.

    Used by the storage watcher to detect content changes.
    """
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        print(f"[HASH ERROR] Failed to hash {path}: {e}")
        return None


# -------------------------------
# Storage Management
# -------------------------------

# Tracks files recently written by the server itself
# Used to avoid generating duplicate events
_recently_written_files = {}


def write_file_to_storage(path, content):
    """
    Write file content to the server storage directory.

    Files written by the server are tracked temporarily so the
    storage watcher does not immediately re-detect them.
    """
    try:
        full_path = os.path.join(STORAGE_DIR, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

        file_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        _recently_written_files[path] = file_hash

        print(f"[SERVER] Wrote file to storage: {path}")
    except Exception as e:
        print(f"[STORAGE ERROR] Failed to write {path}: {e}")


def delete_file_from_storage(path):
    """
    Delete a file from the server storage directory.

    Empty parent directories are cleaned up recursively.
    """
    try:
        full_path = os.path.join(STORAGE_DIR, path)
        if os.path.exists(full_path):
            os.remove(full_path)

            parent = os.path.dirname(full_path)
            while parent != STORAGE_DIR and parent != os.path.dirname(STORAGE_DIR):
                try:
                    if not os.listdir(parent):
                        os.rmdir(parent)
                        parent = os.path.dirname(parent)
                    else:
                        break
                except:
                    break

            print(f"[SERVER] Deleted file from storage: {path}")
    except Exception as e:
        print(f"[STORAGE ERROR] Failed to delete {path}: {e}")


# -------------------------------
# Event Persistence
# -------------------------------

def save_event(path, file_hash, deleted, client, content=None):
    """
    Persist a synchronization event in the database.

    After saving the event, the server storage directory is updated
    unless the event originated from the server itself.
    """
    try:
        conn = get_db()
        cur = conn.cursor()

        try:
            cur.execute("""
                INSERT INTO file_events (path, hash, deleted, client, content)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING event_id
            """, (path, file_hash, deleted, client, content))
            event_id = cur.fetchone()[0]

        except psycopg2.ProgrammingError:
            try:
                cur.execute("""
                    INSERT INTO file_events (path, hash, deleted, client, content)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (path, file_hash, deleted, client, content))
                event_id = cur.fetchone()[0]
            except psycopg2.ProgrammingError:
                cur.execute("""
                    INSERT INTO file_events (path, hash, deleted, client, content)
                    VALUES (%s, %s, %s, %s, %s)
                """, (path, file_hash, deleted, client, content))
                event_id = None

        conn.commit()
        conn.close()

        # Apply change to storage only for external clients
        if client != "SERVER":
            if deleted:
                delete_file_from_storage(path)
            elif content is not None:
                write_file_to_storage(path, content)

        return event_id

    except Exception as e:
        print(f"[DB ERROR] Failed to save event: {e}")
        raise


def init_database():
    """
    Initialize the database schema if it does not exist.
    """
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS file_events (
                event_id SERIAL PRIMARY KEY,
                path TEXT NOT NULL,
                hash TEXT,
                deleted BOOLEAN DEFAULT FALSE,
                client TEXT,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
        print("[SERVER] Database table initialized")
    except Exception as e:
        print(f"[DB ERROR] Failed to initialize database: {e}")


def get_events(since_event_id):
    """
    Fetch all events newer than the given event ID.

    Events are returned in ascending order to preserve consistency.
    """
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        try:
            cur.execute("""
                SELECT event_id, path, hash, deleted, content, client
                FROM file_events
                WHERE event_id > %s
                ORDER BY event_id ASC
            """, (since_event_id,))
        except psycopg2.ProgrammingError:
            cur.execute("""
                SELECT id AS event_id, path, hash, deleted, content, client
                FROM file_events
                WHERE id > %s
                ORDER BY id ASC
            """, (since_event_id,))

        rows = cur.fetchall()
        conn.close()
        return rows

    except Exception as e:
        print(f"[DB ERROR] Failed to get events: {e}")
        return []


# -------------------------------
# Storage Watcher
# -------------------------------

def watch_storage():
    """
    Monitor the server storage directory for changes.

    Any detected changes are converted into synchronization events
    and stored in the database.
    """
    global _recently_written_files
    known = {}

    while True:
        try:
            current = {}

            if os.path.exists(STORAGE_DIR):
                for root, _, files in os.walk(STORAGE_DIR):
                    for f in files:
                        abs_path = os.path.join(root, f)
                        rel = os.path.relpath(abs_path, STORAGE_DIR)

                        if rel.startswith('.'):
                            continue

                        h = hash_file(abs_path)
                        if not h:
                            continue

                        current[rel] = h

                        if rel not in known or known[rel] != h:
                            if rel in _recently_written_files and _recently_written_files[rel] == h:
                                known[rel] = h
                                _recently_written_files.pop(rel, None)
                                continue

                            with open(abs_path, "r", encoding="utf-8") as fh:
                                content = fh.read()

                            save_event(
                                path=rel,
                                file_hash=h,
                                deleted=False,
                                client="SERVER",
                                content=content
                            )

                            print(f"[SERVER] Detected change in storage: {rel}")

            for rel in known:
                if rel not in current and rel not in _recently_written_files:
                    save_event(
                        path=rel,
                        file_hash=None,
                        deleted=True,
                        client="SERVER",
                        content=None
                    )
                    print(f"[SERVER] Detected deletion in storage: {rel}")

            known = current

        except Exception as e:
            print(f"[STORAGE WATCH ERROR] {e}")

        time.sleep(3)


# -------------------------------
# HTTP Request Handler
# -------------------------------

class SyncHandler(BaseHTTPRequestHandler):
    """
    HTTP API handler for synchronization requests.
    """

    def _json(self, code, payload):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def do_POST(self):
        if self.path != "/event":
            return self._json(404, {"error": "not found"})

        try:
            length = int(self.headers.get("Content-Length", 0))
            if length == 0:
                return self._json(400, {"error": "empty body"})

            data = json.loads(self.rfile.read(length))

            save_event(
                path=data["path"],
                file_hash=data.get("hash"),
                deleted=data.get("deleted", False),
                client=data.get("client", "UNKNOWN"),
                content=data.get("content")
            )

            self._json(200, {"status": "ok"})

        except Exception as e:
            print(f"[SERVER ERROR] POST /event failed: {e}")
            self._json(500, {"error": str(e)})

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/sync":
            try:
                since_id = int(parse_qs(parsed.query).get("since_id", [0])[0])
                events = get_events(since_id)
                return self._json(200, events)
            except Exception as e:
                print(f"[SERVER ERROR] GET /sync failed: {e}")
                return self._json(500, {"error": str(e)})

        return self._json(404, {"error": "not found"})


# -------------------------------
# Entry Point
# -------------------------------

if __name__ == "__main__":
    try:
        init_database()
    except Exception as e:
        print(f"[SERVER WARNING] Database initialization failed: {e}")

    os.makedirs(STORAGE_DIR, exist_ok=True)
    print(f"[SERVER] Storage directory: {STORAGE_DIR}")

    threading.Thread(target=watch_storage, daemon=True).start()
    print("[SERVER] Storage watcher started")

    print(f"[SERVER] Running on port {SERVER_PORT}")
    HTTPServer(("0.0.0.0", SERVER_PORT), SyncHandler).serve_forever()
