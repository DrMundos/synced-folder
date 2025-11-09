🗂️ Synced Folder

A simple file synchronization system built in Python, designed for educational and demonstration purposes.
It includes a lightweight server, client, and optional PostgreSQL + Grafana integration for monitoring activity — conceptually similar to Dropbox, but fully local and minimal.

⚙️ Features

🔄 Automatic file synchronization between clients and a central server

⬆️ Uploads and ⬇️ downloads handled automatically

🗑️ Local deletions propagate to the server

🧩 Conflict detection and version tracking

🧠 Built entirely with Python’s standard library — no external dependencies required for core sync logic

🗃️ Optional PostgreSQL database for tracking file events

📊 Optional Grafana dashboard for visualizing sync activity

🧰 Project Structure
synced-folder/
│
├── src/                    # Main application source code
│   ├── server/
│   │   ├── __init__.py
│   │   └── server.py      # HTTP server handling uploads, downloads, and file index
│   ├── client/
│   │   ├── __init__.py
│   │   └── client.py      # Watches local folder, syncs with the server
│   └── config/
│       ├── __init__.py
│       └── settings.py    # Configuration settings
│
├── infrastructure/        # Infrastructure and deployment files
│   ├── docker/
│   │   ├── Dockerfile     # Shared build for both server and client
│   │   └── docker-compose.yml  # Multi-container setup
│   ├── grafana/
│   │   ├── provisioning/
│   │   │   ├── datasources/
│   │   │   │   └── datasource.yml
│   │   │   └── dashboards/
│   │   │       └── dashboard.yml
│   │   └── dashboards/
│   │       └── sync_dashboard.json
│   └── prometheus/
│       └── prometheus.yml
│
├── tests/                 # Test files (future)
├── storage/               # Server storage directory (runtime, gitignored)
├── synced/                # Client synced folder (runtime, gitignored)
├── requirements.txt       # Python dependencies
├── README.md
└── LICENSE

🚀 Quick Start (Docker Setup)
1️⃣ Build and start all containers
cd infrastructure/docker
docker compose up --build


This launches:

🐘 PostgreSQL (sync_postgres)

⚙️ Server (sync_server)

💻 Client (sync_client)

📈 Grafana (sync_grafana)

2️⃣ Access the system
Component	URL	Default Credentials
Server API	http://localhost:8080
	N/A
Client Synced Folder	./synced/	Files auto-sync
Grafana Dashboard	http://localhost:3030
	admin / admin
3️⃣ Test synchronization

Add or edit files inside synced/
→ They'll automatically upload to the server and appear in the storage/ folder.

Deletions or modifications will propagate both ways.

4️⃣ View database activity

Open PostgreSQL shell:

docker exec -it sync_postgres psql -U syncuser -d syncdb


Check the sync log:

SELECT * FROM files_log ORDER BY id DESC LIMIT 10;

5️⃣ View metrics in Grafana

Grafana automatically loads:

PostgreSQL as a preconfigured data source

A ready-to-use dashboard showing uploads and deletions over time

Visit http://localhost:3030
, log in as admin / admin, and explore the “Sync Folder Activity” dashboard.

🧩 How Synchronization Works

The client periodically scans its local folder (synced/).

It compares file SHA256 hashes against the server’s index.

Changes are automatically uploaded or downloaded.

Local deletions trigger remote deletions.

The server maintains version history and logs actions in PostgreSQL.

🧪 Example Workflow

Run docker compose up from infrastructure/docker/

Drop example.txt into synced/

The file appears in storage/

PostgreSQL logs the upload

Grafana shows the new data point on the chart

🧱 Technologies Used

🐍 Python 3.10 (standard library only)

🐘 PostgreSQL 15

📈 Grafana (auto-provisioned dashboard)

🐳 Docker + Docker Compose

⚠️ Limitations

This is a simplified demo implementation.
It does not include:

Authentication or encryption

Large-file chunking

File rename tracking or “tombstones”

Distributed conflict resolution

👤 Author

Sahar Gehasi
Built as part of a Computer Systems Workshop final project.
Extended for Dockerized deployment with PostgreSQL & Grafana observability.

🧡 License

Released under the MIT License.
You’re free to use, modify, and distribute this project for any purpose.
