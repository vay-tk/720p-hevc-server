#!/bin/bash

# Get the port from environment variable or use default 8000
PORT=${PORT:-8000}

# Start the application with the appropriate port
python -m uvicorn main:app --host 0.0.0.0 --port $PORT
