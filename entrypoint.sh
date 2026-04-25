#!/bin/bash
set -e

# Initialize database if it doesn't exist
if [ ! -f "instance/erp_top.db" ]; then
    echo "Database not found. Initializing..."
    flask init-db
fi

# Start Gunicorn
echo "Starting Gunicorn..."
exec gunicorn --bind 0.0.0.0:5000 --workers 4 --threads 2 --timeout 120 run:app
