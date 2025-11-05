FROM python:3.11-slim

WORKDIR /app
COPY . .

# Install dependencies
RUN pip install --no-cache-dir psycopg2-binary requests prometheus_client

EXPOSE 8080
EXPOSE 8000

CMD ["python", "server/server.py"]