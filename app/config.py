import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Get project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# Load .env file explicitly
load_dotenv(PROJECT_ROOT / ".env")


class Settings(BaseSettings):
    CALIBRE_LIBRARY_PATH: str
    REPLICA_PATHS: str

    @property
    def replica_paths_list(self) -> List[str]:
        """Convert comma-separated paths to a list"""
        if not self.REPLICA_PATHS:
            return []
        return [path.strip() for path in self.REPLICA_PATHS.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()