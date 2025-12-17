# Synced Folder

## Overview

Synced Folder is a lightweight file synchronization system implemented in Python as part of a final academic project.  
The project demonstrates core distributed systems concepts such as client–server architecture, event-based synchronization, consistency, and containerized deployment.

The system is designed for educational purposes and focuses on correctness, clarity, and architectural reasoning rather than production-level completeness.

---

## Project Goals

The main objectives of the project are:

- Implement a basic client–server file synchronization mechanism  
- Maintain consistency between multiple clients using a central server  
- Prevent data loss during concurrent file updates  
- Log synchronization activity for analysis and observability  
- Provide a reproducible deployment using Docker  

---

## System Architecture

The system consists of the following components:

### Server
- Acts as the single source of truth  
- Maintains a global file index and event log  
- Handles upload, download, and deletion requests  
- Exposes HTTP endpoints for synchronization  
- Optionally logs events to a PostgreSQL database  

### Client
- Monitors a local directory for file changes  
- Periodically synchronizes with the server  
- Uploads new or modified files  
- Applies updates and deletions received from the server  

### Database (Optional)
- PostgreSQL database used for logging synchronization events  
- Not required for the core synchronization logic  

### Monitoring (Optional)
- Prometheus for metrics collection  
- Grafana dashboards for visualization  

---

## Synchronization Model

### Core Principles

- The server maintains a global, ordered event log  
- All clients apply events in the same order  
- Consistency is enforced by a single authoritative server  

### Synchronization Flow

1. The client scans the local synchronization directory  
2. File changes are detected using SHA-256 hashes  
3. Changes are sent to the server as events  
4. The server assigns a global order to events  
5. Clients fetch and apply missing events  

---

## Conflict Prevention Strategy

The system does not implement active conflict resolution or file merging.

Instead, conflicts are prevented by design:

- All file changes are serialized by the server  
- The server determines a single authoritative order of events  
- Clients apply updates strictly according to this order  

This approach ensures that all clients converge to the same state without complex merge logic.

---

## Deployment

### Docker-Based Deployment (Recommended)

The project includes a Docker Compose setup for running all components together.

To start the system:

```bash
cd infrastructure/docker
docker compose up --build

and start upload/update/delete files from one of the synced folders (synced1/synced2)