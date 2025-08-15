"""Enhanced Calibre service that works with preserved Calibre directory structure."""

import os
import json
import subprocess
import logging
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from pathlib import Path
from functools import lru_cache

from ..config import settings


logger = logging.getLogger("calibre_service_enhanced")


class CalibreServiceEnhanced:
    """Enhanced Calibre service that works with preserved Calibre directory structure."""
    
    def __init__(self, library_path: str):
        """Initialize with path to Calibre library using preserved directory structure."""
        self.library_path = library_path
        self._books_cache = None
        self._cache_timestamp = None
    
    def get_books(self) -> List[Dict[str, Any]]:
        """Get books from the preserved Calibre directory structure."""
        books = []
        
        if not os.path.exists(self.library_path):
            logger.error(f"Library path does not exist: {self.library_path}")
            return books

        # Scan the directory structure for author directories
        try:
            for author_dir in os.listdir(self.library_path):
                author_path = os.path.join(self.library_path, author_dir)
                
                # Skip files and non-directories
                if not os.path.isdir(author_path) or author_dir.startswith('.'):
                    continue
                
                # Skip system files
                if author_dir.lower() in ['metadata.db', 'metadata_db_prefs_backup.json']:
                    continue
                
                # Scan book directories within author directory
                try:
                    for book_dir in os.listdir(author_path):
                        book_path = os.path.join(author_path, book_dir)
                        
                        if not os.path.isdir(book_path):
                            continue
                        
                        book_data = self._extract_book_data(author_dir, book_dir, book_path)
                        if book_data:
                            books.append(book_data)
                            
                except OSError as e:
                    logger.warning(f"Error scanning author directory {author_path}: {e}")
                    continue
                    
        except OSError as e:
            logger.error(f"Error scanning library directory {self.library_path}: {e}")
            return books
        
        # Sort books by title
        books.sort(key=lambda x: x.get('title', '').lower())
        
        logger.info(f"Found {len(books)} books in Calibre directory structure")
        return books
    
    def _extract_book_data(self, author_name: str, book_dir: str, book_path: str) -> Optional[Dict[str, Any]]:
        """Extract book data from a Calibre book directory."""
        try:
            # Extract book ID from directory name (format: "Title (ID)")
            book_id = None
            if book_dir.endswith(')') and '(' in book_dir:
                try:
                    book_id = int(book_dir.split('(')[-1].rstrip(')'))
                except ValueError:
                    logger.warning(f"Could not extract ID from directory name: {book_dir}")
            
            if book_id is None:
                # Generate a hash-based ID if we can't extract from directory name
                import hashlib
                book_id = abs(hash(f"{author_name}_{book_dir}")) % (10**8)
            
            # Get title from directory name (remove ID part)
            title = book_dir
            if '(' in book_dir and book_dir.endswith(')'):
                title = book_dir.rsplit('(', 1)[0].strip()
            
            # Check for metadata.opf file
            tags = []
            metadata_path = os.path.join(book_path, 'metadata.opf')
            if os.path.exists(metadata_path):
                try:
                    metadata = self._parse_opf_metadata(metadata_path)
                    if metadata:
                        title = metadata.get('title', title)
                        author_name = metadata.get('authors', [author_name])[0] if metadata.get('authors') else author_name
                        tags = metadata.get('tags', [])
                except Exception as e:
                    logger.debug(f"Could not parse metadata.opf for {book_dir}: {e}")
            
            # Find all ebook format files in the directory
            formats = []
            format_files = {}
            cover_path = None
            
            for filename in os.listdir(book_path):
                file_path = os.path.join(book_path, filename)
                
                if not os.path.isfile(file_path):
                    continue
                
                # Check for cover image
                if filename.lower() == 'cover.jpg':
                    cover_path = file_path
                    continue
                
                # Check for ebook formats
                _, ext = os.path.splitext(filename.lower())
                if ext in ['.epub', '.mobi', '.azw', '.azw3', '.pdf', '.txt', '.rtf', '.docx']:
                    format_ext = ext.lstrip('.')
                    
                    # Handle original formats
                    if filename.lower().endswith('.original_epub'):
                        format_ext = 'epub'
                    elif filename.lower().endswith('.original_mobi'):
                        format_ext = 'mobi'
                    elif filename.lower().endswith('.original_azw3'):
                        format_ext = 'azw3'
                    
                    if format_ext not in formats:
                        formats.append(format_ext)
                    format_files[format_ext] = file_path
            
            # Get file stats from first available format file
            size = None
            last_modified = None
            main_file_path = None
            
            if format_files:
                # Prefer epub, then mobi, then others
                for preferred_format in ['epub', 'mobi', 'azw3', 'pdf']:
                    if preferred_format in format_files:
                        main_file_path = format_files[preferred_format]
                        break
                
                if not main_file_path:
                    main_file_path = list(format_files.values())[0]
                
                try:
                    stat_info = os.stat(main_file_path)
                    size = stat_info.st_size
                    last_modified = stat_info.st_mtime
                except OSError:
                    pass
            
            return {
                'id': book_id,
                'title': title,
                'authors': [author_name],
                'formats': formats,
                'format_files': format_files,  # Additional info for file access
                'size': size,
                'last_modified': last_modified,
                'path': main_file_path,
                'cover_path': cover_path,
                'book_directory': book_path,
                'tags': tags
            }
            
        except Exception as e:
            logger.error(f"Error extracting book data from {book_path}: {e}")
            return None
    
    def _parse_opf_metadata(self, opf_path: str) -> Optional[Dict[str, Any]]:
        """Parse OPF metadata file to extract book information."""
        try:
            tree = ET.parse(opf_path)
            root = tree.getroot()
            
            # Define namespace
            namespaces = {
                'opf': 'http://www.idpf.org/2007/opf',
                'dc': 'http://purl.org/dc/elements/1.1/'
            }
            
            metadata = {}
            
            # Extract title
            title_elem = root.find('.//dc:title', namespaces)
            if title_elem is not None and title_elem.text:
                metadata['title'] = title_elem.text.strip()
            
            # Extract authors
            authors = []
            for creator_elem in root.findall('.//dc:creator', namespaces):
                if creator_elem.text:
                    authors.append(creator_elem.text.strip())
            if authors:
                metadata['authors'] = authors
            
            # Extract other metadata
            for field in ['publisher', 'language', 'description']:
                elem = root.find(f'.//dc:{field}', namespaces)
                if elem is not None and elem.text:
                    metadata[field] = elem.text.strip()
            
            # Extract publication date
            date_elem = root.find('.//dc:date', namespaces)
            if date_elem is not None and date_elem.text:
                metadata['published'] = date_elem.text.strip()
            
            # Extract identifiers (ISBN, etc.)
            identifiers = {}
            for identifier_elem in root.findall('.//dc:identifier', namespaces):
                scheme = identifier_elem.get('scheme') or identifier_elem.get('{http://www.idpf.org/2007/opf}scheme')
                if scheme and identifier_elem.text:
                    identifiers[scheme.lower()] = identifier_elem.text.strip()
            if identifiers:
                metadata['identifiers'] = identifiers
                if 'isbn' in identifiers:
                    metadata['isbn'] = identifiers['isbn']
            
            # Extract tags/subjects
            tags = []
            for subject_elem in root.findall('.//dc:subject', namespaces):
                if subject_elem.text:
                    tags.append(subject_elem.text.strip())
            if tags:
                metadata['tags'] = tags
            
            return metadata
            
        except Exception as e:
            logger.debug(f"Error parsing OPF file {opf_path}: {e}")
            return None
    
    def get_book_by_id(self, book_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific book."""
        books = self.get_books()
        for book in books:
            if book['id'] == book_id:
                return book
        return None
    
    def get_cover_path(self, book_id: int) -> Optional[str]:
        """Get the path to a book's cover image - now directly from cover.jpg."""
        book = self.get_book_by_id(book_id)
        if book and book.get('cover_path') and os.path.exists(book['cover_path']):
            return book['cover_path']
        return None
    
    def get_book_file_path(self, book_id: int, format_type: Optional[str] = None) -> Optional[str]:
        """Get the file path for a specific book format."""
        book = self.get_book_by_id(book_id)
        if not book:
            return None
        
        format_files = book.get('format_files', {})
        
        if format_type:
            # Return specific format if requested
            return format_files.get(format_type.lower())
        else:
            # Return preferred format (epub > mobi > others)
            for preferred_format in ['epub', 'mobi', 'azw3', 'pdf']:
                if preferred_format in format_files:
                    return format_files[preferred_format]
            
            # Return any available format
            if format_files:
                return list(format_files.values())[0]
        
        return None
    
    def search_books(self, query: str) -> List[Dict[str, Any]]:
        """Search for books by title or author."""
        all_books = self.get_books()
        query_lower = query.lower().strip()
        
        if not query_lower:
            return all_books
        
        matching_books = []
        for book in all_books:
            # Search in title
            if query_lower in book.get('title', '').lower():
                matching_books.append(book)
                continue
            
            # Search in authors
            authors = book.get('authors', [])
            if any(query_lower in author.lower() for author in authors):
                matching_books.append(book)
                continue
        
        return matching_books
    
    def get_book_metadata_detailed(self, book_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed metadata for a book, including OPF data."""
        book = self.get_book_by_id(book_id)
        if not book:
            return None
        
        # Start with basic book data
        metadata = {
            'id': book['id'],
            'title': book.get('title'),
            'authors': book.get('authors', []),
            'formats': book.get('formats', [])
        }
        
        # Try to get additional metadata from OPF file
        book_directory = book.get('book_directory')
        if book_directory:
            opf_path = os.path.join(book_directory, 'metadata.opf')
            if os.path.exists(opf_path):
                opf_metadata = self._parse_opf_metadata(opf_path)
                if opf_metadata:
                    metadata.update(opf_metadata)
        
        return metadata
    




# Create a singleton instance
@lru_cache()
def get_calibre_service_enhanced() -> CalibreServiceEnhanced:
    """Get a CalibreServiceEnhanced instance configured with settings."""
    if not hasattr(settings, 'LIBRARY_PATHS') or not settings.LIBRARY_PATHS:
        logger.critical("LIBRARY_PATHS is not configured in settings.")
        raise ValueError("LIBRARY_PATHS must be set in configuration.")

    # Get the first library path from the comma-separated list
    library_paths = [path.strip() for path in settings.LIBRARY_PATHS.split(',') if path.strip()]
    if not library_paths:
        logger.critical("No valid library paths found in LIBRARY_PATHS.")
        raise ValueError("At least one library path must be configured.")
    
    primary_library_path = library_paths[0]

    if not os.path.isdir(primary_library_path):
        logger.warning(f"Library path '{primary_library_path}' does not exist or is not a directory.")

    return CalibreServiceEnhanced(library_path=primary_library_path)