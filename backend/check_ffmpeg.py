#!/usr/bin/env python3
"""
Check FFmpeg capabilities and resource availability.
This script helps determine the appropriate encoding settings
based on the available system resources.
"""

import os
import sys
import json
import subprocess
import platform
import logging
from typing import Dict, Any, Tuple, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ffmpeg_checker")

def get_system_info() -> Dict[str, Any]:
    """Get information about the system resources"""
    info = {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "is_docker": os.path.exists("/.dockerenv") or os.path.exists("/run/.containerenv"),
    }
    
    # Try to get CPU info
    try:
        if info["platform"] == "Linux":
            # Get CPU count
            cpu_count = 0
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('processor'):
                        cpu_count += 1
            info["cpu_count"] = cpu_count
            
            # Get memory info
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if line.startswith('MemTotal'):
                        mem_total = int(line.split()[1]) / 1024  # Convert to MB
                        info["memory_mb"] = mem_total
                        break
        else:
            import multiprocessing
            info["cpu_count"] = multiprocessing.cpu_count()
            
            # Memory on Windows/Mac
            import psutil
            info["memory_mb"] = psutil.virtual_memory().total / (1024 * 1024)
    except Exception as e:
        logger.warning(f"Error getting system resources: {e}")
        info["cpu_count"] = "unknown"
        info["memory_mb"] = "unknown"
    
    return info

def check_ffmpeg() -> Dict[str, Any]:
    """Check ffmpeg availability and capabilities"""
    result = {
        "available": False,
        "version": None,
        "encoders": [],
        "hevc_support": False,
        "h264_support": False,
        "aac_support": False,
    }
    
    try:
        # Check if ffmpeg is available
        version_process = subprocess.run(
            ["ffmpeg", "-version"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True,
            timeout=5
        )
        
        if version_process.returncode == 0:
            result["available"] = True
            version_output = version_process.stdout.splitlines()[0]
            result["version"] = version_output
            
            # Check encoders
            encoders_process = subprocess.run(
                ["ffmpeg", "-encoders"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True,
                timeout=5
            )
            
            if encoders_process.returncode == 0:
                encoders_output = encoders_process.stdout
                # Check for specific encoders
                result["hevc_support"] = "libx265" in encoders_output
                result["h264_support"] = "libx264" in encoders_output
                result["aac_support"] = " aac" in encoders_output or "libfdk_aac" in encoders_output
                
                # Extract all video encoders
                for line in encoders_output.splitlines():
                    if " V" in line[:10]:  # Video encoder line starts with "V"
                        encoder = line.split()[1]
                        result["encoders"].append(encoder)
            
            # Run a quick encoding test to measure performance
            result.update(run_encoding_test())
            
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        logger.error(f"Error checking FFmpeg: {e}")
    
    return result

def run_encoding_test() -> Dict[str, Any]:
    """Run a quick encoding test to measure performance"""
    results = {
        "performance_test": "not_run",
        "fps_h264": None,
        "fps_hevc": None,
        "recommended_preset": "medium",
        "recommended_codec": "libx264",
        "resource_constrained": False
    }
    
    try:
        # Create a 5-second test video using FFmpeg
        test_input = "-f lavfi -i testsrc=duration=1:size=1280x720:rate=30"
        
        # H.264 test
        h264_cmd = f"ffmpeg {test_input} -c:v libx264 -preset ultrafast -f null -"
        h264_process = subprocess.run(
            h264_cmd, 
            shell=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True,
            timeout=10
        )
        
        h264_fps = None
        if h264_process.returncode == 0:
            # Extract FPS from output
            for line in h264_process.stderr.splitlines():
                if "fps=" in line and "time=" in line:
                    fps_parts = line.split("fps=")[1].split()[0]
                    try:
                        h264_fps = float(fps_parts)
                    except ValueError:
                        pass
        
        # HEVC test (if available)
        hevc_fps = None
        if results["hevc_support"]:
            hevc_cmd = f"ffmpeg {test_input} -c:v libx265 -preset ultrafast -f null -"
            hevc_process = subprocess.run(
                hevc_cmd, 
                shell=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True,
                timeout=15
            )
            
            if hevc_process.returncode == 0:
                for line in hevc_process.stderr.splitlines():
                    if "fps=" in line and "time=" in line:
                        fps_parts = line.split("fps=")[1].split()[0]
                        try:
                            hevc_fps = float(fps_parts)
                        except ValueError:
                            pass
        
        results["fps_h264"] = h264_fps
        results["fps_hevc"] = hevc_fps
        results["performance_test"] = "completed"
        
        # Analyze results and provide recommendations
        if h264_fps is not None:
            if h264_fps < 15:
                results["resource_constrained"] = True
                results["recommended_preset"] = "ultrafast" 
                results["recommended_codec"] = "libx264"
            elif h264_fps < 30:
                results["recommended_preset"] = "veryfast"
                results["recommended_codec"] = "libx264"
            elif h264_fps < 60:
                results["recommended_preset"] = "fast" 
                results["recommended_codec"] = "libx264" if not results["hevc_support"] or not hevc_fps or hevc_fps < 15 else "libx265"
            else:
                results["recommended_preset"] = "medium"
                results["recommended_codec"] = "libx264" if not results["hevc_support"] or not hevc_fps or hevc_fps < 30 else "libx265"
        
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        logger.error(f"Error running encoding test: {e}")
        results["performance_test"] = f"failed: {str(e)}"
    
    return results

def get_recommended_ffmpeg_settings() -> Dict[str, Any]:
    """Get recommended FFmpeg settings based on the system capabilities"""
    system_info = get_system_info()
    ffmpeg_info = check_ffmpeg()
    
    settings = {
        "system": system_info,
        "ffmpeg": ffmpeg_info,
        "recommendations": {}
    }
    
    # Set recommended settings
    if not ffmpeg_info["available"]:
        settings["recommendations"] = {
            "status": "ffmpeg_not_available",
            "message": "FFmpeg not found. Please install FFmpeg."
        }
        return settings
    
    # Start with a baseline recommendation
    settings["recommendations"] = {
        "status": "ok",
        "codec": ffmpeg_info.get("recommended_codec", "libx264"),
        "preset": ffmpeg_info.get("recommended_preset", "medium"),
        "crf": 23 if ffmpeg_info.get("recommended_codec") == "libx264" else 28,
        "audio_codec": "aac",
        "audio_bitrate": "96k",
        "scale": "-2:720",  # maintain aspect ratio with 720p height
        "threads": min(2, system_info.get("cpu_count", 2) if isinstance(system_info.get("cpu_count"), int) else 2),
    }
    
    # Adjust for resource constraints
    if ffmpeg_info.get("resource_constrained", False):
        settings["recommendations"].update({
            "status": "resource_constrained",
            "message": "System resources are limited. Using optimized settings.",
            "codec": "libx264",  # H.264 is faster than HEVC
            "preset": "ultrafast",  # Fastest preset
            "crf": 28,  # Lower quality for speed
            "scale": "-2:480",  # Lower resolution
            "threads": 1,  # Limit threads
        })
    
    # Check if in a container environment
    if system_info.get("is_docker", False):
        if settings["recommendations"]["status"] == "ok":
            settings["recommendations"]["status"] = "container_environment"
            settings["recommendations"]["message"] = "Running in container environment. Adjusted settings for better performance."
            settings["recommendations"]["preset"] = "veryfast"
    
    return settings

def main():
    """Main function to print information about FFmpeg capabilities"""
    print("FFmpeg Capability Checker")
    print("========================")
    
    settings = get_recommended_ffmpeg_settings()
    
    # Print system info
    print("\nSystem Information:")
    print(f"  Platform: {settings['system']['platform']} {settings['system']['platform_version']}")
    print(f"  Architecture: {settings['system']['architecture']}")
    cpu_count = settings['system'].get('cpu_count')
    print(f"  CPU Count: {cpu_count if isinstance(cpu_count, int) else 'Unknown'}")
    memory = settings['system'].get('memory_mb')
    print(f"  Memory: {int(memory) if isinstance(memory, (int, float)) else 'Unknown'} MB")
    print(f"  Container Environment: {'Yes' if settings['system'].get('is_docker') else 'No'}")
    
    # Print FFmpeg info
    print("\nFFmpeg Information:")
    if settings['ffmpeg']['available']:
        print(f"  Version: {settings['ffmpeg']['version']}")
        print(f"  HEVC/H.265 Support: {'Yes' if settings['ffmpeg']['hevc_support'] else 'No'}")
        print(f"  H.264 Support: {'Yes' if settings['ffmpeg']['h264_support'] else 'No'}")
        print(f"  AAC Support: {'Yes' if settings['ffmpeg']['aac_support'] else 'No'}")
        
        if settings['ffmpeg']['performance_test'] == "completed":
            print("\nPerformance Test Results:")
            print(f"  H.264 Encoding Speed: {settings['ffmpeg']['fps_h264']:.1f} fps")
            if settings['ffmpeg']['fps_hevc'] is not None:
                print(f"  HEVC Encoding Speed: {settings['ffmpeg']['fps_hevc']:.1f} fps")
    else:
        print("  FFmpeg not available on this system")
    
    # Print recommendations
    print("\nRecommended FFmpeg Settings:")
    print(f"  Status: {settings['recommendations']['status']}")
    if "message" in settings['recommendations']:
        print(f"  Message: {settings['recommendations']['message']}")
    print(f"  Video Codec: {settings['recommendations']['codec']}")
    print(f"  Preset: {settings['recommendations']['preset']}")
    print(f"  CRF: {settings['recommendations']['crf']}")
    print(f"  Scale: {settings['recommendations']['scale']}")
    print(f"  Threads: {settings['recommendations']['threads']}")
    print(f"  Audio Codec: {settings['recommendations']['audio_codec']}")
    print(f"  Audio Bitrate: {settings['recommendations']['audio_bitrate']}")
    
    # Sample command
    print("\nSample FFmpeg Command:")
    print(f"""  ffmpeg -i input.mp4 -c:v {settings['recommendations']['codec']} \\
    -preset {settings['recommendations']['preset']} \\
    -crf {settings['recommendations']['crf']} \\
    -vf scale={settings['recommendations']['scale']} \\
    -c:a {settings['recommendations']['audio_codec']} \\
    -b:a {settings['recommendations']['audio_bitrate']} \\
    -threads {settings['recommendations']['threads']} \\
    -movflags +faststart output.mp4""")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
