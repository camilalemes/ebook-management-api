"""Enhanced Calibre service with caching, better error handling, and async support."""

import asyncio
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from functools import lru_cache

from ..config import settings
from ..exceptions import CalibreServiceException, CalibreCommandException, BookNotFoundException
from ..utils.logging import LoggerMixin
from ..utils.cache import cache_books, cache_metadata, cache_covers


class CalibreServiceEnhanced(LoggerMixin):
    """Enhanced Calibre service with caching and better error handling."""
    
    def __init__(self, library_path: str):
        self.library_path = Path(library_path)
        self.calibre_cmd = settings.CALIBRE_CMD_PATH
        self._validate_setup()
    
    def _validate_setup(self) -> None:
        """Validate Calibre setup and library path."""
        if not self.library_path.exists():
            raise CalibreServiceException(
                f"Library path does not exist: {self.library_path}",
                error_code="LIBRARY_PATH_NOT_FOUND"
            )
        
        if not self.library_path.is_dir():
            raise CalibreServiceException(
                f"Library path is not a directory: {self.library_path}",
                error_code="INVALID_LIBRARY_PATH"
            )
        
        # Check if calibredb is available
        try:
            subprocess.run(
                [self.calibre_cmd, "--version"],
                capture_output=True,
                check=True,
                timeout=10
            )
        except subprocess.CalledProcessError as e:
            raise CalibreServiceException(
                f"Calibre command failed: {e}",
                error_code="CALIBRE_NOT_AVAILABLE"
            )
        except subprocess.TimeoutExpired:
            raise CalibreServiceException(
                "Calibre command timed out",
                error_code="CALIBRE_TIMEOUT"
            )
        except FileNotFoundError:
            raise CalibreServiceException(
                f"Calibre command not found: {self.calibre_cmd}",
                error_code="CALIBRE_NOT_FOUND"
            )
    
    async def _run_calibredb_async(
        self, 
        command: List[str], 
        timeout: int = 30,
        custom_library_path: Optional[str] = None
    ) -> subprocess.CompletedProcess:
        """Run calibredb command asynchronously."""
        lib_path = custom_library_path or str(self.library_path)
        cmd = [self.calibre_cmd] + command + ["--library-path", lib_path]
        
        self.logger.debug(f"Running async command: {' '.join(cmd)}")
        
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    check=True,
                    timeout=timeout
                )
            )
            return result
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Calibre command failed: {' '.join(cmd)}")
            self.logger.error(f"Error output: {e.stderr}")
            raise CalibreCommandException(' '.join(cmd), e.stderr)
            
        except subprocess.TimeoutExpired:
            self.logger.error(f"Calibre command timed out: {' '.join(cmd)}")
            raise CalibreServiceException(
                f"Command timed out after {timeout}s",
                error_code="CALIBRE_TIMEOUT"
            )
    
    def _run_calibredb(
        self, 
        command: List[str], 
        timeout: int = 30,
        custom_library_path: Optional[str] = None
    ) -> subprocess.CompletedProcess:
        """Run calibredb command synchronously."""
        lib_path = custom_library_path or str(self.library_path)
        cmd = [self.calibre_cmd] + command + ["--library-path", lib_path]
        
        self.logger.debug(f"Running command: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                check=True,
                timeout=timeout
            )
            return result
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Calibre command failed: {' '.join(cmd)}")
            self.logger.error(f"Error output: {e.stderr}")
            raise CalibreCommandException(' '.join(cmd), e.stderr)
            
        except subprocess.TimeoutExpired:
            self.logger.error(f"Calibre command timed out: {' '.join(cmd)}")
            raise CalibreServiceException(
                f"Command timed out after {timeout}s",
                error_code="CALIBRE_TIMEOUT"
            )
    
    @cache_books(ttl=300)  # Cache for 5 minutes
    def get_books(self, library_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all books from the library with caching."""
        current_library_path = library_path or str(self.library_path)
        
        self.logger.info(f"Fetching books from library: {current_library_path}")
        
        try:
            result = self._run_calibredb(
                ["list", "--for-machine", "--fields", "title,authors,formats,id"],
                custom_library_path=current_library_path
            )
            
            books = json.loads(result.stdout)
            
            # Process and validate book data
            processed_books = []
            for book in books:
                processed_book = self._process_book_data(book)
                if processed_book:
                    processed_books.append(processed_book)
            
            self.logger.info(f"Retrieved {len(processed_books)} books")
            return processed_books
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to decode JSON from calibredb output: {e}")
            raise CalibreServiceException(
                "Invalid response from Calibre database",
                error_code="INVALID_CALIBRE_RESPONSE"
            )
    
    async def get_books_async(self, library_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all books from the library asynchronously."""
        current_library_path = library_path or str(self.library_path)
        
        self.logger.info(f"Fetching books async from library: {current_library_path}")
        
        try:
            result = await self._run_calibredb_async(
                ["list", "--for-machine", "--fields", "title,authors,formats,id"],
                custom_library_path=current_library_path
            )
            
            books = json.loads(result.stdout)
            
            # Process and validate book data
            processed_books = []
            for book in books:
                processed_book = self._process_book_data(book)
                if processed_book:
                    processed_books.append(processed_book)
            
            self.logger.info(f"Retrieved {len(processed_books)} books async")
            return processed_books
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to decode JSON from calibredb output: {e}")
            raise CalibreServiceException(
                "Invalid response from Calibre database",
                error_code="INVALID_CALIBRE_RESPONSE"
            )
    
    def _process_book_data(self, book: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process and validate book data."""
        try:
            # Ensure required fields exist
            if not all(key in book for key in ['id', 'title']):
                self.logger.warning(f"Book missing required fields: {book}")
                return None
            
            # Process authors
            authors = book.get("authors", [])
            if not isinstance(authors, list):
                authors = [str(authors)] if authors else ["Unknown"]
            else:
                authors = [str(author) for author in authors if author]
            
            # Process formats
            formats = book.get("formats", [])
            if isinstance(formats, str):
                formats = [formats]
            elif not isinstance(formats, list):
                formats = []
            
            return {
                "id": int(book["id"]),
                "title": str(book["title"]),
                "authors": authors,
                "formats": formats
            }
            
        except (ValueError, TypeError) as e:
            self.logger.warning(f"Error processing book data {book}: {e}")
            return None
    
    def get_book_by_id(self, book_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific book."""
        if book_id <= 0:
            raise ValueError("Book ID must be positive")
        
        try:
            result = self._run_calibredb(["list", "--for-machine", str(book_id)])
            books = json.loads(result.stdout)
            
            if not books:
                return None
            
            return self._process_book_data(books[0])
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to decode JSON for book {book_id}: {e}")
            raise CalibreServiceException(
                "Invalid response from Calibre database",
                error_code="INVALID_CALIBRE_RESPONSE"
            )
    
    @cache_metadata(ttl=600)  # Cache for 10 minutes
    def get_book_metadata(self, book_id: int) -> Optional[Dict[str, Any]]:
        """Get book metadata with caching."""
        if book_id <= 0:
            raise ValueError("Book ID must be positive")
        
        self.logger.debug(f"Fetching metadata for book ID: {book_id}")
        
        try:
            result = self._run_calibredb(["show_metadata", "--as-opf", str(book_id)])
            
            if not result.stdout.strip():
                raise BookNotFoundException(book_id)
            
            # Parse OPF metadata - this is a simplified version
            # In a real implementation, you'd parse the XML properly
            return {
                "id": book_id,
                "opf_content": result.stdout
            }
            
        except subprocess.CalledProcessError:
            raise BookNotFoundException(book_id)
    
    def add_book(self, file_path: str, tags: Optional[List[str]] = None) -> Optional[int]:
        """Add a book to the library with validation."""
        file_path_obj = Path(file_path)
        
        if not file_path_obj.exists():
            raise CalibreServiceException(
                f"File not found: {file_path}",
                error_code="FILE_NOT_FOUND"
            )
        
        if not file_path_obj.is_file():
            raise CalibreServiceException(
                f"Path is not a file: {file_path}",
                error_code="INVALID_FILE_PATH"
            )
        
        # Check file extension
        allowed_extensions = settings.allowed_extensions_list
        if file_path_obj.suffix.lower() not in allowed_extensions:
            raise CalibreServiceException(
                f"File type not supported: {file_path_obj.suffix}",
                error_code="UNSUPPORTED_FILE_TYPE"
            )
        
        cmd = ["add", str(file_path_obj.absolute())]
        
        if tags:
            cmd.extend(["--tags", ",".join(tags)])
        
        self.logger.info(f"Adding book: {file_path}")
        
        try:
            result = self._run_calibredb(cmd, timeout=60)  # Longer timeout for file operations
            
            # Parse book ID from output
            output = result.stdout.strip()
            if "Added book ids:" in output:
                id_part = output.split("Added book ids:")[1].split("\n")[0].strip()
                if id_part.isdigit():
                    book_id = int(id_part)
                    self.logger.info(f"Successfully added book with ID: {book_id}")
                    return book_id
            
            self.logger.warning(f"Could not parse book ID from output: {output}")
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to add book {file_path}: {e}")
            raise CalibreServiceException(
                f"Failed to add book: {str(e)}",
                error_code="ADD_BOOK_FAILED"
            )
    
    def remove_book(self, book_id: int) -> bool:
        """Remove a book from the library."""
        if book_id <= 0:
            raise ValueError("Book ID must be positive")
        
        self.logger.info(f"Removing book ID: {book_id}")
        
        try:
            self._run_calibredb(["remove", str(book_id)])
            self.logger.info(f"Successfully removed book ID: {book_id}")
            return True
            
        except CalibreCommandException:
            # Book might not exist
            raise BookNotFoundException(book_id)
    
    @cache_covers(ttl=3600)  # Cache for 1 hour
    def get_cover_path(self, book_id: int) -> Optional[str]:
        """Get the path to a book's cover image."""
        if book_id <= 0:
            raise ValueError("Book ID must be positive")
        
        try:
            # Search for cover files in the library directory
            for root, dirs, files in self.library_path.rglob("*"):
                if f"({book_id})" in root.name:
                    for cover_name in ["cover.jpg", "cover.jpeg", "cover.png"]:
                        cover_path = root / cover_name
                        if cover_path.exists():
                            self.logger.debug(f"Found cover for book {book_id}: {cover_path}")
                            return str(cover_path)
            
            self.logger.debug(f"No cover found for book ID {book_id}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error finding cover for book {book_id}: {e}")
            return None
    
    def search_books(self, query: str) -> List[Dict[str, Any]]:
        """Search for books in the library."""
        if not query.strip():
            raise ValueError("Search query cannot be empty")
        
        self.logger.info(f"Searching books with query: {query}")
        
        try:
            result = self._run_calibredb([
                "list", "--for-machine", 
                "--fields", "title,authors,formats,id", 
                "--search", query
            ])
            
            books = json.loads(result.stdout)
            processed_books = []
            
            for book in books:
                processed_book = self._process_book_data(book)
                if processed_book:
                    processed_books.append(processed_book)
            
            self.logger.info(f"Found {len(processed_books)} books matching query")
            return processed_books
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to decode search results: {e}")
            raise CalibreServiceException(
                "Invalid search response",
                error_code="INVALID_SEARCH_RESPONSE"
            )


# Dependency injection function
@lru_cache()
def get_calibre_service_enhanced() -> CalibreServiceEnhanced:
    """Get enhanced Calibre service instance with caching."""
    # Get the first library path from LIBRARY_PATHS
    library_paths = [path.strip() for path in settings.LIBRARY_PATHS.split(',') if path.strip()]
    primary_library_path = library_paths[0] if library_paths else ""
    return CalibreServiceEnhanced(primary_library_path)