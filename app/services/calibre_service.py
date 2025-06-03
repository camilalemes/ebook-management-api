# app/calibre_service.py
import os
import json
import subprocess
import logging
from typing import List, Dict, Any, Optional

from ..config import settings

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("calibre_service")


class CalibreService:
    def __init__(self, library_path: str):
        """Initialize with path to Calibre library."""
        self.library_path = library_path

    def _run_calibredb(self, command: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run a calibredb command and return the result."""
        # Use full path to calibredb if configured, otherwise try PATH
        calibredb_path = getattr(settings, "CALIBRE_CMD_PATH", "calibredb")

        cmd = [calibredb_path] + command + ["--library-path", self.library_path]
        logger.debug(f"Running command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                check=check,
                capture_output=True,
                text=True
            )
            return result
        except FileNotFoundError:
            logger.error(
                f"calibredb command not found at '{calibredb_path}'. Check that Calibre is installed and CALIBRE_CMD_PATH is set correctly.")
            raise
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed: {e.cmd}")
            logger.error(f"Error output: {e.stderr}")
            raise

    def get_books(self) -> List[Dict[str, Any]]:
        """Get a list of all books in the library with formats."""
        result = self._run_calibredb(["list", "--for-machine", "--fields", "title,authors,formats,id"])
        books = json.loads(result.stdout)

        # Process the books to ensure formats are properly represented
        for book in books:
            # Ensure formats is a list
            if "formats" not in book or book["formats"] is None:
                book["formats"] = []
            elif isinstance(book["formats"], str):
                book["formats"] = [book["formats"]]

        return books

    def get_book_by_id(self, book_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific book."""
        try:
            result = self._run_calibredb(["list", "--for-machine", str(book_id)])
            books = json.loads(result.stdout)
            return books[0] if books else None
        except Exception as e:
            logger.error(f"Error getting book {book_id}: {e}")
            return None

    def get_book_metadata(self, book_id: int) -> Optional[str]:
        """Get the OPF metadata for a book."""
        try:
            result = self._run_calibredb(["show_metadata", "--as-opf", str(book_id)])
            return result.stdout
        except Exception as e:
            logger.error(f"Error getting metadata for book {book_id}: {e}")
            return None

    def add_book(self, file_path: str, tags: Optional[List[str]] = None) -> Optional[int]:
        """Add a book to the Calibre library."""
        cmd = ["add"]

        if tags:
            cmd.extend(["--tags", ",".join(tags)])

        cmd.append(file_path)

        try:
            result = self._run_calibredb(cmd)
            # Parse the output to get the book ID
            # Output is typically: "Added book ids: 1234"
            output = result.stdout.strip()
            if "Added book ids:" in output:
                book_id = output.split(":")[-1].strip()
                return int(book_id) if book_id.isdigit() else None
            return None
        except Exception as e:
            logger.error(f"Error adding book {file_path}: {e}")
            return None

    def remove_book(self, book_id: int) -> bool:
        """Remove a book from the Calibre library."""
        try:
            self._run_calibredb(["remove", str(book_id)])
            return True
        except Exception as e:
            logger.error(f"Error removing book {book_id}: {e}")
            return False

    def search_books(self, query: str) -> List[Dict[str, Any]]:
        """Search for books in the library."""
        try:
            result = self._run_calibredb(["list", "--for-machine", query])
            return json.loads(result.stdout)
        except Exception as e:
            logger.error(f"Error searching for '{query}': {e}")
            return []

    def get_cover_path(self, book_id: int) -> Optional[str]:
        """Get the path to a book's cover image."""
        try:
            # First get book details to find its folder
            books = self.get_book_by_id(book_id)
            if not books:
                return None

            # Calibre stores books in folders named by author/title or by ID
            # Try to locate the cover in the standard location
            formats = books.get("formats", [])
            if formats:
                # Extract the directory from the first format path
                format_path = formats[0]
                book_dir = os.path.dirname(format_path)
                cover_path = os.path.join(book_dir, "cover.jpg")

                if os.path.exists(cover_path):
                    return cover_path

            # Fallback to the legacy location
            cover_path = os.path.join(self.library_path, "cover_cache", str(book_id), "cover.jpg")
            if os.path.exists(cover_path):
                return cover_path

            return None
        except Exception as e:
            logger.error(f"Error getting cover for book {book_id}: {e}")
            return None


# Create a singleton instance
def get_calibre_service() -> CalibreService:
    """Get a CalibreService instance configured with settings."""
    return CalibreService(library_path=settings.CALIBRE_LIBRARY_PATH)