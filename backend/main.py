import os
import tempfile
import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl, validator
import uvicorn

from video_processor import VideoProcessor
from config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('youtube_processor.log')
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="YouTube Video Processor API",
    description="Download, process, and upload YouTube videos to Cloudinary with robust error handling for real-world issues",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize settings
try:
    settings = get_settings()
    video_processor = VideoProcessor(settings)
    logger.info("Successfully initialized video processor")
except Exception as e:
    logger.error(f"Failed to initialize video processor: {str(e)}")
    settings = None
    video_processor = None

class VideoProcessRequest(BaseModel):
    url: HttpUrl
    
    @validator('url')
    def validate_youtube_url(cls, v):
        url_str = str(v)
        valid_domains = ['youtube.com', 'youtu.be', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com']
        if not any(domain in url_str for domain in valid_domains):
            raise ValueError('Must be a valid YouTube URL')
        
        # Additional validation for common invalid patterns
        if '/playlist' in url_str and 'list=' in url_str:
            raise ValueError('Playlist URLs are not supported, please provide individual video URLs')
        if '/channel/' in url_str or '/c/' in url_str or '/user/' in url_str:
            raise ValueError('Channel URLs are not supported, please provide individual video URLs')
            
        return v

class VideoProcessResponse(BaseModel):
    status: str
    public_url: Optional[str] = None
    duration: Optional[float] = None
    filesize: Optional[int] = None
    video_id: Optional[str] = None
    title: Optional[str] = None
    error: Optional[str] = None
    processing_info: Optional[Dict[str, Any]] = None

@app.get("/")
async def root():
    return {
        "message": "YouTube Video Processor API",
        "version": "1.0.0",
        "features": [
            "Handles geo-restrictions and age-restricted content",
            "Multiple fallback strategies for download failures", 
            "Bot detection and CAPTCHA bypass attempts",
            "HEVC/libx265 encoding with 720p max resolution",
            "Automatic cleanup and error recovery"
        ],
        "endpoints": {
            "POST /process": "Process a YouTube video",
            "GET /health": "Health check"
        },
        "status": "ready" if video_processor else "configuration_error"
    }

@app.get("/health")
async def health_check():
    if not video_processor:
        return {
            "status": "unhealthy",
            "error": "Video processor not initialized - check configuration",
            "service": "youtube-video-processor"
        }
        
    # Check system dependencies
    dependencies = {}
    
    # Check ffmpeg
    try:
        import subprocess
        result = subprocess.run(['ffmpeg', '-version'], 
                              stdout=subprocess.PIPE, 
                              stderr=subprocess.PIPE, 
                              check=True, timeout=10)
        dependencies['ffmpeg'] = 'available'
        
        # Check for libx265 support
        if b'libx265' in result.stdout:
            dependencies['libx265'] = 'available'
        else:
            dependencies['libx265'] = 'missing'
            
    except subprocess.TimeoutExpired:
        dependencies['ffmpeg'] = 'timeout'
    except subprocess.CalledProcessError:
        dependencies['ffmpeg'] = 'error'
    except FileNotFoundError:
        dependencies['ffmpeg'] = 'missing'
    except Exception as e:
        dependencies['ffmpeg'] = f'error: {str(e)}'
    
    # Check ffprobe
    try:
        subprocess.run(['ffprobe', '-version'], 
                      stdout=subprocess.DEVNULL, 
                      stderr=subprocess.DEVNULL, 
                      check=True, timeout=10)
        dependencies['ffprobe'] = 'available'
    except:
        dependencies['ffprobe'] = 'missing'
    
    # Check cookies file
    cookies_path = os.path.join(os.path.dirname(__file__), 'cookies.txt')
    if os.path.exists(cookies_path):
        # Check if cookies file has content
        try:
            with open(cookies_path, 'r') as f:
                content = f.read().strip()
                if content and not content.startswith('#'):
                    dependencies['cookies'] = 'configured'
                else:
                    dependencies['cookies'] = 'empty_template'
        except:
            dependencies['cookies'] = 'read_error'
    else:
        dependencies['cookies'] = 'not_found'
    
    # Check Cloudinary configuration
    try:
        if settings:
            if all([settings.cloudinary_cloud_name, settings.cloudinary_api_key, settings.cloudinary_api_secret]):
                dependencies['cloudinary'] = 'configured'
            else:
                dependencies['cloudinary'] = 'missing_credentials'
        else:
            dependencies['cloudinary'] = 'not_initialized'
    except:
        dependencies['cloudinary'] = 'error'
    
    # Check yt-dlp
    try:
        import yt_dlp
        dependencies['yt_dlp'] = f'available (v{yt_dlp.version.__version__})'
    except:
        dependencies['yt_dlp'] = 'missing'
    
    # Determine overall health
    critical_deps = ['ffmpeg', 'ffprobe', 'yt_dlp', 'cloudinary']
    health_status = "healthy"
    
    for dep in critical_deps:
        if dep not in dependencies or dependencies[dep] in ['missing', 'error', 'not_initialized', 'missing_credentials']:
            health_status = "unhealthy"
            break
    
    if dependencies.get('libx265') == 'missing':
        health_status = "degraded"  # Can still work but without HEVC
    
    return {
        "status": health_status,
        "service": "youtube-video-processor",
        "dependencies": dependencies,
        "recommendations": {
            "cookies": "Configure cookies.txt for age-restricted content access" if dependencies.get('cookies') != 'configured' else None,
            "libx265": "Install ffmpeg with libx265 support for HEVC encoding" if dependencies.get('libx265') == 'missing' else None
        }
    }

@app.post("/process", response_model=VideoProcessResponse)
async def process_video(
    request: VideoProcessRequest,
    background_tasks: BackgroundTasks
):
    """
    Process a YouTube video with robust error handling for real-world issues:
    - Handles geo-restrictions, age restrictions, and bot detection
    - Multiple fallback strategies for format availability
    - Downloads, transcodes to HEVC 720p, and uploads to Cloudinary
    - Comprehensive error reporting and recovery
    """
    if not video_processor:
        return VideoProcessResponse(
            status="failure",
            error="Service not properly configured - check environment variables and dependencies",
            processing_info={
                "error_type": "configuration_error",
                "suggestion": "Check /health endpoint for detailed status"
            }
        )
        
    try:
        logger.info(f"Processing video: {request.url}")
        
        # Process the video
        result = await video_processor.process_video(str(request.url))
        
        if result['status'] == 'success':
            return VideoProcessResponse(
                status="success",
                public_url=result['public_url'],
                duration=result.get('duration'),
                filesize=result.get('filesize'),
                video_id=result.get('video_id'),
                title=result.get('title'),
                processing_info={
                    "message": "Video successfully processed with HEVC encoding",
                    "resolution": "720p max",
                    "codec": "libx265"
                }
            )
        else:
            return VideoProcessResponse(
                status="failure",
                error=result.get('error', 'Unknown error occurred'),
                processing_info={
                    "attempted_strategies": "Multiple download and processing strategies attempted",
                    "common_issues": "May be due to geo-restrictions, bot detection, or format unavailability"
                }
            )
    
    except Exception as e:
        logger.error(f"Error processing video: {str(e)}")
        return VideoProcessResponse(
            status="failure",
            error=str(e),
            processing_info={
                "error_type": "unexpected_error",
                "suggestion": "Check server logs for detailed error information"
            }
        )

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )