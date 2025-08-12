import os
import shutil
import hashlib
import logging
import re
from typing import List, Dict, Optional, Set, Tuple
from ..config import settings

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("sync_service")


class SyncService:
    def __init__(self, source_path: str, replica_paths: List[str]):
        """Initialize the sync service with source and replica paths."""
        self.source_path = source_path
        self.replica_paths = replica_paths

    def calculate_file_hash(self, filepath: str) -> str:
        """Calculate MD5 hash of a file for comparison."""
        hash_md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def get_calibre_files(self) -> Dict[str, Dict]:
        """
        Create a dictionary of all book files in the Calibre library.
        Maps book files to their metadata, organized by extension.
        """
        files_data = {}

        for root, dirs, files in os.walk(self.source_path):
            for filename in sorted(files):
                if filename.startswith('.') or filename in ['metadata.opf', 'cover.jpg']:
                    continue  # Skip metadata files and hidden files

                filepath = os.path.join(root, filename)
                _, ext = os.path.splitext(filename)
                ext = ext.lower().lstrip('.')

                if not ext:  # Skip files without extensions
                    continue

                try:
                    stat_info = os.stat(filepath)
                    # Use the file name as the key (we'll handle duplicates)
                    key = filename

                    # Store path and metadata
                    files_data[key] = {
                        "path": filepath,
                        "size": stat_info.st_size,
                        "mtime": stat_info.st_mtime,
                        "ext": ext
                    }
                except OSError as e:
                    logger.error(f"Error accessing {filepath}: {e}")

        return files_data

    def get_replica_files(self, replica_path: str) -> Dict[str, Dict]:
        """
        Get a dictionary of file metadata from the replica.
        Keys are filenames, values contain metadata and paths.
        """
        files_data = {}

        # First, scan the main directory for .mobi files
        if os.path.exists(replica_path):
            self._scan_directory(replica_path, files_data)

        # Then scan all the specialized subdirectories
        for subdir in ["epubs", "original_mobi", "original_epubs", "kfx", "azw3"]:
            subdir_path = os.path.join(replica_path, subdir)
            if os.path.exists(subdir_path):
                self._scan_directory(subdir_path, files_data)

        return files_data

    def get_destination_path(self, replica_path: str, original_file: Dict, dry_run: bool = False) -> str | None:
        """
        Determine the destination path in the replica based on file extension and rename the file
        using the proper title and author from Calibre metadata.
        """
        filename = os.path.basename(original_file["path"])
        ext = original_file["ext"]
        
        # Special case: metadata.db goes directly to replica root without renaming
        if filename == 'metadata.db':
            return os.path.join(replica_path, filename)

        # Get the book metadata from Calibre to use for renaming
        calibre_title = original_file.get("title", "")
        calibre_authors = original_file.get("authors", ["Unknown"])

        # Create a properly formatted filename if we have Calibre metadata
        if calibre_title:
            # Handle cases where the author field contains part of the title
            author_str = ""
            if calibre_authors and isinstance(calibre_authors, list) and calibre_authors[0]:
                author_string = calibre_authors[0]

                # Check if author string contains title components (separated by " - ")
                if " - " in author_string:
                    # Extract the real title and author using a simpler approach
                    parts = author_string.split(" - ")

                    if len(parts) >= 2:
                        # Use the last part as the author
                        author_str = parts[-1].strip()

                        # Use everything before the last part as additional title components
                        title_components = " - ".join(parts[:-1]).strip()
                        calibre_title = f"{calibre_title} - {title_components}"

                        logger.info(
                            f"Extracted compound title: '{calibre_title}' from author field, real author: '{author_str}'")
                    else:
                        author_str = author_string
                else:
                    author_str = author_string
            else:
                author_str = str(calibre_authors[0]) if calibre_authors else "Unknown"

            # Create a sanitized filename: "Title - Author.ext"
            # Remove characters that are problematic in filenames
            safe_title = re.sub(r'[\\/*?:"<>|]', '', calibre_title)
            safe_author = re.sub(r'[\\/*?:"<>|]', '', author_str)

            # Create the new filename
            filename = f"{safe_title} - {safe_author}.{ext}"
            logger.debug(f"Created filename: '{filename}'")

        # Map extensions to directories
        ext_dir_map = {
            "epub": "epubs",
            "original_epub": "original_epubs",
            "original_mobi": "original_mobi",
            "kfx": "kfx",
            "azw3": "azw3",
            "original_azw3": "azw3"
        }

        if ext in ext_dir_map:
            # Place file in appropriate subdirectory
            subdir = os.path.join(replica_path, ext_dir_map[ext])
            if not dry_run:
                os.makedirs(subdir, exist_ok=True)
            return os.path.join(subdir, filename)
        elif ext == "mobi":
            # All other files go directly to the replica root
            return os.path.join(replica_path, filename)
        else:
            # For unsupported extensions, just return the original path
            logger.warning(f"Unsupported file extension '{ext}' for file '{filename}', ignoring.")
            return None

    def _scan_directory(self, directory: str, files_data: Dict[str, Dict]) -> None:
        """Helper method to scan a directory and add files to files_data dict"""
        if not os.path.exists(directory):
            return

        for filename in sorted(os.listdir(directory)):
            filepath = os.path.join(directory, filename)
            if os.path.isfile(filepath) and not filename.startswith('.'):
                try:
                    stat_info = os.stat(filepath)
                    _, ext = os.path.splitext(filename)
                    ext = ext.lower().lstrip('.')

                    if not ext:  # Skip files without extensions
                        continue

                    files_data[filename] = {
                        "path": filepath,
                        "size": stat_info.st_size,
                        "mtime": stat_info.st_mtime,
                        "ext": ext
                    }
                except OSError as e:
                    logger.error(f"Error accessing {filepath}: {e}")

    def sync_folder(self, destination: str, dry_run: bool = False) -> Dict:
        """
        Sync from Calibre library to destination with a flat structure.
        Returns stats about the operation.
        """
        logger.info(f"Starting sync from {self.source_path} to {destination}")

        from ..services.calibre_service import CalibreService

        # Get Calibre metadata for all books to use for renaming
        calibre_books_by_path = {}
        calibre_books_by_id = {}
        try:
            # Create a temporary CalibreService to access book metadata
            calibre_service = CalibreService(self.source_path)
            books_data = calibre_service.get_books()

            # Create lookups by file path and book ID
            for book in books_data:
                book_id = book.get("id")
                title = book.get("title", "")
                authors = book.get("authors", ["Unknown"])

                # Normalize authors to list
                if isinstance(authors, str):
                    authors = [authors]

                # Store in ID lookup
                calibre_books_by_id[book_id] = {
                    "title": title,
                    "authors": authors,
                    "book_id": book_id
                }

                # Create path lookup
                book_formats = book.get("formats", [])
                if isinstance(book_formats, str):
                    book_formats = [book_formats]

                for fmt in book_formats:
                    if fmt and os.path.exists(fmt):
                        # Store the absolute path
                        calibre_books_by_path[os.path.abspath(fmt)] = {
                            "title": title,
                            "authors": authors,
                            "book_id": book_id
                        }
                        logger.debug(
                            f"Found metadata for '{os.path.basename(fmt)}': '{title}' by {authors[0] if authors else 'Unknown'}")
        except Exception as e:
            logger.warning(f"Could not retrieve Calibre metadata: {e}")

        # Ensure destination exists
        if not os.path.exists(destination):
            if not dry_run:
                os.makedirs(destination)
            logger.info(f"Created destination directory: {destination}")

        # Get file metadata for source and destination
        source_files = self.get_calibre_files()
        dest_files = self.get_replica_files(destination)

        # Track statistics
        stats = {
            "added": 0,
            "updated": 0,
            "deleted": 0,
            "unchanged": 0,
            "ignored": 0,  # For files that are skipped (e.g., .db, .json)
            "errors": 0,
            # File lists for detailed reporting
            "added_files": [],
            "updated_files": [],
            "deleted_files": [],
            "ignored_files": [],
            "error_files": []
        }

        # Process source files - copy or update as needed
        processed_dest_files = set()

        for filename, source_meta in source_files.items():
            # Handle different file types
            file_ext = os.path.splitext(filename)[1].lower()
            
            # Always copy metadata.db as it contains important Calibre library information
            if filename == 'metadata.db':
                # Process metadata.db normally - it should be copied to replicas
                pass
            # Skip other .db and .json files
            elif file_ext in ['.db', '.json']:
                stats["ignored"] += 1
                stats["ignored_files"].append(filename)
                logger.debug(f"Ignoring database/config file: {filename}")
                continue

            # Add Calibre metadata for renaming - use absolute path for reliable matching
            source_path = os.path.abspath(source_meta["path"])

            # Try to find metadata for this file
            if source_path in calibre_books_by_path:
                source_meta.update(calibre_books_by_path[source_path])
                logger.debug(f"Applied metadata: '{calibre_books_by_path[source_path]['title']}' to '{filename}'")
            else:
                logger.warning(f"No metadata found for '{filename}' at '{source_path}'")
                # Try to find a partial match (in case paths are different but filenames match)
                matched = False
                for cal_path, cal_meta in calibre_books_by_path.items():
                    if os.path.basename(cal_path) == filename:
                        source_meta.update(cal_meta)
                        logger.info(f"Applied metadata by filename match: '{cal_meta['title']}' to '{filename}'")
                        matched = True
                        break

                if not matched:
                    logger.warning(f"No metadata match found for '{filename}' - will copy with original name")

            dest_path = self.get_destination_path(destination, source_meta, dry_run)
            if not dest_path: continue
            dest_filename = os.path.basename(dest_path)

            # Log the transformation
            if filename != dest_filename:
                logger.debug(f"Renaming: '{filename}' → '{dest_filename}'")

            # Keep track of processed files
            processed_dest_files.add(dest_filename)

            # Check if file exists in destination
            if dest_filename not in dest_files:
                # File doesn't exist in destination, copy it
                if not dry_run:
                    try:
                        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                        shutil.copy2(source_meta["path"], dest_path)
                        stats["added"] += 1
                        stats["added_files"].append(dest_filename)
                        logger.info(f"Added: {dest_filename}")
                    except Exception as e:
                        stats["errors"] += 1
                        stats["error_files"].append(dest_filename)
                        logger.error(f"Error copying {dest_filename}: {e}")
                else:
                    stats["added"] += 1
                    stats["added_files"].append(dest_filename)
                    logger.info(f"Would add: {dest_filename}")
            else:
                # File exists, check if it's different
                dest_meta = dest_files[dest_filename]

                if source_meta["size"] != dest_meta["size"] or \
                        abs(source_meta["mtime"] - dest_meta["mtime"]) > 1:  # Allow 1 second difference
                    # Different size or modification time, compare hashes for certainty
                    source_hash = self.calculate_file_hash(source_meta["path"])
                    dest_hash = self.calculate_file_hash(dest_meta["path"])

                    if source_hash != dest_hash:
                        if not dry_run:
                            try:
                                shutil.copy2(source_meta["path"], dest_path)
                                stats["updated"] += 1
                                stats["updated_files"].append(dest_filename)
                                logger.info(f"Updated: {dest_filename}")
                            except Exception as e:
                                stats["errors"] += 1
                                stats["error_files"].append(dest_filename)
                                logger.error(f"Error updating {dest_filename}: {e}")
                        else:
                            stats["updated"] += 1
                            stats["updated_files"].append(dest_filename)
                            logger.info(f"Would update: {dest_filename}")
                    else:
                        stats["unchanged"] += 1
                else:
                    stats["unchanged"] += 1

        # Find files to delete (in dest but not in source)
        for dest_filename, dest_meta in dest_files.items():
            if dest_filename not in processed_dest_files:
                # Never delete essential Calibre system files
                if dest_filename in ['metadata.db', 'metadata_db_prefs_backup.json']:
                    logger.debug(f"Preserving Calibre system file: {dest_filename}")
                    continue
                
                if not dry_run:
                    try:
                        os.remove(dest_meta["path"])
                        stats["deleted"] += 1
                        stats["deleted_files"].append(dest_filename)
                        logger.info(f"Deleted: {dest_filename}")
                    except Exception as e:
                        stats["errors"] += 1
                        stats["error_files"].append(dest_filename)
                        logger.error(f"Error deleting {dest_filename}: {e}")
                else:
                    stats["deleted"] += 1
                    stats["deleted_files"].append(dest_filename)
                    logger.info(f"Would delete: {dest_filename}")

        logger.info(f"Sync completed. Stats: {stats}")
        return stats

    def sync_all(self, dry_run: bool = False) -> Dict[str, Dict]:
        """Sync the source to all replica destinations."""
        results = {}

        for replica in self.replica_paths:
            try:
                results[replica] = self.sync_folder(replica, dry_run)
            except Exception as e:
                logger.error(f"Failed to sync to {replica}: {e}")
                results[replica] = {"error": str(e)}

        return results


# Helper function to create a sync service from settings
def get_sync_service() -> SyncService:
    """Create a SyncService instance using settings."""
    return SyncService(
        source_path=settings.CALIBRE_LIBRARY_PATH,
        replica_paths=settings.replica_paths_list  # Use the property instead of REPLICA_PATHS directly
    )


# Function for direct use in scripts or API endpoints
def sync_folders(dry_run: bool = False) -> Dict[str, Dict]:
    """Synchronize the Calibre library to all replica locations."""
    sync_service = get_sync_service()
    return sync_service.sync_all(dry_run=dry_run)