# 🗂️ Synced Folder

A simple **file synchronization system** built in Python, designed for educational purposes.  
It consists of a lightweight **server** and **client** that automatically sync files between multiple machines — similar in concept to Dropbox, but fully local and minimal.

--------------------------------------------------------------------------------

## ⚙️ Features

- 🔄 **Automatic synchronization** between clients and a central server  
- ⬆️ Uploads and ⬇️ downloads handled automatically  
- 🗑️ Local deletions are synced to the server  
- 🧩 Conflict detection and version tracking  
- 🪶 Built with only Python’s standard library — no external dependencies  
- 🧠 Fully open and easy to understand — great for learning about file synchronization logic  

--------------------------------------------------------------------------------

## 🧰 Project Structure

synced-folder/
│
├── server/
│ └── server.py # Runs the HTTP server and manages file index
│
├── client/
│ └── client.py # Client that watches and syncs local folder
│
├── .gitignore
└── README.md


--------------------------------------------------------------------------------


## 🚀 How to Run

### 1️⃣ Start the Server

```bash
cd server
python server.py

# The server will start on port 8080 and create a storage directory (storage/) to hold uploaded files


### 2️⃣ Start the Cleint 
cd client
python client.py

#A folder called synced/ will appear automatically. Any file you place inside this folder will upload to the server and sync across all clients connected to the same server.


--------------------------------------------------------------------------------

🧩 How Synchronization Works

The client scans the local folder (synced/) every few seconds.

It compares file hashes (SHA256) with the server index.

Changes are uploaded or downloaded automatically.

Local deletions trigger a remote delete on the server.

The server keeps a version index for all synced files.

--------------------------------------------------------------------------------


🧪 Example Demo

Run the server.

Run two clients (on two different machines or folders).

Add or modify files in one client → they appear in the other.

Delete a file locally → it’s removed everywhere.


--------------------------------------------------------------------------------

🧱 Technologies Used

🐍 Python 3.13.3

Standard libraries only:

http.server

hashlib

json

os, time, logging, urllib

--------------------------------------------------------------------------------


⚠️ Limitations

This is a simple educational implementation.
It does not yet include:

Encryption or authentication

Large-file chunking

“Tombstones” (deleted file history)

However, it’s a great foundation for implementing those features later.

--------------------------------------------------------------------------------

👤 Author

Sahar Gehasi
Built as part of a Computer Systems Workshop final project.

--------------------------------------------------------------------------------

🧡 License

This project is released under the MIT License.
You’re free to use, modify, and share it for any purpose.

--------------------------------------------------------------------------------
