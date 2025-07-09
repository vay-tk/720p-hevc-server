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
    # Set cloud optimization flag
    export CLOUD_OPTIMIZED=1
    # Increase FFmpeg timeout for cloud environment
    export FFMPEG_TIMEOUT=1800
fi

# Check for FFmpeg
if command -v ffmpeg &> /dev/null; then
    echo "✅ FFmpeg found: $(ffmpeg -version | head -n1)"
else
    echo "❌ FFmpeg not found! Video processing will fail."
fi

# Update yt-dlp to the latest version to handle YouTube API changes
echo "🔄 Updating yt-dlp to latest version..."
python -m pip install --upgrade yt-dlp
echo "✅ yt-dlp updated successfully"

# Run FFmpeg capability check to optimize settings
echo "🔧 Checking FFmpeg capabilities for optimal settings..."
python check_ffmpeg.py
echo ""

# Show YouTube download optimization status
if [ -f "cookies.txt" ]; then
    COOKIE_SIZE=$(wc -c < cookies.txt)
    if [ $COOKIE_SIZE -gt 100 ]; then
        echo "🍪 YouTube cookies found (~${COOKIE_SIZE} bytes) - Enhanced access enabled"
        # Set proper permissions
        chmod 600 cookies.txt
    else
        echo "⚠️ YouTube cookies file exists but appears empty"
    fi
else
    echo "ℹ️ No YouTube cookies file found - Access to restricted videos may be limited"
    # Create empty cookies template
    echo "# Netscape HTTP Cookie File - Empty template" > cookies.txt
    echo "# Get YouTube cookies using a browser extension and place them here" >> cookies.txt
    chmod 600 cookies.txt
fi

echo "===========================================" 
echo "📡 Starting server on http://0.0.0.0:$PORT"
echo "📚 API docs available at http://0.0.0.0:$PORT/docs"
echo "===========================================" 

# Set optimization flags for cloud environments
if [ -n "$CLOUD_OPTIMIZED" ]; then
    echo "🚀 Cloud optimization enabled"
    export FFMPEG_PRESET=veryfast
    export VIDEO_CODEC=libx264
    export MAX_RESOLUTION=480
    exec python -m uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1
else
    # Start the application with the appropriate port
    exec python -m uvicorn main:app --host 0.0.0.0 --port $PORT
fi
