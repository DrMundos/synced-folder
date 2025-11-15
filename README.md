# 🗂️ Synced FolderA lightweight file synchronization system built in Python, designed for educational and demonstration purposes. It provides automatic bidirectional file synchronization between clients and a central server, conceptually similar to Dropbox but fully local and minimal.## ⚙️ Features- 🔄 **Automatic file synchronization** between clients and a central server- ⬆️ **Bidirectional sync** - uploads and downloads handled automatically- 🗑️ **Deletion propagation** - local deletions propagate to the server- 🧩 **Conflict detection** - version tracking and conflict resolution- 📊 **Optional monitoring** - PostgreSQL database for tracking file events- 📈 **Optional metrics** - Grafana dashboard for visualizing sync activity- 🐳 **Docker deployment** - Complete containerized setup## 🏗️ ArchitectureThe system consists of:- **Server**: HTTP server that maintains the master file index and handles upload/download operations- **Client**: Background service that monitors local folder changes and syncs with server- **Database**: PostgreSQL for logging sync operations (optional)- **Monitoring**: Prometheus metrics and Grafana dashboards (optional)## 📋 Requirements### Core Dependencies- Python 3.10+- PostgreSQL 15 (optional, for logging)- Docker & Docker Compose (for containerized deployment)### Python Dependencies
psycopg2-binary==2.9.9 # PostgreSQL connector
prometheus-client==0.20.0 # Prometheus metrics exporter
python-dotenv==1.0.1 # Environment variable loading
requests==2.32.3 # HTTP client for optional integrations
## 🚀 Quick Start### Option 1: Docker Setup (Recommended)1. **Clone and navigate to docker directory:**     cd infrastructure/docker   2. **Start all services:**     docker compose up --build      This launches:   - 🐘 PostgreSQL database (`sync_postgres`)   - ⚙️ Sync server (`sync_server`) on port 8080   - 💻 Sync client (`sync_client`)   - 📊 Grafana dashboard on port 3030   - 📈 Prometheus metrics on port 90903. **Access the system:**   - **Server API**: http://localhost:8080   - **Grafana Dashboard**: http://localhost:3030 (admin/admin)   - **Client Synced Folder**: `./synced/` (auto-sync enabled)4. **Test synchronization:**   - Add files to the `synced/` folder   - They'll automatically upload to server and appear in `storage/`   - Check Grafana dashboard for activity visualization### Option 2: Local Development Setup1. **Install dependencies:**     pip install -r requirements.txt   2. **Set up PostgreSQL (optional):**     CREATE DATABASE syncdb;   CREATE USER syncuser WITH PASSWORD 'syncpass';   GRANT ALL PRIVILEGES ON DATABASE syncdb TO syncuser;   3. **Configure environment:**     # Create .env file in src/config/   POSTGRES_HOST=localhost   POSTGRES_DB=syncdb   POSTGRES_USER=syncuser   POSTGRES_PASSWORD=syncpass   SERVER_PORT=8080   SYNC_DIR=./synced   4. **Start the server:**     cd src   python -m server.server   5. **Start the client (in another terminal):**     cd src   python -m client.client   ## 🧩 How Synchronization Works### Core Algorithm1. **Client scans local folder** (`synced/`) periodically2. **Compares SHA256 hashes** against server's file index3. **Uploads new/changed files** to server4. **Downloads missing/outdated files** from server5. **Propagates deletions** in both directions6. **Handles conflicts** by creating conflict copies### Conflict ResolutionWhen both client and server have modified the same file:- Server creates a conflict copy: `filename (conflict @timestamp).ext`- Client version becomes the new canonical version- Both versions are preserved for manual resolution### Version Tracking- Each file maintains a version number- SHA256 hashes ensure data integrity- Modification timestamps track change order- All operations logged to PostgreSQL (when enabled)## 📊 Monitoring & Observability### Metrics Endpoints- **Prometheus**: `http://localhost:8000/metrics`- **Sync Logs API**: `http://localhost:8080/logs`### Grafana DashboardPre-configured dashboard includes:- Upload/download activity over time- File operation counts- Sync performance metrics- Database activity visualization### Database SchemaCREATE TABLE files_log (    id SERIAL PRIMARY KEY,    action VARCHAR(20),  -- 'upload' or 'delete'    path TEXT,    version INT,    sha TEXT,    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP);## 🧪 TestingRun the test suite:python -m pytest tests/### Test Coverage- Client-server communication- File hashing and integrity- Conflict resolution- Database logging- Error handling## 🏛️ Project Structure
Start all services:
   docker compose up --buildvironment Variables| Variable | Default | Description ||----------|---------|-------------|| `SERVER_PORT` | 8080 | HTTP server port || `METRICS_PORT` | 8000 | Prometheus metrics port || `SYNC_DIR` | `./synced` | Client sync directory || `SCAN_INTERVAL` | 3 | Client scan interval (seconds) || `POSTGRES_HOST` | postgres | Database host || `POSTGRES_DB` | syncdb | Database name || `POSTGRES_USER` | syncuser | Database user || `POSTGRES_PASSWORD` | syncpass | Database password |## 🛠️ Development### Code Quality# Lint codeflake8 src/# Run tests with coveragepytest --cov=src tests/### Adding Features- Server endpoints in `src/server/server.py`- Client logic in `src/client/client.py`- Configuration in `src/config/settings.py`- Tests in `tests/` directory## ⚠️ LimitationsThis is a simplified demo implementation with the following limitations:- **No authentication** - anyone can access the sync server- **No encryption** - files transferred in plain HTTP- **No large file chunking** - entire files loaded into memory- **No rename tracking** - renames treated as delete+create- **No distributed conflict resolution** - basic conflict handling only- **No user management** - single shared sync space## 🤝 Contributing1. Fork the repository2. Create a feature branch3. Add tests for new functionality4. Ensure all tests pass5. Submit a pull request## 📄 LicenseReleased under the MIT License - see [LICENSE](LICENSE) file for details.## 👤 Author**Sahar Gehasi**Built as part of a Computer Systems Workshop final project.Extended for Dockerized deployment with PostgreSQL & Grafana observability.---*Educational project demonstrating distributed systems concepts, file synchronization algorithms, and containerized deployment patterns.*
This launches:
🐘 PostgreSQL database (sync_postgres)
⚙️ Sync server (sync_server) on port 8080
💻 Sync client (sync_client)
📊 Grafana dashboard on port 3030
📈 Prometheus metrics on port 9090
Access the system:
Server API: http://localhost:8080
Grafana Dashboard: http://localhost:3030 (admin/admin)
Client Synced Folder: ./synced/ (auto-sync enabled)
Test synchronization:
Add files to the synced/ folder
They'll automatically upload to server and appear in storage/
Check Grafana dashboard for activity visualization
Option 2: Local Development Setup
Install dependencies:
   pip install -r requirements.txt
Set up PostgreSQL (optional):
   CREATE DATABASE syncdb;   CREATE USER syncuser WITH PASSWORD 'syncpass';   GRANT ALL PRIVILEGES ON DATABASE syncdb TO syncuser;
Configure environment:
   # Create .env file in src/config/   POSTGRES_HOST=localhost   POSTGRES_DB=syncdb   POSTGRES_USER=syncuser   POSTGRES_PASSWORD=syncpass   SERVER_PORT=8080   SYNC_DIR=./synced
Start the server:
   cd src   python -m server.server
Start the client (in another terminal):
   cd src   python -m client.client
🧩 How Synchronization Works
Core Algorithm
Client scans local folder (synced/) periodically
Compares SHA256 hashes against server's file index
Uploads new/changed files to server
Downloads missing/outdated files from server
Propagates deletions in both directions
Handles conflicts by creating conflict copies
Conflict Resolution
When both client and server have modified the same file:
Server creates a conflict copy: filename (conflict @timestamp).ext
Client version becomes the new canonical version
Both versions are preserved for manual resolution
Version Tracking
Each file maintains a version number
SHA256 hashes ensure data integrity
Modification timestamps track change order
All operations logged to PostgreSQL (when enabled)
📊 Monitoring & Observability
Metrics Endpoints
Prometheus: http://localhost:8000/metrics
Sync Logs API: http://localhost:8080/logs
Grafana Dashboard
Pre-configured dashboard includes:
Upload/download activity over time
File operation counts
Sync performance metrics
Database activity visualization
Database Schema
CREATE TABLE files_log (    id SERIAL PRIMARY KEY,    action VARCHAR(20),  -- 'upload' or 'delete'    path TEXT,    version INT,    sha TEXT,    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
🧪 Testing
Run the test suite:
python -m pytest tests/
Test Coverage
Client-server communication
File hashing and integrity
Conflict resolution
Database logging
Error handling
🏛️ Project Structure
synced-folder/├── src/                          # Main application code│   ├── server/│   │   ├── __init__.py│   │   └── server.py             # HTTP server with sync API│   ├── client/│   │   ├── __init__.py│   │   └── client.py             # File watcher and sync client│   └── config/│       ├── __init__.py│       └── settings.py           # Configuration management├── infrastructure/               # Deployment and monitoring│   ├── docker/│   │   ├── docker-compose.yml    # Multi-container setup│   │   └── Dockerfile            # Python application container│   ├── grafana/│   │   ├── dashboards/           # Pre-built Grafana dashboards│   │   └── provisioning/         # Grafana configuration│   └── prometheus/│       └── prometheus.yml        # Metrics collection config├── tests/                        # Test suite├── requirements.txt              # Python dependencies└── README.md
🔧 Configuration
Environment Variables
Variable	Default	Description
SERVER_PORT	8080	HTTP server port
METRICS_PORT	8000	Prometheus metrics port
SYNC_DIR	./synced	Client sync directory
SCAN_INTERVAL	3	Client scan interval (seconds)
POSTGRES_HOST	postgres	Database host
POSTGRES_DB	syncdb	Database name
POSTGRES_USER	syncuser	Database user
POSTGRES_PASSWORD	syncpass	Database password
🛠️ Development
Code Quality
# Lint codeflake8 src/# Run tests with coveragepytest --cov=src tests/
Adding Features
Server endpoints in src/server/server.py
Client logic in src/client/client.py
Configuration in src/config/settings.py
Tests in tests/ directory
⚠️ Limitations
This is a simplified demo implementation with the following limitations:
No authentication - anyone can access the sync server
No encryption - files transferred in plain HTTP
No large file chunking - entire files loaded into memory
No rename tracking - renames treated as delete+create
No distributed conflict resolution - basic conflict handling only
No user management - single shared sync space
🤝 Contributing
Fork the repository
Create a feature branch
Add tests for new functionality
Ensure all tests pass
Submit a pull request
📄 License
Released under the MIT License - see LICENSE file for details.
👤 Author
Sahar Gehasi
Built as part of a Computer Systems Workshop final project.
Extended for Dockerized deployment with PostgreSQL & Grafana observability.