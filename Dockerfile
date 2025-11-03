FROM python:3.10-slim

WORKDIR /app
COPY . /app

# Install dependencies for psycopg2
RUN apt-get update && apt-get install -y gcc libpq-dev curl && \
    pip install --no-cache-dir psycopg2-binary && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Default command (will be overridden by docker-compose)
CMD ["python", "server/server.py"]