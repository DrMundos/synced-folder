# === Base image ===
FROM python:3.10-slim

# === Set working directory ===
WORKDIR /app

# === Copy the entire project into the container ===
COPY . /app

# === Install optional tools (like curl) ===
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# === Default command (will be overridden in docker-compose) ===
CMD ["python", "server/server.py"]
