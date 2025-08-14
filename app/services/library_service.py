# app/services/library_service.py
"""Service for reading library ebook collections."""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

from ..config import settings


logger = logging.getLogger(__name__)


class LibraryService:
    """Service for reading ebook files from library locations."""
    
    def __init__(self):
        self.library_paths = self._get_valid_library_paths()
    
    def _get_valid_library_paths(self) -> List[str]:
        """Get list of valid library paths."""
        valid_paths = []
        for path in settings.library_paths_list:
            if Path(path).exists() and Path(path).is_dir():
                valid_paths.append(path)
            else:
                logger.warning(f"Library path not accessible: {path}")
        return valid_paths
    
    def get_library_files(self, library_path: str) -> List[Dict[str, Any]]:
        """Get list of ebook files from library path."""
        books = []
        
        if not os.path.exists(library_path):
            logger.warning(f"Library path does not exist: {library_path}")
            return books
        
        try:
            # Scan all files in library directory
            for filename in sorted(os.listdir(library_path)):
                file_path = os.path.join(library_path, filename)
                
                # Skip directories and non-ebook files
                if os.path.isdir(file_path):
                    continue
                
                # Skip system files
                if filename.startswith('.') or filename in ['metadata.db', 'notes.db']:
                    continue
                
                # Get file extension
                _, ext = os.path.splitext(filename)
                ext = ext.lower()
                
                # Only include ebook formats
                if ext not in ['.epub', '.pdf', '.mobi', '.azw', '.azw3', '.txt', '.rtf', '.doc', '.docx', '.fb2']:
                    continue
                
                try:
                    stat = os.stat(file_path)
                    
                    # Parse title and author from filename (format: "Title - Author.ext")
                    base_name = os.path.splitext(filename)[0]
                    if ' - ' in base_name:
                        title, author = base_name.split(' - ', 1)
                    else:
                        title = base_name
                        author = "Unknown"
                    
                    books.append({
                        'id': hash(filename) % 2147483647,  # Generate pseudo-ID from filename
                        'title': title.strip(),
                        'authors': [author.strip()],
                        'formats': [ext.lstrip('.')],
                        'size': stat.st_size,
                        'last_modified': stat.st_mtime,
                        'path': file_path,
                        'filename': filename
                    })
                    
                except (OSError, ValueError) as e:
                    logger.warning(f"Error processing file {filename}: {e}")
                    continue
        
        except OSError as e:
            logger.error(f"Error scanning library path {library_path}: {e}")
        
        return books


def get_library_service() -> LibraryService:
    """Get library service instance."""
    return LibraryService()