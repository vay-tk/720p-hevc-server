import os
from typing import Optional
try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings

class Settings(BaseSettings):
    # Cloudinary configuration
    cloudinary_cloud_name: Optional[str] = None
    cloudinary_api_key: Optional[str] = None
    cloudinary_api_secret: Optional[str] = None
    
    # Application configuration
    app_name: str = "YouTube Video Processor"
    debug: bool = False
    max_video_size_mb: int = 500
    temp_dir: Optional[str] = None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Validate required Cloudinary settings
        if not all([self.cloudinary_cloud_name, self.cloudinary_api_key, self.cloudinary_api_secret]):
            missing = []
            if not self.cloudinary_cloud_name:
                missing.append("CLOUDINARY_CLOUD_NAME")
            if not self.cloudinary_api_key:
                missing.append("CLOUDINARY_API_KEY")
            if not self.cloudinary_api_secret:
                missing.append("CLOUDINARY_API_SECRET")
            
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

# Singleton pattern for settings
_settings: Optional[Settings] = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings