import os
import tempfile
import asyncio
import subprocess
import logging
import time
import random
import json
import shutil  # Add this import for the shutil.which() function
from pathlib import Path
from typing import Dict, Any, Optional, List
import yt_dlp
import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url

logger = logging.getLogger(__name__)

class VideoProcessor:
    def __init__(self, settings):
        self.settings = settings
        self.setup_cloudinary()
        
    def setup_cloudinary(self):
        """Configure Cloudinary with credentials"""
        cloudinary.config(
            cloud_name=self.settings.cloudinary_cloud_name,
            api_key=self.settings.cloudinary_api_key,
            api_secret=self.settings.cloudinary_api_secret,
            secure=True
        )
        
    async def process_video(self, url: str) -> Dict[str, Any]:
        """
        Main video processing pipeline with comprehensive error handling
        """
        temp_dir = None
        try:
            # Create temporary directory
            temp_dir = tempfile.mkdtemp(prefix="youtube_processor_")
            logger.info(f"Created temp directory: {temp_dir}")
            
            # Step 1: Download video with multiple fallback strategies
            download_result = await self.download_video_with_fallbacks(url, temp_dir)
            if not download_result['success']:
                return {'status': 'failure', 'error': download_result['error']}
            
            # Step 2: Process video with ffmpeg
            process_result = await self.process_with_ffmpeg(
                download_result['video_path'],
                download_result.get('audio_path'),
                temp_dir
            )
            if not process_result['success']:
                return {'status': 'failure', 'error': process_result['error']}
            
            # Step 3: Upload to Cloudinary
            upload_result = await self.upload_to_cloudinary(
                process_result['output_path'],
                download_result['video_info']
            )
            if not upload_result['success']:
                return {'status': 'failure', 'error': upload_result['error']}
            
            return {
                'status': 'success',
                'public_url': upload_result['public_url'],
                'duration': download_result['video_info'].get('duration'),
                'filesize': upload_result.get('filesize'),
                'video_id': download_result['video_info'].get('id'),
                'title': download_result['video_info'].get('title')
            }
            
        except Exception as e:
            logger.error(f"Error in process_video: {str(e)}")
            return {'status': 'failure', 'error': str(e)}
        finally:
            # Cleanup temporary directory
            if temp_dir and os.path.exists(temp_dir):
                await self.cleanup_temp_dir(temp_dir)

    async def download_video_with_fallbacks(self, url: str, temp_dir: str) -> Dict[str, Any]:
        """
        Download video with multiple fallback strategies to handle real-world issues
        """
        strategies = [
            self._strategy_best_quality,
            self._strategy_with_cookies,
            self._strategy_mobile_user_agent,
            self._strategy_bypass_geo,
            self._strategy_worst_quality,
            self._strategy_legacy_formats,
            self._strategy_audio_only_fallback
        ]
        
        last_error = None
        
        for i, strategy in enumerate(strategies):
            try:
                logger.info(f"Attempting download strategy {i+1}/{len(strategies)}: {strategy.__name__}")
                
                # Add random delay between attempts to avoid rate limiting
                if i > 0:
                    delay = random.uniform(2, 5)
                    logger.info(f"Waiting {delay:.1f}s before retry...")
                    await asyncio.sleep(delay)
                
                result = await strategy(url, temp_dir)
                if result['success']:
                    logger.info(f"Successfully downloaded using strategy: {strategy.__name__}")
                    return result
                else:
                    last_error = result['error']
                    logger.warning(f"Strategy {strategy.__name__} failed: {last_error}")
                    
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Strategy {strategy.__name__} threw exception: {last_error}")
                continue
        
        return {
            'success': False, 
            'error': f'All download strategies failed. Last error: {last_error}'
        }

    async def _strategy_best_quality(self, url: str, temp_dir: str) -> Dict[str, Any]:
        """Strategy 1: Best quality with standard options"""
        # Updated modern user agent - using Firefox instead of Chrome to avoid bot detection
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0'
        
        ydl_opts = {
            'format': 'best[height<=720][ext=mp4]/best[height<=720]/best[ext=mp4]/best/worst',
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'noplaylist': True,
            'extract_flat': False,
            'writethumbnail': False,
            'writesubtitles': False,
            'writeautomaticsub': False,
            'ignoreerrors': False,
            'no_warnings': False,
            'quiet': False,
            'verbose': False,
            'http_headers': {
                'User-Agent': user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'TE': 'trailers',
                'DNT': '1',
            },
            'extractor_args': {
                'youtube': {
                    # Updated player clients and keys
                    'player_client': ['web', 'android', 'ios'],
                    'player_skip': [],
                    'innertube_host': ['www.youtube.com', 'youtubei.googleapis.com'],
                    'innertube_key': [
                        'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8',  # Web
                        'AIzaSyB-63vPrdThhKuerbB2N_l7Kwwcxj6yUAc',  # Mobile
                        'AIzaSyDCU8hByM-4DrUqRUYnGn-3llEO78bcxq8'   # Android TV
                    ]
                }
            }
        }
        
        return await self._download_with_options(url, temp_dir, ydl_opts)

    async def _strategy_with_cookies(self, url: str, temp_dir: str) -> Dict[str, Any]:
        """Strategy 2: Use cookies to handle login/age restrictions"""
        cookies_path = os.path.join(os.path.dirname(__file__), 'cookies.txt')
        
        # Updated modern user agent with Safari on macOS
        user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15'
        
        ydl_opts = {
            'format': 'best[height<=720][ext=mp4]/best[height<=720]/best[ext=mp4]/best/worst',
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'noplaylist': True,
            'extract_flat': False,
            'ignoreerrors': False,
            'quiet': False,
            'cookiefile': cookies_path if os.path.exists(cookies_path) else None,
            'http_headers': {
                'User-Agent': user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Referer': 'https://www.youtube.com/',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate', 
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['web', 'android', 'ios'],
                    'player_skip': [],
                    'innertube_host': ['www.youtube.com', 'youtubei.googleapis.com'],
                    'innertube_key': [
                        'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8',
                        'AIzaSyB-63vPrdThhKuerbB2N_l7Kwwcxj6yUAc'
                    ]
                }
            }
        }
        
        if not os.path.exists(cookies_path):
            return {'success': False, 'error': 'Cookies file not available'}
            
        return await self._download_with_options(url, temp_dir, ydl_opts)

    async def _strategy_mobile_user_agent(self, url: str, temp_dir: str) -> Dict[str, Any]:
        """Strategy 3: Use mobile user agent to bypass some restrictions"""
        # Updated modern iOS user agent
        user_agent = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1'
        
        ydl_opts = {
            'format': 'best[height<=480]/worst',
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'noplaylist': True,
            'quiet': False,
            'http_headers': {
                'User-Agent': user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Referer': 'https://m.youtube.com/',
                'Upgrade-Insecure-Requests': '1',
                'X-Requested-With': 'XMLHttpRequest',
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Dest': 'empty',
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['ios', 'android'],
                    'player_skip': [],
                    'innertube_host': ['m.youtube.com', 'youtubei.googleapis.com'],
                    'innertube_key': ['AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8', 'AIzaSyB-63vPrdThhKuerbB2N_l7Kwwcxj6yUAc']
                }
            }
        }
        
        return await self._download_with_options(url, temp_dir, ydl_opts)

    async def _strategy_bypass_geo(self, url: str, temp_dir: str) -> Dict[str, Any]:
        """Strategy 4: Attempt to bypass geo-restrictions"""
        # Rotating through user agents - Android device
        user_agent = 'Mozilla/5.0 (Linux; Android 13; SM-S908B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36'
        
        ydl_opts = {
            'format': 'worst/best',
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'noplaylist': True,
            'quiet': False,
            'geo_bypass': True,
            'geo_bypass_country': 'US',
            'http_headers': {
                'User-Agent': user_agent,
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate',
                'Origin': 'https://www.youtube.com',
                'Connection': 'keep-alive',
                'Referer': 'https://www.youtube.com/',
                'X-YouTube-Client-Name': '2', 
                'X-YouTube-Client-Version': '2.20240701.01.00',
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    'player_skip': [],
                    'innertube_host': ['youtubei.googleapis.com'],
                    'innertube_key': ['AIzaSyB-63vPrdThhKuerbB2N_l7Kwwcxj6yUAc'],
                    'use_player_response': ['True']
                }
            }
        }
        
        return await self._download_with_options(url, temp_dir, ydl_opts)

    async def _strategy_worst_quality(self, url: str, temp_dir: str) -> Dict[str, Any]:
        """Strategy 5: Fallback to worst quality if others fail"""
        # Use "evergreen" browser UA to avoid fingerprinting
        user_agent = 'Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0'
        
        ydl_opts = {
            'format': 'worst',
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'noplaylist': True,
            'quiet': False,
            'ignoreerrors': True,
            'http_headers': {
                'User-Agent': user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Referer': 'https://www.google.com/',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate', 
                'Sec-Fetch-User': '?1',
                'Sec-GPC': '1',
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['web', 'tv_embedded', 'android'],
                    'player_skip': [],
                    'innertube_host': ['www.youtube.com'],
                    'innertube_key': ['AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8']
                }
            }
        }
        
        return await self._download_with_options(url, temp_dir, ydl_opts)

    async def _strategy_legacy_formats(self, url: str, temp_dir: str) -> Dict[str, Any]:
        """Strategy 6: Try legacy format selection"""
        # Smart TV user agent
        user_agent = 'Mozilla/5.0 (SMART-TV; Linux; Tizen 5.5) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/3.0 Chrome/69.0.3497.106 TV Safari/537.36'
        
        ydl_opts = {
            'format': '18/22/36/17/13/5',  # Legacy format codes
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'noplaylist': True,
            'quiet': False,
            'ignoreerrors': True,
            'prefer_insecure': True,
            'http_headers': {
                'User-Agent': user_agent,
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Origin': 'https://www.youtube.com',
                'Connection': 'keep-alive',
                'Referer': 'https://www.youtube.com/',
                'X-YouTube-Client-Name': '3',
                'X-YouTube-Client-Version': '16.20'
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['tv_embedded', 'android'],
                    'player_skip': [],
                    'innertube_host': ['youtubei.googleapis.com'],
                    'innertube_key': ['AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8', 'AIzaSyB-63vPrdThhKuerbB2N_l7Kwwcxj6yUAc']
                }
            }
        }
        
        return await self._download_with_options(url, temp_dir, ydl_opts)

    async def _strategy_audio_only_fallback(self, url: str, temp_dir: str) -> Dict[str, Any]:
        """Strategy 7: Last resort - audio only (will be converted to video with static image)"""
        # Game console user agent
        user_agent = 'Mozilla/5.0 (PlayStation; PlayStation 5/2.26) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0 Safari/605.1.15'
        
        ydl_opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio',
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'noplaylist': True,
            'quiet': False,
            'ignoreerrors': True,
            'http_headers': {
                'User-Agent': user_agent,
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Referer': 'https://www.youtube.com/',
                'X-YouTube-Client-Name': '5',
                'X-YouTube-Client-Version': '16.20'
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['tv_embedded', 'android', 'web'],
                    'player_skip': [],
                    'innertube_host': ['youtubei.googleapis.com'],
                    'innertube_key': ['AIzaSyB-63vPrdThhKuerbB2N_l7Kwwcxj6yUAc']
                }
            }
        }
        
        result = await self._download_with_options(url, temp_dir, ydl_opts)
        
        if result['success']:
            # Mark as audio-only for special processing
            result['audio_only'] = True
            
        return result

    async def _download_with_options(self, url: str, temp_dir: str, ydl_opts: Dict) -> Dict[str, Any]:
        """
        Execute download with given options and handle common errors
        """
        try:
            video_info = None
            video_path = None
            
            # Add common options to prevent issues
            ydl_opts.update({
                'socket_timeout': 30,
                'retries': 3,
                'fragment_retries': 3,
                'skip_unavailable_fragments': True,
                'keep_fragments': False,
                'abort_on_unavailable_fragment': False,
                # Enable debugging for YouTube related issues
                'debug_printtraffic': self.settings.debug,
                # Add proxy support if configured
                'proxy': os.environ.get('HTTP_PROXY', None),
                # IMPORTANT: Disable cookiesfrombrowser to avoid failures in Docker/containers
                'cookiesfrombrowser': None,
                # Request page for longer and with randomization to avoid bot detection
                'sleep_interval': random.uniform(1.0, 3.0),
                'max_sleep_interval': 5.0,
                'sleep_interval_requests': 1,
                'sleep_interval_subtitles': 0,
            })
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract video info first
                try:
                    info = ydl.extract_info(url, download=False)
                    if not info:
                        return {'success': False, 'error': 'Could not extract video information'}
                    video_info = info
                except Exception as e:
                    error_msg = str(e).lower()
                    if any(phrase in error_msg for phrase in [
                        'sign in to confirm', 'not a bot', 'captcha',
                        'blocked', 'restricted', 'unavailable', 'private',
                        'members-only', 'join this channel', 'age-restricted',
                        'precondition check failed'
                    ]):
                        return {'success': False, 'error': f'Access restricted: {str(e)}'}
                    elif 'video unavailable' in error_msg:
                        return {'success': False, 'error': 'Video is unavailable or deleted'}
                    elif 'premieres in' in error_msg:
                        return {'success': False, 'error': 'Video is a premiere and not yet available'}
                    raise
                
                # Add some randomization to appear less bot-like
                await asyncio.sleep(random.uniform(0.5, 2.0))
                
                # Download the video
                try:
                    ydl.download([url])
                except Exception as e:
                    error_msg = str(e).lower()
                    if 'format not available' in error_msg:
                        return {'success': False, 'error': 'Requested format not available'}
                    elif 'no video formats found' in error_msg:
                        return {'success': False, 'error': 'No downloadable video formats available'}
                    elif any(phrase in error_msg for phrase in [
                        'sign in to confirm', 'not a bot', 'captcha', 'precondition check failed'
                    ]):
                        return {'success': False, 'error': 'Bot detection or login required'}
                    elif any(phrase in error_msg for phrase in [
                        'blocked', 'restricted', 'unavailable', 'geo',
                        'not available in your country', 'copyright'
                    ]):
                        return {'success': False, 'error': 'Content blocked or geo-restricted'}
                    elif 'http error 429' in error_msg:
                        return {'success': False, 'error': 'Rate limited by YouTube'}
                    elif 'http error 403' in error_msg:
                        return {'success': False, 'error': 'Access forbidden - may need authentication'}
                    raise
                
                # Find downloaded files
                downloaded_files = []
                for file in os.listdir(temp_dir):
                    if file.endswith(('.mp4', '.mkv', '.webm', '.m4a', '.mp3', '.wav', '.flv', '.avi', '.3gp', '.f4v')):
                        downloaded_files.append(os.path.join(temp_dir, file))
                
                if not downloaded_files:
                    # Check if only non-video files were downloaded
                    all_files = os.listdir(temp_dir)
                    if any(f.endswith('.mhtml') for f in all_files):
                        return {'success': False, 'error': 'Only images available - video may be restricted or deleted'}
                    return {'success': False, 'error': 'No files downloaded'}
                
                video_path = downloaded_files[0]
                
                # Verify file is not empty
                if os.path.getsize(video_path) < 1024:  # Less than 1KB
                    return {'success': False, 'error': 'Downloaded file appears to be empty or corrupted'}
                
                # Check if it's actually a video file (not just an image or metadata)
                if video_path.endswith('.mhtml'):
                    return {'success': False, 'error': 'Only thumbnail/metadata downloaded - video content not available'}
            
            logger.info(f"Successfully downloaded: {video_path}")
            
            return {
                'success': True,
                'video_path': video_path,
                'video_info': video_info
            }
            
        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e).lower()
            if 'format not available' in error_msg:
                return {'success': False, 'error': 'Video format not available'}
            elif 'no video formats found' in error_msg:
                return {'success': False, 'error': 'No downloadable formats found'}
            elif any(phrase in error_msg for phrase in [
                'sign in to confirm', 'not a bot', 'captcha', 'precondition check failed'
            ]):
                return {'success': False, 'error': 'YouTube bot detection triggered'}
            elif any(phrase in error_msg for phrase in [
                'blocked', 'restricted', 'unavailable', 'private', 'deleted'
            ]):
                return {'success': False, 'error': 'Video blocked or restricted'}
            elif 'http error' in error_msg:
                return {'success': False, 'error': f'Network error: {str(e)}'}
            else:
                return {'success': False, 'error': f'Download error: {str(e)}'}
        except yt_dlp.utils.ExtractorError as e:
            error_msg = str(e).lower()
            if 'video unavailable' in error_msg:
                return {'success': False, 'error': 'Video is unavailable or has been removed'}
            elif 'private video' in error_msg:
                return {'success': False, 'error': 'Video is private'}
            elif 'members-only' in error_msg:
                return {'success': False, 'error': 'Video is members-only'}
            elif 'precondition check failed' in error_msg:
                return {'success': False, 'error': 'YouTube access restricted - may need authentication or video is unavailable'}
            elif 'only images are available' in error_msg:
                return {'success': False, 'error': 'Video content not available - only thumbnails accessible'}
            else:
                return {'success': False, 'error': f'Extraction error: {str(e)}'}
        except Exception as e:
            return {'success': False, 'error': f'Unexpected error: {str(e)}'}

    async def process_with_ffmpeg(self, video_path: str, audio_path: Optional[str], temp_dir: str) -> Dict[str, Any]:
        """
        Process video with ffmpeg to HEVC 720p with enhanced error handling
        """
        try:
            output_path = os.path.join(temp_dir, 'output_hevc_720p.mp4')
            
            # Check if input is audio-only
            is_audio_only = video_path.endswith(('.m4a', '.mp3', '.wav'))
            
            # First, probe the input file to check if it's valid
            probe_cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', video_path]
            try:
                probe_process = await asyncio.create_subprocess_exec(
                    *probe_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                probe_stdout, probe_stderr = await asyncio.wait_for(
                    probe_process.communicate(), 
                    timeout=30
                )
                
                if probe_process.returncode != 0:
                    error_detail = probe_stderr.decode() if probe_stderr else "Unknown probe error"
                    logger.error(f"FFprobe failed: {error_detail}")
                    return {'success': False, 'error': f'Input file is corrupted or invalid: {error_detail}'}
                
                # Parse probe output to get stream info
                try:
                    probe_data = json.loads(probe_stdout.decode())
                    has_video = any(stream.get('codec_type') == 'video' for stream in probe_data.get('streams', []))
                    has_audio = any(stream.get('codec_type') == 'audio' for stream in probe_data.get('streams', []))
                    
                    if not has_video and not has_audio:
                        return {'success': False, 'error': 'No valid video or audio streams found'}
                    
                    logger.info(f"Input file analysis: has_video={has_video}, has_audio={has_audio}")
                        
                except json.JSONDecodeError as e:
                    logger.warning(f"Could not parse probe output: {str(e)}, proceeding anyway")
                    has_video = not is_audio_only
                    has_audio = True
                    
            except asyncio.TimeoutError:
                logger.warning("FFprobe timed out, proceeding anyway")
                has_video = not is_audio_only
                has_audio = True
            except Exception as e:
                logger.warning(f"Could not probe input file: {str(e)}, proceeding anyway")
                has_video = not is_audio_only
                has_audio = True

            # Build FFmpeg command based on input type
            if is_audio_only or not has_video:
                # Create video from audio with static image
                cmd = [
                    'ffmpeg',
                    '-f', 'lavfi',
                    '-i', 'color=c=black:s=1280x720:r=1',
                    '-i', video_path,
                    '-c:v', 'libx265',
                    '-crf', '28',
                    '-preset', 'medium',
                    '-c:a', 'aac',
                    '-b:a', '96k',
                    '-shortest',
                    '-movflags', '+faststart',
                    # Add progress output
                    '-stats',
                    '-progress', 'pipe:1',
                    '-y',
                    output_path
                ]
            else:
                # Standard video processing with simplified approach
                cmd = [
                    'ffmpeg',
                    '-i', video_path,
                    '-c:v', 'libx265',
                    '-crf', '28',
                    '-preset', 'medium',
                    '-vf', 'scale=-2:720',  # Simplified scaling
                    '-c:a', 'aac',
                    '-b:a', '96k',
                    '-movflags', '+faststart',
                    '-avoid_negative_ts', 'make_zero',
                    # Replace error level with stats
                    '-stats',
                    '-progress', 'pipe:1',
                    '-y',
                    output_path
                ]

            # If separate audio file exists, use it
            if audio_path and os.path.exists(audio_path) and not is_audio_only:
                cmd = [
                    'ffmpeg',
                    '-i', video_path,
                    '-i', audio_path,
                    '-c:v', 'libx265',
                    '-crf', '28',
                    '-preset', 'medium',
                    '-vf', 'scale=-2:720',
                    '-c:a', 'aac',
                    '-b:a', '96k',
                    '-map', '0:v:0',
                    '-map', '1:a:0',
                    '-movflags', '+faststart',
                    '-avoid_negative_ts', 'make_zero',
                    # Replace error level with stats
                    '-stats',
                    '-progress', 'pipe:1',
                    '-y',
                    output_path
                ]

            logger.info(f"Running ffmpeg command: {' '.join(cmd)}")

            # Get absolute path to ffmpeg on Windows to avoid PATH issues
            if os.name == 'nt':  # Windows
                ffmpeg_path = shutil.which("ffmpeg")
                if ffmpeg_path:
                    cmd[0] = ffmpeg_path
                    logger.info(f"Using absolute FFmpeg path: {ffmpeg_path}")

            # Handle Windows path issues with quotes for spaces
            if os.name == 'nt':
                for i, arg in enumerate(cmd):
                    if isinstance(arg, str) and os.path.exists(arg) and ' ' in arg:
                        logger.info(f"Path with spaces detected: {arg}")
                        
            # Log the command for debugging
            if os.name == 'nt':
                logger.info(f"Windows command list: {cmd}")

            # Run ffmpeg with progress monitoring in a thread pool
            try:
                # Create environment with explicit PATH to ensure ffmpeg is found
                env = os.environ.copy()
                if os.name == 'nt' and 'C:\\ffmpeg\\bin' not in env.get('PATH', ''):
                    if 'PATH' in env:
                        env['PATH'] = f"C:\\ffmpeg\\bin;{env['PATH']}"
                    else:
                        env['PATH'] = "C:\\ffmpeg\\bin"
                
                # Use the standard subprocess module in a thread pool executor
                import concurrent.futures
                import re
                from datetime import datetime
                
                def run_ffmpeg_subprocess_with_progress():
                    try:
                        # Run the FFmpeg command with real-time output monitoring
                        process = subprocess.Popen(
                            cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            env=env,
                            cwd=temp_dir,
                            text=True,
                            bufsize=1,  # Line buffered
                            universal_newlines=True,
                        )
                        
                        stdout_lines = []
                        stderr_lines = []
                        
                        # Variables to track progress
                        start_time = datetime.now()
                        frame_count = 0
                        total_frames = None
                        fps = 0
                        progress = 0
                        time_position = "00:00:00"
                        duration = None
                        speed = "0x"
                        last_update_time = datetime.now()
                        
                        # Function to print progress update
                        def print_progress_update():
                            elapsed = (datetime.now() - start_time).total_seconds()
                            print(f"\r[FFmpeg] {time_position}", end='')
                            
                            if duration:
                                percent = min(100, int(progress * 100))
                                progress_bar = f" [{percent:3d}%] "
                                print(f"{progress_bar}", end='')
                            
                            if fps > 0:
                                print(f" {fps:.1f} fps", end='')
                            
                            if speed:
                                print(f" {speed}", end='')
                            
                            if frame_count:
                                print(f" [{frame_count} frames]", end='')
                                
                            print("     ", end='', flush=True)
                        
                        # Process stderr for FFmpeg progress info
                        while process.poll() is None:
                            # Check stderr for progress info
                            if process.stderr:
                                stderr_line = process.stderr.readline()
                                if stderr_line:
                                    stderr_lines.append(stderr_line)
                                    
                                    # Parse frame info
                                    frame_match = re.search(r'frame=\s*(\d+)', stderr_line)
                                    if frame_match:
                                        frame_count = int(frame_match.group(1))
                                    
                                    # Parse FPS
                                    fps_match = re.search(r'fps=\s*(\d+\.?\d*)', stderr_line)
                                    if fps_match:
                                        fps = float(fps_match.group(1))
                                        
                                    # Parse time position
                                    time_match = re.search(r'time=\s*(\d+:\d+:\d+\.\d+)', stderr_line)
                                    if time_match:
                                        time_position = time_match.group(1)
                                        
                                        # Try to calculate progress if we have duration
                                        if not duration:
                                            # Try to parse duration
                                            duration_match = re.search(r'Duration: (\d+:\d+:\d+\.\d+)', '\n'.join(stderr_lines))
                                            if duration_match:
                                                duration = duration_match.group(1)
                                        
                                        if duration:
                                            # Convert time strings to seconds
                                            def time_to_seconds(time_str):
                                                h, m, s = time_str.split(':')
                                                return int(h) * 3600 + int(m) * 60 + float(s)
                                            
                                            pos_seconds = time_to_seconds(time_position.split('.')[0])
                                            dur_seconds = time_to_seconds(duration.split('.')[0])
                                            progress = pos_seconds / dur_seconds if dur_seconds > 0 else 0
                                    
                                    # Parse speed
                                    speed_match = re.search(r'speed=\s*(\d+\.?\d*x)', stderr_line)
                                    if speed_match:
                                        speed = speed_match.group(1)
                                    
                                    # Only update UI at most once every 0.5 seconds to avoid excessive output
                                    current_time = datetime.now()
                                    if (current_time - last_update_time).total_seconds() >= 0.5:
                                        print_progress_update()
                                        last_update_time = current_time
                            
                            # Check stdout
                            if process.stdout:
                                stdout_line = process.stdout.readline()
                                if stdout_line:
                                    stdout_lines.append(stdout_line)
                                    
                                    # Parse progress information from pipe format
                                    if '=' in stdout_line:
                                        key, value = stdout_line.strip().split('=', 1)
                                        if key == 'frame':
                                            frame_count = int(value)
                                        elif key == 'fps':
                                            fps = float(value)
                                        elif key == 'out_time_ms':
                                            ms = int(value)
                                            seconds = ms / 1000000
                                            h = int(seconds // 3600)
                                            m = int((seconds % 3600) // 60)
                                            s = seconds % 60
                                            time_position = f"{h:02d}:{m:02d}:{s:06.3f}"
                                        elif key == 'progress' and value == 'end':
                                            progress = 1.0  # 100% complete
                                            print_progress_update()
                        
                        # Get final outputs
                        stdout_remainder, stderr_remainder = process.communicate()
                        
                        if stdout_remainder:
                            stdout_lines.append(stdout_remainder)
                        if stderr_remainder:
                            stderr_lines.append(stderr_remainder)
                        
                        # Print final progress
                        print("\n[FFmpeg] Conversion complete!")
                        
                        return process.returncode, ''.join(stdout_lines), ''.join(stderr_lines)
                    except Exception as e:
                        logger.error(f"Error in ffmpeg subprocess thread: {str(e)}")
                        return -1, None, str(e)
                
                # Execute in thread pool with timeout
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    # Submit the task to the thread pool
                    future = pool.submit(run_ffmpeg_subprocess_with_progress)
                    
                    try:
                        # Wait for the result with a timeout
                        returncode, stdout_data, stderr_data = await asyncio.get_event_loop().run_in_executor(
                            None, 
                            lambda: future.result(timeout=1800)  # 30 minutes timeout
                        )
                    except concurrent.futures.TimeoutError:
                        logger.error("FFmpeg processing timed out")
                        # We can't directly terminate the process from here
                        # The future will be canceled when the pool is shutdown
                        return {'success': False, 'error': 'Video processing timed out (30 minutes limit)'}

            except FileNotFoundError as e:
                logger.error(f"FFmpeg executable not found: {str(e)}", exc_info=True)
                return {'success': False, 'error': f'FFmpeg not found. Error: {str(e)}'}
            except PermissionError as e:
                logger.error(f"Permission denied when running FFmpeg: {str(e)}", exc_info=True)
                return {'success': False, 'error': f'Permission denied when running FFmpeg: {str(e)}'}
            except Exception as e:
                logger.error(f"Failed to start FFmpeg process: {str(e)}", exc_info=True)
                error_type = type(e).__name__
                error_msg = str(e)
                
                return {'success': False, 'error': f'Failed to start video processing: {error_type}: {error_msg}'}

            # Process the output 
            stdout_text = stdout_data.decode('utf-8', errors='ignore') if stdout_data else ""
            stderr_text = stderr_data.decode('utf-8', errors='ignore') if stderr_data else ""

            logger.info(f"FFmpeg completed with return code: {returncode}")

            # Always log stderr if it exists (even for successful runs)
            if stderr_text.strip():
                logger.info(f"FFmpeg stderr output: {stderr_text}")

            if returncode != 0:
                logger.error(f"FFmpeg failed with return code {returncode}")
                logger.error(f"FFmpeg full stderr: {stderr_text}")
                logger.error(f"FFmpeg full stdout: {stdout_text}")
                
                # Check for specific ffmpeg errors
                stderr_lower = stderr_text.lower()
                if 'libx265' in stderr_lower and ('not found' in stderr_lower or 'unknown encoder' in stderr_lower):
                    return {'success': False, 'error': 'HEVC encoder (libx265) not available. Please install ffmpeg with libx265 support.'}
                elif 'no such file or directory' in stderr_lower:
                    return {'success': False, 'error': f'Input file not found: {video_path}'}
                elif 'invalid data found' in stderr_lower or 'moov atom not found' in stderr_lower:
                    return {'success': False, 'error': 'Corrupted or incomplete video file'}
                elif 'no space left' in stderr_lower:
                    return {'success': False, 'error': 'Insufficient disk space'}
                elif 'permission denied' in stderr_lower:
                    return {'success': False, 'error': 'Permission denied accessing files'}
                elif 'codec not currently supported' in stderr_lower:
                    return {'success': False, 'error': 'Video codec not supported'}
                elif 'conversion failed' in stderr_lower:
                    return {'success': False, 'error': 'Video conversion failed - format may be unsupported'}
                elif stderr_text.strip():
                    return {'success': False, 'error': f'Video processing failed: {stderr_text[:200]}'}
                else:
                    return {'success': False, 'error': f'Video processing failed with return code {returncode}'}

            # Check if output file was created
            if not os.path.exists(output_path):
                return {'success': False, 'error': 'Processed video file was not created'}

            # Verify output file is valid
            file_size = os.path.getsize(output_path)
            if file_size < 1024:  # Less than 1KB is likely invalid
                return {'success': False, 'error': f'Output video file appears to be corrupted (size: {file_size} bytes)'}

            logger.info(f"Successfully processed video: {output_path} ({file_size} bytes)")

            return {
                'success': True,
                'output_path': output_path
            }
            
        except Exception as e:
            logger.error(f"Error processing video: {str(e)}", exc_info=True)
            return {'success': False, 'error': f'Processing failed: {str(e)}'}

    async def upload_to_cloudinary(self, video_path: str, video_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Upload processed video to Cloudinary with enhanced error handling
        """
        try:
            # Generate public ID
            video_id = video_info.get('id', 'unknown')
            # Sanitize video ID for use as filename
            import re
            video_id = re.sub(r'[^a-zA-Z0-9_-]', '_', video_id)
            public_id = f"youtube_hevc_720p/{video_id}"
            
            logger.info(f"Uploading to Cloudinary: {public_id}")
            
            # Check file size before upload
            file_size = os.path.getsize(video_path)
            max_size = self.settings.max_video_size_mb * 1024 * 1024
            
            if file_size > max_size:
                return {
                    'success': False, 
                    'error': f'Video file too large ({file_size / 1024 / 1024:.1f}MB > {self.settings.max_video_size_mb}MB)'
                }
            
            # Verify file is readable
            try:
                with open(video_path, 'rb') as f:
                    f.read(1024)  # Try to read first 1KB
            except Exception as e:
                return {'success': False, 'error': f'Cannot read video file: {str(e)}'}
            
            # Upload video with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    upload_result = cloudinary.uploader.upload(
                        video_path,
                        resource_type="video",
                        public_id=public_id,
                        folder="youtube_hevc_720p",
                        overwrite=True,
                        notification_url=None,
                        eager_async=False,
                        quality="auto",
                        timeout=600,  # 10 minute timeout
                        chunk_size=6000000  # 6MB chunks for large files
                    )
                    
                    if not upload_result.get('secure_url'):
                        if attempt < max_retries - 1:
                            logger.warning(f"Upload attempt {attempt + 1} failed, retrying...")
                            await asyncio.sleep(5)
                            continue
                        return {'success': False, 'error': 'Upload failed - no secure URL returned'}
                    
                    logger.info(f"Successfully uploaded to Cloudinary: {upload_result['secure_url']}")
                    
                    return {
                        'success': True,
                        'public_url': upload_result['secure_url'],
                        'filesize': upload_result.get('bytes'),
                        'cloudinary_id': upload_result.get('public_id')
                    }
                    
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"Upload attempt {attempt + 1} failed: {str(e)}, retrying...")
                        await asyncio.sleep(5)
                        continue
                    raise
            
        except Exception as e:
            error_msg = str(e)
            if 'timeout' in error_msg.lower():
                return {'success': False, 'error': 'Upload timed out - file may be too large'}
            elif 'unauthorized' in error_msg.lower():
                return {'success': False, 'error': 'Cloudinary authentication failed'}
            elif 'invalid' in error_msg.lower() and 'credentials' in error_msg.lower():
                return {'success': False, 'error': 'Invalid Cloudinary credentials'}
            elif 'quota' in error_msg.lower():
                return {'success': False, 'error': 'Cloudinary quota exceeded'}
            elif 'file size' in error_msg.lower():
                return {'success': False, 'error': 'File too large for Cloudinary'}
            else:
                logger.error(f"Error uploading to Cloudinary: {str(e)}")
                return {'success': False, 'error': f'Upload failed: {str(e)}'}

    async def cleanup_temp_dir(self, temp_dir: str):
        """
        Clean up temporary directory with enhanced error handling
        """
        try:
            import shutil
            # Wait a bit to ensure all file handles are closed
            await asyncio.sleep(1)
            shutil.rmtree(temp_dir)
            logger.info(f"Cleaned up temp directory: {temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp directory: {str(e)}")
            # Try alternative cleanup method
            try:
                import os
                for root, dirs, files in os.walk(temp_dir, topdown=False):
                    for file in files:
                        try:
                            os.remove(os.path.join(root, file))
                        except:
                            pass
                    for dir in dirs:
                        try:
                            os.rmdir(os.path.join(root, dir))
                        except:
                            pass
                os.rmdir(temp_dir)
                logger.info(f"Alternative cleanup successful: {temp_dir}")
            except Exception as e2:
                logger.error(f"All cleanup methods failed: {str(e2)}")
