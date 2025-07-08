#!/bin/bash
set -e

# Default port is 8000 if not provided
PORT=${PORT:-8000}

# Start the application
echo "Starting application on port $PORT"
exec python -m uvicorn main:app --host 0.0.0.0 --port $PORT
