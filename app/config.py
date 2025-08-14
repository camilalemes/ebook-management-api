import os
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

from .exceptions import ConfigurationException

# Get project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# Load .env file explicitly
load_dotenv(PROJECT_ROOT / ".env")


class Settings(BaseSettings):
    """Application settings with validation and defaults."""
    
    # Calibre Configuration (deprecated - use LIBRARY_PATHS instead)
    CALIBRE_CMD_PATH: str = Field(
        default="calibredb",
        description="Path to calibredb executable"
    )
    LIBRARY_PATHS: str = Field(
        default="",
        description="Comma-separated paths to library locations (read-only)"
    )
    
    # API Configuration
    API_HOST: str = Field(default="0.0.0.0", description="API host")
    API_PORT: int = Field(default=8000, ge=1, le=65535, description="API port")
    API_DEBUG: bool = Field(default=False, description="Enable debug mode")
    API_VERSION: str = Field(default="1.0.0", description="API version")
    
    # Logging Configuration
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    LOG_FILE: Optional[str] = Field(default=None, description="Log file path")
    LOG_ROTATION_SIZE: int = Field(
        default=10 * 1024 * 1024,  # 10MB
        ge=1024 * 1024,  # Minimum 1MB
        description="Log file rotation size in bytes"
    )
    LOG_BACKUP_COUNT: int = Field(
        default=5,
        ge=1,
        description="Number of backup log files to keep"
    )
    
    # CORS Configuration
    CORS_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:4200",
        description="Comma-separated list of allowed CORS origins"
    )
    
    # Sync Configuration
    SYNC_BATCH_SIZE: int = Field(
        default=100,
        ge=1,
        description="Number of files to process in each sync batch"
    )
    SYNC_TIMEOUT: int = Field(
        default=3600,  # 1 hour
        ge=60,  # Minimum 1 minute
        description="Sync operation timeout in seconds"
    )
    
    # Cache Configuration
    CACHE_TTL: int = Field(
        default=300,  # 5 minutes
        ge=60,  # Minimum 1 minute
        description="Cache TTL in seconds"
    )
    
    # File Upload Configuration
    MAX_UPLOAD_SIZE: int = Field(
        default=100 * 1024 * 1024,  # 100MB
        ge=1024 * 1024,  # Minimum 1MB
        description="Maximum file upload size in bytes"
    )
    ALLOWED_FILE_EXTENSIONS: str = Field(
        default=".epub,.pdf,.mobi,.azw,.azw3,.txt,.rtf,.doc,.docx,.fb2",
        description="Comma-separated list of allowed file extensions"
    )
    
    
    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ConfigurationException(
                detail=f"Invalid log level: {v}. Must be one of {valid_levels}",
                config_key="LOG_LEVEL"
            )
        return v.upper()

    @property
    def library_paths_list(self) -> List[str]:
        """Convert comma-separated paths to a list of validated paths."""
        if not self.LIBRARY_PATHS:
            return []
        
        paths = []
        for path_str in self.LIBRARY_PATHS.split(","):
            path_str = path_str.strip()
            if path_str:
                path = Path(path_str)
                if path.exists() and path.is_dir():
                    paths.append(str(path.absolute()))
                else:
                    # Log warning but don't fail - library paths might be created later
                    import logging
                    logging.getLogger(__name__).warning(
                        f"Library path does not exist or is not a directory: {path_str}"
                    )
        
        return paths
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Convert comma-separated CORS origins to a list."""
        if not self.CORS_ORIGINS:
            return ["*"]  # Allow all origins if none specified
        
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
    
    @property
    def allowed_extensions_list(self) -> List[str]:
        """Convert comma-separated file extensions to a list."""
        if not self.ALLOWED_FILE_EXTENSIONS:
            return []
        
        extensions = []
        for ext in self.ALLOWED_FILE_EXTENSIONS.split(","):
            ext = ext.strip().lower()
            if ext and not ext.startswith("."):
                ext = f".{ext}"
            if ext:
                extensions.append(ext)
        
        return extensions

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore"
    }


def get_settings() -> Settings:
    """Get application settings with caching."""
    return Settings()


# Create global settings instance
settings = get_settings()