"""
YouTube-specific utilities for dealing with bot protection and other issues.
"""
import os
import time
import random
import logging
import subprocess
import tempfile
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# Collection of user agents from modern browsers across different platforms
USER_AGENTS = [
    # Desktop browsers - Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
    # Desktop browsers - macOS
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    # Mobile browsers - iOS
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (iPad; CPU OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/120.0.6099.119 Mobile/15E148 Safari/604.1',
    # Mobile browsers - Android
    'Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.144 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.144 Mobile Safari/537.36',
    # TV browsers
    'Mozilla/5.0 (Linux; Android 10; MIBOX4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Mobile Safari/537.36',
    'Mozilla/5.0 (SMART-TV; Linux; Tizen 7.0) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/20.0 Chrome/106.0.5249.0 TV Safari/537.36'
]

# Collection of YouTube-friendly referrers that won't trigger bot detection
REFERRERS = [
    'https://www.google.com/search?q=youtube+videos',
    'https://www.google.com/',
    'https://www.bing.com/search?q=youtube+videos',
    'https://www.facebook.com/',
    'https://www.reddit.com/',
    'https://www.twitter.com/',
    'https://www.instagram.com/',
    'https://news.ycombinator.com/',
    'https://www.youtube.com/',
    'https://m.youtube.com/'
]

def get_random_user_agent() -> str:
    """Get a random user agent from the list"""
    return random.choice(USER_AGENTS)

def get_random_referrer() -> str:
    """Get a random referrer from the list"""
    return random.choice(REFERRERS)

def get_http_headers(is_mobile: bool = False) -> Dict[str, str]:
    """
    Generate random HTTP headers to help bypass bot detection
    
    Args:
        is_mobile: Whether to use mobile-specific headers
    """
    headers = {
        'User-Agent': random.choice([ua for ua in USER_AGENTS if ('Mobile' in ua) == is_mobile]),
        'Accept-Language': random.choice(['en-US,en;q=0.9', 'en-GB,en;q=0.9', 'en;q=0.9']),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': random.choice(['none', 'same-origin']),
        'Sec-Fetch-User': '?1',
        'Cache-Control': random.choice(['max-age=0', 'no-cache']),
        'Referer': get_random_referrer()
    }
    
    # Add some randomness to make the headers look more organic
    if random.random() < 0.5:
        headers['DNT'] = '1'
    
    if random.random() < 0.3:
        headers['TE'] = 'Trailers'
        
    return headers

def get_additional_yt_dlp_options() -> Dict[str, Any]:
    """
    Get additional yt-dlp options to help bypass YouTube bot detection
    """
    options = {
        # Randomized sleep intervals
        'sleep_interval': random.uniform(1.0, 3.0),
        'max_sleep_interval': random.uniform(5.0, 10.0),
        'sleep_interval_requests': 1,
        
        # Use a random player client
        'extractor_args': {
            'youtube': {
                'player_client': random.choice([
                    ['android', 'web'],
                    ['web', 'ios'],
                    ['android', 'ios'],
                    ['web', 'android', 'ios']
                ]),
                'player_skip': [],
                # Randomly alternate between these hosts
                'innertube_host': random.choice([
                    ['www.youtube.com', 'youtubei.googleapis.com'],
                    ['youtubei.googleapis.com', 'www.youtube.com'],
                    ['m.youtube.com', 'youtubei.googleapis.com']
                ]),
                # Recent innertube keys
                'innertube_key': random.choice([
                    ['AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8'],
                    ['AIzaSyB-63vPrdThhKuerbB2N_l7Kwwcxj6yUAc'],
                    ['AIzaSyDCU8hByM-4DrUqRUYnGn-3llEO78bcxq8']
                ])
            }
        },
        
        # Randomize timeouts to appear more human-like
        'socket_timeout': random.randint(20, 40),
        'retries': random.randint(3, 5),
        
        # Browser fingerprinting avoidance
        'noprogress': random.choice([True, False]),
        
        # Misc options to appear more like a browser
        'add_header': [f'Origin:{get_random_referrer()}'],
    }
    
    return options

def generate_cookies_file(output_path: str) -> bool:
    """
    Generate a simple cookies file that might help with basic authentication.
    Note: This is not a full solution but may help in some cases
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        content = """# Netscape HTTP Cookie File
# https://curl.se/docs/http-cookies.html
# This is a generated file - YouTube cookies require actual authentication!

.youtube.com	TRUE	/	TRUE	2147483647	CONSENT	YES+cb.20220301-17-p0.en+FX+200

# Note: For real YouTube access without bot detection,
# you need to export valid cookies from a real browser session.
# See: https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp
"""
        with open(output_path, 'w') as f:
            f.write(content)
        return True
    except Exception as e:
        logger.error(f"Failed to generate cookies file: {e}")
        return False

def validate_youtube_cookies(cookie_file_path: str) -> Tuple[bool, str]:
    """
    Check if YouTube cookies appear to be valid
    
    Args:
        cookie_file_path: Path to the cookies.txt file
    
    Returns:
        Tuple[bool, str]: (is_valid, message)
    """
    if not os.path.exists(cookie_file_path):
        return False, "Cookies file doesn't exist"
    
    try:
        with open(cookie_file_path, 'r') as f:
            content = f.read()
            
        # Check if file is empty or just comments
        lines = [line.strip() for line in content.split('\n') if line.strip() and not line.strip().startswith('#')]
        if not lines:
            return False, "Cookies file is empty or contains only comments"
        
        # Check for important YouTube cookies
        important_cookies = ['__Secure-1PSID', '__Secure-3PSID', 'LOGIN_INFO', 'VISITOR_INFO1_LIVE']
        found_cookies = [cookie for cookie in important_cookies if any(cookie in line for line in lines)]
        
        if not found_cookies:
            return False, "No critical YouTube cookies found"
        
        # Check if cookies file contains all needed cookies
        if len(found_cookies) < 3:
            return False, f"Only {len(found_cookies)}/{len(important_cookies)} critical cookies found"
            
        return True, f"Found {len(found_cookies)}/{len(important_cookies)} critical cookies"
        
    except Exception as e:
        return False, f"Error validating cookies: {e}"

def check_youtube_connectivity() -> Dict[str, Any]:
    """
    Check if YouTube is accessible and if bot detection is active
    
    Returns:
        Dict with status information
    """
    result = {
        "accessible": False,
        "bot_detection_active": True,
        "error": None,
        "message": "",
    }
    
    try:
        # Create a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            cookie_file = os.path.join(os.path.dirname(__file__), "cookies.txt")
            cookies_valid, cookies_msg = validate_youtube_cookies(cookie_file)
            
            # Try to fetch YouTube homepage
            import yt_dlp
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'skip_download': True,
                'dumpjson': True,
                'noprogress': True,
                'http_headers': get_http_headers(),
                'cookiefile': cookie_file if cookies_valid else None,
            }
            
            # Update with additional options
            ydl_opts.update(get_additional_yt_dlp_options())
            
            # Try to extract info from a popular video that's unlikely to be taken down
            test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Astley - Never Gonna Give You Up
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    info = ydl.extract_info(test_url, download=False)
                    result["accessible"] = True
                    result["bot_detection_active"] = False
                    result["message"] = "YouTube is accessible without bot detection"
                except yt_dlp.utils.DownloadError as e:
                    error_msg = str(e).lower()
                    result["accessible"] = True  # We could at least connect
                    
                    if any(phrase in error_msg for phrase in [
                        'sign in to confirm', 'not a bot', 'captcha', 'robot'
                    ]):
                        result["bot_detection_active"] = True
                        result["message"] = f"YouTube bot detection is active: {str(e)}"
                    else:
                        result["bot_detection_active"] = False
                        result["message"] = f"YouTube access error (non-bot): {str(e)}"
                except Exception as e:
                    result["error"] = str(e)
                    result["message"] = f"Failed to check YouTube: {str(e)}"
    
    except Exception as e:
        result["error"] = str(e)
        result["message"] = f"Connection test failed: {str(e)}"
    
    # Add cookie status
    cookie_file = os.path.join(os.path.dirname(__file__), "cookies.txt")
    cookies_valid, cookies_msg = validate_youtube_cookies(cookie_file)
    result["cookies_valid"] = cookies_valid
    result["cookies_message"] = cookies_msg
    
    return result
