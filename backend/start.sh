#!/bin/bash

# Print banner
echo "===========================================" 
echo "🎬 YouTube Video Processor API"
echo "===========================================" 
echo "Starting up services..."

# Get the port from environment variable or use default 8000
PORT=${PORT:-8000}
echo "🔌 Using port: $PORT"

# Check if running in Docker or other container environment
if [ -f "/.dockerenv" ] || [ -f "/run/.containerenv" ]; then
    echo "🐳 Running in container environment"
    # Ensure logs are immediately flushed
    export PYTHONUNBUFFERED=1
    # Set FFmpeg options for containerized environment
    export FFMPEG_OPTS="-hide_banner -nostats"
    # Enable colorized output
    export COLORTERM=truecolor
fi

# Check for FFmpeg
if command -v ffmpeg &> /dev/null; then
    echo "✅ FFmpeg found: $(ffmpeg -version | head -n1)"
else
    echo "❌ FFmpeg not found! Video processing will fail."
fi

# Check for Cloudinary credentials
if [ -z "$CLOUDINARY_CLOUD_NAME" ] || [ -z "$CLOUDINARY_API_KEY" ] || [ -z "$CLOUDINARY_API_SECRET" ]; then
    echo "⚠️ Warning: Cloudinary credentials not set or incomplete"
fi

# Show YouTube download optimization status
if [ -f "cookies.txt" ]; then
    COOKIE_SIZE=$(wc -c < cookies.txt)
    if [ $COOKIE_SIZE -gt 100 ]; then
        echo "🍪 YouTube cookies found (~${COOKIE_SIZE} bytes) - Enhanced access enabled"
    else
        echo "⚠️ YouTube cookies file exists but appears empty"
    fi
else
    echo "ℹ️ No YouTube cookies file found - Access to restricted videos may be limited"
fi

echo "===========================================" 
echo "📡 Starting server on http://0.0.0.0:$PORT"
echo "📚 API docs available at http://0.0.0.0:$PORT/docs"
echo "===========================================" 

# Start the application with the appropriate port
exec python -m uvicorn main:app --host 0.0.0.0 --port $PORT
