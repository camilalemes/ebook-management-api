# app/calibre_service.py
import os
import json
import subprocess
import logging
from typing import List, Dict, Any, Optional, Tuple  # Added Tuple

from ..config import settings

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("calibre_service")


class CalibreService:
    def __init__(self, library_path: str):
        """Initialize with path to Calibre library."""
        self.library_path = library_path

    def _run_calibredb(self, command: List[str], check: bool = True,
                       custom_library_path: Optional[str] = None) -> subprocess.CompletedProcess:
        """Run a calibredb command and return the result."""
        calibredb_path = getattr(settings, "CALIBRE_CMD_PATH", "calibredb")

        # Use custom_library_path if provided, otherwise use instance's library_path
        lib_path = custom_library_path if custom_library_path else self.library_path

        cmd = [calibredb_path] + command + ["--library-path", lib_path]
        logger.debug(f"Running command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                check=check,
                capture_output=True,
                text=True,
                encoding='utf-8'  # Specify encoding for consistent text output
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

    def get_books(self, library_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get a list of all books in the specified library (or instance's default) with formats."""
        # Use the provided library_path for this specific call, or default to self.library_path
        # This modification makes get_books more flexible for the comparison function
        current_library_path = library_path if library_path else self.library_path

        result = self._run_calibredb(
            ["list", "--for-machine", "--fields", "title,authors,formats,id", "--sort-by", "title", "--ascending"],
            custom_library_path=current_library_path
        )

        try:
            books = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON from calibredb output: {e}")
            logger.error(f"Raw output: {result.stdout[:500]}...")  # Log a snippet of the problematic output
            return []

        # Process the books to ensure formats are properly represented
        for book in books:
            # Ensure authors is a list of strings
            if "authors" not in book or book["authors"] is None:
                book["authors"] = []
            elif not isinstance(book["authors"], list):
                # This case might not happen with --for-machine, but good for robustness
                book["authors"] = [str(book["authors"])]
            else:
                book["authors"] = [str(author) for author in book["authors"]]

            # Ensure formats is a list
            if "formats" not in book or book["formats"] is None:
                book["formats"] = []
            elif isinstance(book["formats"], str):  # calibredb might return a single string if only one format
                book["formats"] = [book["formats"]]
            # If it's already a list, assume it's fine. Add more checks if needed.

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

        # Ensure file_path is an absolute path or calibredb might not find it
        cmd.append(os.path.abspath(file_path))

        try:
            result = self._run_calibredb(cmd)
            output = result.stdout.strip()
            # Output for a single book: "Added book ids: 1234"
            # Output for multiple books (e.g. adding a duplicate): "Added book ids: \nNot added:\n..."
            # We are interested in the "Added book ids:" part.
            added_ids_marker = "Added book ids:"
            if added_ids_marker in output:
                # Extract the part after "Added book ids:" and before any potential "Not added:"
                id_part = output.split(added_ids_marker)[1].split("\n")[0].strip()
                if id_part.isdigit():
                    return int(id_part)
                elif not id_part:  # No ID followed, means it might not have been added or was a duplicate message
                    logger.info(f"Book at {file_path} might not have been added or was a duplicate. Output: {output}")
                    # Try to search for the book to see if it exists now (if it was a duplicate without error)
                    # This part can be complex, for now, we'll assume if no ID, it's not a clean add.
                    return None
            logger.warning(f"Could not parse book ID from add command output: {output}")
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
            # Added --fields to search_books to make its output consistent with get_books
            result = self._run_calibredb(
                ["list", "--for-machine", "--fields", "title,authors,formats,id", "--sort-by", "title", "--ascending", "--search", query])
            return json.loads(result.stdout)
        except Exception as e:
            logger.error(f"Error searching for '{query}': {e}")
            return []

    def get_cover_path(self, book_id: int) -> Optional[str]:
        """Get the path to a book's cover image by searching the library directory."""
        try:
            # Simply search the library directory for folders containing the book ID
            # Calibre stores books in folders named like "Author/Title (ID)/"
            for root, dirs, files in os.walk(self.library_path):
                # Check if this directory contains the book ID in its name
                if f"({book_id})" in os.path.basename(root):
                    # Look for cover files in this directory
                    for cover_name in ["cover.jpg", "cover.jpeg", "cover.png"]:
                        cover_path = os.path.join(root, cover_name)
                        if os.path.exists(cover_path):
                            logger.debug(f"Found cover for book {book_id} at: {cover_path}")
                            return cover_path
            
            logger.info(f"No cover found for book ID {book_id}")
            return None

        except Exception as e:
            logger.error(f"Error getting cover for book {book_id}: {e}")
            return None

    def _create_book_identifier(self, book: Dict[str, Any]) -> Tuple[str, Tuple[str, ...]]:
        """
        Creates a comparable identifier for a book (normalized title, sorted normalized authors).
        """
        title = str(book.get('title', '')).strip().lower()
        authors_list = book.get('authors', [])
        if not isinstance(authors_list, list):  # Should be a list from get_books
            authors_list = [str(authors_list)]

        normalized_authors = tuple(sorted([str(author).strip().lower() for author in authors_list]))
        return title, normalized_authors

    def compare_with_library(self, other_library_path: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Compares books in the current library with books in another library using content-based comparison.
        """
        logger.info(f"Comparing current library ({self.library_path}) with {other_library_path}")

        # Validate other library path
        if not os.path.isdir(other_library_path):
            logger.error(f"Other library path '{other_library_path}' is not a valid directory.")
            raise ValueError(f"Invalid library path: {other_library_path}")

        from ..services.sync_service import SyncService

        # Create temporary SyncService instances for accessing file data
        sync_service = SyncService(self.library_path, [])
        other_sync_service = SyncService(other_library_path, [])

        # Get files and metadata from both libraries
        current_files = sync_service.get_calibre_files()
        other_files = other_sync_service.get_calibre_files()

        logger.info(
            f"Found {len(current_files)} files in current library and {len(other_files)} files in other library")

        # Create dictionaries to store books by normalized title-author
        current_books_by_key = {}
        other_books_by_key = {}

        # Helper function to normalize book info from filename
        def normalize_book_info(filename):
            # Remove extension and split by delimiter
            base_name = os.path.splitext(filename)[0]
            parts = base_name.split(" - ")

            # Handle cases with and without author
            if len(parts) > 1:
                title = " - ".join(parts[:-1]).strip().lower()
                author = parts[-1].strip().lower().replace(" ", "")  # Remove spaces in author name
                return f"{title}__{author}"
            else:
                return base_name.strip().lower()

        # Process current library files
        total_files_current = 0
        skipped_files_current = 0

        for filename, file_meta in current_files.items():
            total_files_current += 1

            # Skip database files
            file_ext = os.path.splitext(filename)[1].lower()
            if file_ext in ['.db', '.json']:
                skipped_files_current += 1
                continue

            # Get normalized key for comparison
            book_key = normalize_book_info(filename)
            current_books_by_key[book_key] = file_meta
            logger.debug(f"Current lib: {filename} -> normalized to '{book_key}'")

        # Process other library files
        total_files_other = 0
        skipped_files_other = 0

        for filename, file_meta in other_files.items():
            total_files_other += 1

            # Skip database files
            file_ext = os.path.splitext(filename)[1].lower()
            if file_ext in ['.db', '.json']:
                skipped_files_other += 1
                continue

            # Get normalized key for comparison
            book_key = normalize_book_info(filename)
            other_books_by_key[book_key] = file_meta
            logger.debug(f"Other lib: {filename} -> normalized to '{book_key}'")

        # Find common books using normalized keys
        common_keys = set(current_books_by_key.keys()) & set(other_books_by_key.keys())
        logger.info(f"Found {len(common_keys)} books common to both libraries based on normalized title-author")

        # Log a sample of common books for verification
        sample_size = min(5, len(common_keys))
        if sample_size > 0:
            logger.info(f"Sample of common books (showing up to {sample_size}):")
            for i, key in enumerate(list(common_keys)[:sample_size]):
                current_file = os.path.basename(current_books_by_key[key]["path"])
                other_file = os.path.basename(other_books_by_key[key]["path"])
                logger.info(f"  Common book {i + 1}: '{current_file}' and '{other_file}'")

        # Find books unique to current library
        unique_to_current = []
        for key, file_meta in current_books_by_key.items():
            if key not in other_books_by_key:
                book_info = self._get_book_info_from_filepath(file_meta["path"])
                if book_info:
                    unique_to_current.append(book_info)
                else:
                    # Extract potential author info from filename
                    filename = os.path.basename(file_meta["path"])
                    title_parts = os.path.splitext(filename)[0].split(" - ")

                    authors = ["Unknown"]
                    title = title_parts[0]

                    # If filename follows "Title - Author" format, extract author
                    if len(title_parts) > 1:
                        authors = [title_parts[-1]]
                        title = " - ".join(title_parts[:-1])

                    # Fallback to basic info if metadata retrieval fails
                    unique_to_current.append({
                        "title": title,
                        "authors": authors,
                        "formats": [file_meta["path"]],
                        "size": file_meta["size"],
                        "last_modified": file_meta["mtime"]
                    })

        # Find books unique to other library
        unique_to_other = []
        other_service = CalibreService(other_library_path)
        for key, file_meta in other_books_by_key.items():
            if key not in current_books_by_key:
                book_info = other_service._get_book_info_from_filepath(file_meta["path"])
                if book_info:
                    unique_to_other.append(book_info)
                else:
                    # Extract potential author info from filename
                    filename = os.path.basename(file_meta["path"])
                    title_parts = os.path.splitext(filename)[0].split(" - ")

                    authors = ["Unknown"]
                    title = title_parts[0]

                    # If filename follows "Title - Author" format, extract author
                    if len(title_parts) > 1:
                        authors = [title_parts[-1]]
                        title = " - ".join(title_parts[:-1])

                    # Fallback to basic info if metadata retrieval fails
                    unique_to_other.append({
                        "title": title,
                        "authors": authors,
                        "formats": [file_meta["path"]],
                        "size": file_meta["size"],
                        "last_modified": file_meta["mtime"]
                    })

        logger.info(f"Comparison complete. Found {len(unique_to_current)} books unique to current library "
                    f"and {len(unique_to_other)} books unique to other library.")

        return {
            "unique_to_current_library": unique_to_current,
            "unique_to_other_library": unique_to_other
        }

    def _get_book_info_from_filepath(self, filepath: str) -> Optional[Dict[str, Any]]:
        """
        Attempts to find book metadata for a specific file path by searching the Calibre database.
        """
        try:
            # Get all books
            all_books = self.get_books()

            # Look for the book with matching format path
            for book in all_books:
                formats = book.get("formats", [])
                if not formats:
                    continue

                # Normalize formats to list
                if isinstance(formats, str):
                    formats = [formats]

                # Check if filepath matches any format
                filepath_abs = os.path.abspath(filepath)
                for fmt in formats:
                    if os.path.abspath(fmt) == filepath_abs:
                        return book

            # If no exact match found, try to match by filename
            filename = os.path.basename(filepath)
            for book in all_books:
                formats = book.get("formats", [])
                if not formats:
                    continue

                if isinstance(formats, str):
                    formats = [formats]

                for fmt in formats:
                    if fmt and os.path.basename(fmt) == filename:
                        logger.info(f"Found book metadata by filename match: '{book.get('title')}' for '{filename}'")
                        return book

            return None
        except Exception as e:
            logger.error(f"Error getting book info from filepath {filepath}: {e}")
            return None


# Create a singleton instance
def get_calibre_service() -> CalibreService:
    """Get a CalibreService instance configured with settings."""
    # Ensure CALIBRE_LIBRARY_PATH is set in your settings
    if not hasattr(settings, 'CALIBRE_LIBRARY_PATH') or not settings.CALIBRE_LIBRARY_PATH:
        logger.critical("CALIBRE_LIBRARY_PATH is not configured in settings.")
        raise ValueError("CALIBRE_LIBRARY_PATH must be set in configuration.")

    # Basic check if the main library path seems valid
    if not os.path.isdir(settings.CALIBRE_LIBRARY_PATH):
        logger.warning(
            f"The configured CALIBRE_LIBRARY_PATH '{settings.CALIBRE_LIBRARY_PATH}' does not exist or is not a directory.")
        # Depending on strictness, you might raise an error here or let Calibre handle it.
        # For now, let it proceed, Calibre might create it or error out appropriately.

    return CalibreService(library_path=settings.CALIBRE_LIBRARY_PATH)