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
        self._books_cache = None
        self._cache_timestamp = None

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
            
            # If formats is empty, try to detect formats from synchronized file structure
            if not book["formats"] and current_library_path:
                book["formats"] = self._detect_formats_from_filesystem(book, current_library_path)

        return books

    def _detect_formats_from_filesystem(self, book: Dict[str, Any], library_path: str) -> List[str]:
        """
        Detect available formats for a book from the synchronized file structure.
        This is used when the Calibre database has empty formats but files exist in organized directories.
        """
        import os
        
        # Create expected filename pattern: "Title - Author"
        title = book.get("title", "Unknown")
        authors = book.get("authors", ["Unknown"])
        author = authors[0] if isinstance(authors, list) and authors else "Unknown"
        
        # Sanitize the base filename (remove problematic characters for filesystem)
        import re
        base_filename = f"{title} - {author}".replace("/", "-").replace("\\", "-").replace(":", "").replace("|", " ")
        # Collapse multiple spaces into double spaces (to match actual file naming)
        base_filename = re.sub(r' {3,}', '  ', base_filename)
        
        formats = []
        
        # Known format directories in synchronized structure
        format_dirs = {
            'epubs': 'epub',
            'pdfs': 'pdf', 
            'mobi': 'mobi',
            'azw': 'azw',
            'azw3': 'azw3',
            'txt': 'txt',
            'rtf': 'rtf',
            'docx': 'docx',
            'kfx': 'kfx',
            'original_epubs': 'epub',
            'original_mobi': 'mobi'
        }
        
        # Check format directories
        for format_dir, format_ext in format_dirs.items():
            format_path = os.path.join(library_path, format_dir)
            if os.path.exists(format_path):
                for file in os.listdir(format_path):
                    # Check if file matches this book's pattern
                    if file.startswith(base_filename):
                        # Handle different file extensions based on directory
                        if format_dir == 'original_epubs' and file.lower().endswith('.original_epub'):
                            if format_ext not in formats:
                                formats.append(format_ext)
                        elif format_dir == 'original_mobi' and file.lower().endswith('.original_mobi'):
                            if format_ext not in formats:
                                formats.append(format_ext)
                        elif file.lower().endswith(f'.{format_ext.lower()}'):
                            if format_ext not in formats:
                                formats.append(format_ext)
        
        # Also check root directory for mobi files (common in replica structure)
        if os.path.exists(library_path):
            for file in os.listdir(library_path):
                file_path = os.path.join(library_path, file)
                if os.path.isfile(file_path) and file.startswith(base_filename):
                    # Check for mobi and other formats in root
                    if file.lower().endswith('.mobi') and 'mobi' not in formats:
                        formats.append('mobi')
                    elif file.lower().endswith('.epub') and 'epub' not in formats:
                        formats.append('epub')
                    elif file.lower().endswith('.pdf') and 'pdf' not in formats:
                        formats.append('pdf')
        
        logger.debug(f"Detected formats for book '{title}': {formats}")
        return formats

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
        """Get the path to a book's cover image - check cache first, then extract if needed."""
        try:
            # Check if cover is already cached - this should be INSTANT
            covers_dir = os.path.join(self.library_path, '.covers')
            cached_cover_path = os.path.join(covers_dir, f"cover_{book_id}.jpg")
            
            if os.path.exists(cached_cover_path):
                logger.debug(f"Returning cached cover for book ID {book_id}")
                return cached_cover_path
            
            # If not cached, extract it (this is the slow path, only happens once per book)
            logger.debug(f"Cover not cached for book ID {book_id}, extracting...")
            
            # Get book information to find the actual files
            import time
            current_time = time.time()
            
            if (self._books_cache is None or 
                self._cache_timestamp is None or 
                current_time - self._cache_timestamp > 30):
                self._books_cache = self.get_books()
                self._cache_timestamp = current_time
            
            books_data = self._books_cache
            book = None
            
            for b in books_data:
                if b["id"] == book_id:
                    book = b
                    break
            
            if not book:
                logger.info(f"Book with ID {book_id} not found")
                return None
            
            # Create expected filename pattern for synchronized structure
            title = book.get("title", "Unknown")
            authors = book.get("authors", ["Unknown"])
            author = authors[0] if isinstance(authors, list) and authors else "Unknown"
            import re
            base_filename = f"{title} - {author}".replace("/", "-").replace("\\", "-").replace(":", "").replace("|", " ")
            # Collapse multiple spaces into double spaces (to match actual file naming)
            base_filename = re.sub(r' {3,}', '  ', base_filename)
            
            # Look for ebook files to extract cover from
            # Prioritize formats most likely to have covers: EPUB first, then MOBI
            priority_formats = [
                ('epubs', '.epub'),
                ('original_epubs', '.original_epub'), 
                ('mobi', '.mobi'),
                ('original_mobi', '.original_mobi'),
                ('azw3', '.azw3'),
                ('azw', '.azw')
            ]
            
            # Check priority format directories first
            for format_dir, file_ext in priority_formats:
                format_path = os.path.join(self.library_path, format_dir)
                if os.path.exists(format_path):
                    for file in os.listdir(format_path):
                        if (file.startswith(base_filename) and 
                            file.lower().endswith(file_ext.lower())):
                            ebook_path = os.path.join(format_path, file)
                            cover_path = self._extract_cover_from_ebook(ebook_path, book_id)
                            if cover_path:
                                return cover_path
            
            # Check root directory as fallback
            try:
                for file in os.listdir(self.library_path):
                    if (file.startswith(base_filename) and 
                        os.path.isfile(os.path.join(self.library_path, file)) and
                        any(file.lower().endswith(ext) for ext in ['.epub', '.mobi', '.azw3', '.azw'])):
                        ebook_path = os.path.join(self.library_path, file)
                        cover_path = self._extract_cover_from_ebook(ebook_path, book_id)
                        if cover_path:
                            return cover_path
            except OSError:
                pass
            
            logger.info(f"No cover extractable for book ID {book_id}")
            return None

        except Exception as e:
            logger.error(f"Error getting cover for book {book_id}: {e}")
            return None
    
    def _extract_cover_from_ebook(self, ebook_path: str, book_id: int) -> Optional[str]:
        """Extract cover image from ebook file and save it temporarily."""
        try:
            import tempfile
            import zipfile
            from pathlib import Path
            
            # Create a temporary directory for extracted covers
            covers_dir = os.path.join(self.library_path, '.covers')
            os.makedirs(covers_dir, exist_ok=True)
            
            cover_cache_path = os.path.join(covers_dir, f"cover_{book_id}.jpg")
            
            # If cover already cached, return it
            if os.path.exists(cover_cache_path):
                return cover_cache_path
            
            file_ext = os.path.splitext(ebook_path)[1].lower()
            
            # Handle EPUB files (which are ZIP archives)
            if file_ext in ['.epub', '.original_epub']:
                return self._extract_epub_cover(ebook_path, cover_cache_path)
            
            # Handle MOBI files using calibre's ebook-meta command
            elif file_ext in ['.mobi', '.azw', '.azw3', '.original_mobi']:
                return self._extract_mobi_cover(ebook_path, cover_cache_path)
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting cover from {ebook_path}: {e}")
            return None
    
    def _extract_epub_cover(self, epub_path: str, output_path: str) -> Optional[str]:
        """Extract cover from EPUB file."""
        try:
            import zipfile
            import xml.etree.ElementTree as ET
            
            with zipfile.ZipFile(epub_path, 'r') as epub:
                # Look for cover image in common locations
                cover_candidates = []
                
                for file_info in epub.filelist:
                    filename = file_info.filename.lower()
                    if ('cover' in filename and 
                        any(filename.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif'])):
                        cover_candidates.append(file_info.filename)
                
                # Try to extract first found cover
                if cover_candidates:
                    cover_data = epub.read(cover_candidates[0])
                    with open(output_path, 'wb') as f:
                        f.write(cover_data)
                    logger.debug(f"Extracted EPUB cover to {output_path}")
                    return output_path
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting EPUB cover: {e}")
            return None
    
    def _extract_mobi_cover(self, mobi_path: str, output_path: str) -> Optional[str]:
        """Extract cover from MOBI file using calibre's ebook-meta."""
        try:
            # Use calibre's ebook-meta to extract cover
            cmd = [
                getattr(self.settings if hasattr(self, 'settings') else settings, "CALIBRE_CMD_PATH", "ebook-meta").replace("calibredb", "ebook-meta"),
                mobi_path,
                "--get-cover", output_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3  # Reduced timeout from 10 to 3 seconds
            )
            
            if result.returncode == 0 and os.path.exists(output_path):
                logger.debug(f"Extracted MOBI cover to {output_path}")
                return output_path
            
            return None
            
        except subprocess.TimeoutExpired:
            logger.warning(f"MOBI cover extraction timeout for {mobi_path}")
            return None
        except Exception as e:
            logger.error(f"Error extracting MOBI cover: {e}")
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