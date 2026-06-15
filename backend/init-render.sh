#!/bin/bash
set -e

# Start local Redis in the background (used for transient caching & queues)
echo "Starting local Redis server..."
redis-server --daemonize yes

# Wait for local Redis to be fully responsive
until redis-cli ping | grep -q PONG; do
  echo "Waiting for local Redis..."
  sleep 1
done
echo "Local Redis is up and running."

# Wait for remote MariaDB/MySQL database
echo "Waiting for Cloud Database (${DB_HOST}:${DB_PORT})...."
python3 -c "
import socket
import time
import os
import sys

host = os.environ.get('DB_HOST')
port = int(os.environ.get('DB_PORT', '3306'))

if not host:
    print('Error: DB_HOST environment variable is not defined.')
    sys.exit(1)

while True:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            s.connect((host, port))
            print('Cloud DB is reachable!')
            break
    except Exception as e:
        print(f'Waiting for Cloud DB at {host}:{port}... Details: {e}')
        time.sleep(3)
"

# Build and configure the bench
if [ ! -d "/home/frappe/frappe-bench/apps/frappe" ]; then
    echo "Bench folder not found. Initializing a new Frappe Bench..."
    bench init --skip-redis-config-generation frappe-bench
    cd frappe-bench
    
    # Update DB configurations to use cloud details
    bench set-mariadb-host "$DB_HOST"
    bench set-config -g db_port "$DB_PORT"
    
    # Route Redis tasks through local container Redis
    bench set-redis-cache-host redis://127.0.0.1:6379
    bench set-redis-queue-host redis://127.0.0.1:6379
    bench set-redis-socketio-host redis://127.0.0.1:6379

    # Set CORS to allow requests from the Vercel/Frontend URL
    bench set-config -g allow_cors "$FRONTEND_URL"
    bench set-config -g ignore_csrf 1

    # Remove Redis and Watch processes from standard supervisor configs
    sed -i '/redis/d' ./Procfile
    sed -i '/watch/d' ./Procfile

    echo "Fetching LMS and Payments apps..."
    git clone https://github.com/frappe/payments.git apps/payments --depth 1
    rm -f apps/payments/package.json
    ./env/bin/pip install -e ./apps/payments

    git clone https://github.com/frappe/lms.git apps/lms --depth 1
    rm -rf apps/lms/frontend apps/lms/package.json
    ./env/bin/pip install -e ./apps/lms

    printf "frappe\npayments\nlms\n" > sites/apps.txt

    echo "Provisioning new site on cloud database..."
    bench new-site lms.render \
      --db-name "$DB_NAME" \
      --mariadb-root-username "$DB_USER" \
      --mariadb-root-password "$DB_PASSWORD" \
      --admin-password "${ADMIN_PASSWORD:-admin}" \
      --no-mariadb-socket \
      --force

    bench --site lms.render install-app payments
    bench --site lms.render install-app lms
    bench --site lms.render set-config allow_cors "$FRONTEND_URL"
    bench --site lms.render clear-cache
    bench use lms.render
else
    echo "Bench already exists. Resuming services..."
    cd frappe-bench
fi

# Align Bench web service with Render's dynamic Port binding
sed -i "s/bench serve.*/bench serve --port ${PORT:-8000}/g" ./Procfile

# Start the Bench web server
echo "Starting Frappe Bench web server..."
bench start
