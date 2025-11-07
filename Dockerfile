# ==============================
# 1️⃣ Base image
# ==============================
FROM python:3.11-slim

# Prevent Python from writing .pyc files & buffer logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# ==============================
# 2️⃣ Working directory
# ==============================
WORKDIR /app

# ==============================
# 3️⃣ Copy and install dependencies
# ==============================
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ==============================
# 4️⃣ Copy project files (including config & .env)
# ==============================
COPY . .

# Make sure Python can find packages from /app (so "from config import ..." works)
ENV PYTHONPATH=/app

# ==============================
# 5️⃣ Default environment variables
# ==============================
ENV SERVER_PORT=8080
ENV METRICS_PORT=8000
ENV SCAN_INTERVAL=3

# ==============================
# 6️⃣ Default command (server)
# ==============================
# This can be overridden by docker-compose (for client container)
CMD ["python", "server/server.py"]
