# YouTube Video Processor Backend

A FastAPI-based backend service that downloads YouTube videos, processes them with HEVC encoding, and uploads them to Cloudinary. **Specifically designed to handle real-world YouTube issues** like geo-restrictions, bot detection, format unavailability, and age restrictions.

## Features

### Core Functionality
- Download YouTube videos using yt-dlp with **6 fallback strategies**
- Process videos with ffmpeg to HEVC (libx265) codec at 720p max resolution  
- Upload processed videos to Cloudinary with organized folder structure
- Automatic cleanup of temporary files and comprehensive error handling

### Real-World Issue Handling
- **Format Not Available**: Multiple format fallback strategies (best → mobile → worst → audio-only)
- **"Sign in to confirm you're not a bot"**: Cookie-based authentication and mobile user agents
- **Geo-restrictions**: Geo-bypass attempts with different country codes
- **Age Restrictions**: Cookie-based authentication for age-gated content
- **CAPTCHA/Bot Detection**: User agent rotation and request timing strategies
- **Rate Limiting**: Automatic delays and retry logic between attempts
- **Network Issues**: Timeout handling and connection retry mechanisms

## Setup

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Install system dependencies:**
   ```bash
   # Ubuntu/Debian
   sudo apt update
   sudo apt install ffmpeg
   
   # macOS
   brew install ffmpeg
   
   # Windows
   # Download ffmpeg from https://ffmpeg.org/download.html
   ```

3. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your Cloudinary credentials
   ```

4. **Optional: Configure cookies for restricted videos:**
   **For age-restricted and geo-blocked content:**
   - Install browser extension: "Get cookies.txt" or "cookies.txt"
   - Visit youtube.com while logged in to your account
   - Export cookies to `backend/cookies.txt`
   - Set proper permissions: `chmod 600 cookies.txt`
   - **This enables access to age-restricted and some geo-blocked content**

## Usage

1. **Start the server:**
   ```bash
   python main.py
   ```

2. **API Endpoints:**
   - `GET /` - API information
   - `GET /health` - Health check
   - `POST /process` - Process a YouTube video

3. **Example request:**
   ```bash
   curl -X POST "http://localhost:8000/process" \
        -H "Content-Type: application/json" \
        -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
   ```

4. **Example response:**
   ```json
   {
     "status": "success",
     "public_url": "https://res.cloudinary.com/your-cloud/video/upload/v1234567890/youtube_hevc_720p/dQw4w9WgXcQ.mp4",
     "duration": 212.0,
     "filesize": 5242880,
     "video_id": "dQw4w9WgXcQ",
     "title": "Rick Astley - Never Gonna Give You Up",
     "processing_info": {
       "message": "Video successfully processed with HEVC encoding",
       "resolution": "720p max", 
       "codec": "libx265"
     }
   }
   ```

5. **Error response example:**
   ```json
   {
     "status": "failure",
     "error": "All download strategies failed. Last error: Video blocked or restricted",
     "processing_info": {
       "attempted_strategies": "Multiple download and processing strategies attempted",
       "common_issues": "May be due to geo-restrictions, bot detection, or format unavailability"
     }
   }
   ```

## Configuration

### Environment Variables

- `CLOUDINARY_CLOUD_NAME`: Your Cloudinary cloud name
- `CLOUDINARY_API_KEY`: Your Cloudinary API key
- `CLOUDINARY_API_SECRET`: Your Cloudinary API secret
- `DEBUG`: Enable debug mode (default: false)
- `MAX_VIDEO_SIZE_MB`: Maximum video size in MB (default: 500)

### FFmpeg Processing Settings

- Output format: MP4 container
- Video codec: libx265 (HEVC)
- Max resolution: 720p (maintains aspect ratio)
- Audio codec: AAC
- Audio bitrate: 96 kbps
- Output filename: `output_hevc_720p.mp4`
- Streaming optimization: `+faststart` flag for web playback
- Timeout: 30 minutes maximum processing time

## Error Handling

### Download Error Handling
The service uses **6 progressive fallback strategies**:

1. **Best Quality Strategy**: Standard high-quality download
2. **Cookie Authentication**: Uses cookies.txt for restricted content  
3. **Mobile User Agent**: Bypasses some desktop-specific blocks
4. **Geo-bypass Strategy**: Attempts to bypass regional restrictions
5. **Worst Quality Fallback**: Downloads lowest available quality
6. **Audio-Only Fallback**: Downloads audio and creates video with static image

### Common Error Scenarios Handled:
- Invalid YouTube URLs
- "Sign in to confirm you're not a bot" errors
- Format not available errors
- Geo-restricted content
- Age-restricted videos
- CAPTCHA and bot detection
- Network timeouts
- FFmpeg processing errors
- Cloudinary upload failures
- Rate limiting and quota issues
- Temporary file cleanup

## Logging

The service provides **detailed logging** for troubleshooting:

- Request/response logging
- Strategy attempt logging (which fallback methods were tried)
- Download progress and errors
- Specific error categorization (geo-block vs bot detection vs format issues)
- FFmpeg processing status
- Cloudinary upload status
- Cleanup operations
- Performance metrics and timing

## Security

- Input validation for YouTube URLs
- Secure handling of Cloudinary credentials
- Automatic cleanup of temporary files
- Optional cookie-based authentication for restricted content
- Request timeout limits to prevent resource exhaustion
- File size limits for uploads
- Temporary directory isolation

## Dependencies

- **FastAPI**: Modern web framework
- **yt-dlp**: Robust YouTube downloader (actively maintained fork of youtube-dl)
- **ffmpeg**: Video processing
- **cloudinary**: Cloud storage and CDN
- **pydantic**: Data validation
- **uvicorn**: ASGI server

## Deployment

For production deployment:

1. Use a production ASGI server (already configured with uvicorn)
2. Set up proper environment variables
3. Configure CORS origins appropriately
4. Set up monitoring and logging
5. Consider using a reverse proxy (nginx)
6. Implement rate limiting if needed
7. Configure cookies.txt for maximum content access
8. Monitor disk space for temporary file processing
9. Set up alerts for common error patterns

## Troubleshooting Common Issues

### "All download strategies failed"
- Check if cookies.txt is properly configured
- Verify the video is publicly accessible
- Check server logs for specific error details

### "Bot detection or login required"  
- Ensure cookies.txt contains valid YouTube session cookies
- Try accessing the video manually in a browser first
- Consider using a VPN if geo-blocked

### "Format not available"
- The service automatically tries multiple formats
- May indicate the video uses a very new or proprietary format
- Check if the video plays normally in a browser

### Processing timeouts
- Large videos may exceed the 30-minute processing limit
- Consider increasing MAX_VIDEO_SIZE_MB in environment variables
- Monitor server resources during processing

## License

This project is for educational purposes. Ensure you comply with YouTube's Terms of Service and copyright laws when using this service.