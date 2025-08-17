"""
Direct Calibre Database Service
Reads directly from Calibre's metadata.db SQLite database for optimal performance.
"""
import sqlite3
import os
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

logger = logging.getLogger("calibre_db_service")


class CalibreDbService:
    """Service that reads directly from Calibre's metadata.db for optimal performance."""
    
    def __init__(self, library_path: str):
        """Initialize with path to Calibre library."""
        self.library_path = library_path
        self.db_path = os.path.join(library_path, "metadata.db")
        
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"Calibre database not found at {self.db_path}")
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with optimized settings."""
        # Shorter timeout for network-mounted databases
        timeout = 5.0 if self._is_network_path() else 30.0
        conn = sqlite3.Connection(self.db_path, timeout=timeout)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        
        # Optimize for network performance
        if self._is_network_path():
            # More aggressive optimizations for network paths
            conn.execute("PRAGMA journal_mode=MEMORY")  # Keep journal in memory
            conn.execute("PRAGMA synchronous=OFF")       # Disable sync for reading
            conn.execute("PRAGMA cache_size=50000")      # Larger cache
            conn.execute("PRAGMA temp_store=MEMORY")
            conn.execute("PRAGMA mmap_size=0")           # Disable memory mapping for network
        else:
            # Standard optimizations for local paths
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=10000")
            conn.execute("PRAGMA temp_store=MEMORY")
        
        return conn
    
    def _is_network_path(self) -> bool:
        """Check if the database is on a network mount."""
        return "/mnt/" in self.library_path or "192.168" in self.library_path
    
    def get_books_paginated(self, offset: int = 0, limit: int = 50, 
                           search: Optional[str] = None, 
                           tag_filter: Optional[str] = None) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get paginated list of books with optional search and tag filtering.
        Returns (books, total_count).
        """
        with self._get_connection() as conn:
            # Base query with all necessary joins
            base_query = """
                SELECT 
                    b.id,
                    b.title,
                    b.sort as title_sort,
                    b.timestamp as date_added,
                    b.last_modified,
                    b.series_index,
                    b.isbn,
                    b.lccn,
                    b.path,
                    b.uuid,
                    b.has_cover,
                    GROUP_CONCAT(a.name, ' & ') as authors,
                    s.name as series_name,
                    p.name as publisher,
                    c.text as comments,
                    r.rating,
                    GROUP_CONCAT(t.name) as tags,
                    GROUP_CONCAT(UPPER(d.format)) as formats
                FROM books b
                LEFT JOIN books_authors_link bal ON b.id = bal.book
                LEFT JOIN authors a ON bal.author = a.id
                LEFT JOIN books_series_link bsl ON b.id = bsl.book
                LEFT JOIN series s ON bsl.series = s.id
                LEFT JOIN books_publishers_link bpl ON b.id = bpl.book
                LEFT JOIN publishers p ON bpl.publisher = p.id
                LEFT JOIN comments c ON b.id = c.book
                LEFT JOIN books_ratings_link brl ON b.id = brl.book
                LEFT JOIN ratings r ON brl.rating = r.id
                LEFT JOIN books_tags_link btl ON b.id = btl.book
                LEFT JOIN tags t ON btl.tag = t.id
                LEFT JOIN data d ON b.id = d.book
            """
            
            where_conditions = []
            params = []
            
            # Add search filter
            if search:
                search_condition = """
                    (b.title LIKE ? OR 
                     a.name LIKE ? OR 
                     c.text LIKE ? OR
                     t.name LIKE ?)
                """
                where_conditions.append(search_condition)
                search_param = f"%{search}%"
                params.extend([search_param, search_param, search_param, search_param])
            
            # Add tag filter
            if tag_filter:
                where_conditions.append("t.name LIKE ?")
                params.append(f"%{tag_filter}%")
            
            # Build complete query
            if where_conditions:
                base_query += " WHERE " + " AND ".join(where_conditions)
            
            base_query += " GROUP BY b.id ORDER BY b.sort LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            # Get total count
            count_query = """
                SELECT COUNT(DISTINCT b.id) as total
                FROM books b
                LEFT JOIN books_authors_link bal ON b.id = bal.book
                LEFT JOIN authors a ON bal.author = a.id
                LEFT JOIN comments c ON b.id = c.book
                LEFT JOIN books_tags_link btl ON b.id = btl.book
                LEFT JOIN tags t ON btl.tag = t.id
            """
            
            if where_conditions:
                count_query += " WHERE " + " AND ".join(where_conditions)
            
            # Execute count query (without limit/offset params)
            total_count = conn.execute(count_query, params[:-2]).fetchone()['total']
            
            # Execute main query
            cursor = conn.execute(base_query, params)
            books = []
            
            for row in cursor:
                # Get cover path
                cover_path = None
                if row['has_cover']:
                    book_dir = os.path.join(self.library_path, row['path'])
                    cover_file = os.path.join(book_dir, 'cover.jpg')
                    if os.path.exists(cover_file):
                        cover_path = cover_file
                
                # Parse formats
                formats = []
                if row['formats']:
                    formats = [fmt.strip() for fmt in row['formats'].split(',') if fmt.strip()]
                
                # Parse tags
                tags = []
                if row['tags']:
                    tags = [tag.strip() for tag in row['tags'].split(',') if tag.strip()]
                
                # Parse authors
                authors = []
                if row['authors']:
                    authors = [author.strip() for author in row['authors'].split(' & ') if author.strip()]
                
                book = {
                    'id': row['id'],
                    'title': row['title'] or 'Unknown Title',
                    'authors': authors,
                    'series_name': row['series_name'],
                    'series_index': row['series_index'],
                    'publisher': row['publisher'],
                    'comments': row['comments'],
                    'rating': row['rating'],
                    'tags': tags,
                    'formats': formats,
                    'isbn': row['isbn'],
                    'uuid': row['uuid'],
                    'date_added': row['date_added'],
                    'last_modified': row['last_modified'],
                    'cover_path': cover_path,
                    'path': row['path']
                }
                books.append(book)
            
            return books, total_count
    
    def get_book_by_id(self, book_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific book."""
        books, _ = self.get_books_paginated(offset=0, limit=1)
        # Find the book by filtering on ID in the query
        with self._get_connection() as conn:
            query = """
                SELECT DISTINCT
                    b.id,
                    b.title,
                    b.sort as title_sort,
                    b.timestamp as date_added,
                    b.last_modified,
                    b.series_index,
                    b.isbn,
                    b.lccn,
                    b.path,
                    b.uuid,
                    b.has_cover,
                    GROUP_CONCAT(a.name, ' & ') as authors,
                    s.name as series_name,
                    p.name as publisher,
                    c.text as comments,
                    r.rating,
                    GROUP_CONCAT(t.name) as tags,
                    GROUP_CONCAT(UPPER(d.format)) as formats
                FROM books b
                LEFT JOIN books_authors_link bal ON b.id = bal.book
                LEFT JOIN authors a ON bal.author = a.id
                LEFT JOIN books_series_link bsl ON b.id = bsl.book
                LEFT JOIN series s ON bsl.series = s.id
                LEFT JOIN books_publishers_link bpl ON b.id = bpl.book
                LEFT JOIN publishers p ON bpl.publisher = p.id
                LEFT JOIN comments c ON b.id = c.book
                LEFT JOIN books_ratings_link brl ON b.id = brl.book
                LEFT JOIN ratings r ON brl.rating = r.id
                LEFT JOIN books_tags_link btl ON b.id = btl.book
                LEFT JOIN tags t ON btl.tag = t.id
                LEFT JOIN data d ON b.id = d.book
                WHERE b.id = ?
                GROUP BY b.id
            """
            
            row = conn.execute(query, (book_id,)).fetchone()
            if not row:
                return None
            
            # Get cover path
            cover_path = None
            if row['has_cover']:
                book_dir = os.path.join(self.library_path, row['path'])
                cover_file = os.path.join(book_dir, 'cover.jpg')
                if os.path.exists(cover_file):
                    cover_path = cover_file
            
            # Parse formats
            formats = []
            if row['formats']:
                formats = [fmt.strip() for fmt in row['formats'].split(',') if fmt.strip()]
            
            # Parse tags
            tags = []
            if row['tags']:
                tags = [tag.strip() for tag in row['tags'].split(',') if tag.strip()]
            
            # Parse authors
            authors = []
            if row['authors']:
                authors = [author.strip() for author in row['authors'].split(' & ') if author.strip()]
            
            return {
                'id': row['id'],
                'title': row['title'] or 'Unknown Title',
                'authors': authors,
                'series_name': row['series_name'],
                'series_index': row['series_index'],
                'publisher': row['publisher'],
                'comments': row['comments'],
                'rating': row['rating'],
                'tags': tags,
                'formats': formats,
                'isbn': row['isbn'],
                'uuid': row['uuid'],
                'date_added': row['date_added'],
                'last_modified': row['last_modified'],
                'cover_path': cover_path,
                'path': row['path']
            }
    
    def search_books(self, query: str, offset: int = 0, limit: int = 50) -> Tuple[List[Dict[str, Any]], int]:
        """Search for books in the library with pagination."""
        return self.get_books_paginated(offset=offset, limit=limit, search=query)
    
    def get_cover_path(self, book_id: int) -> Optional[str]:
        """Get the path to a book's cover image."""
        book = self.get_book_by_id(book_id)
        if book and book.get('cover_path'):
            return book['cover_path']
        return None
    
    def get_all_tags(self) -> List[str]:
        """Get all unique tags in the library."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT DISTINCT name FROM tags ORDER BY name")
            return [row['name'] for row in cursor]
    
    def get_all_authors(self) -> List[str]:
        """Get all unique authors in the library."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT DISTINCT name FROM authors ORDER BY sort")
            return [row['name'] for row in cursor]
    
    def get_all_series(self) -> List[str]:
        """Get all unique series in the library."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT DISTINCT name FROM series ORDER BY sort")
            return [row['name'] for row in cursor]
    
    def get_library_stats(self) -> Dict[str, Any]:
        """Get statistics about the library."""
        with self._get_connection() as conn:
            stats = {}
            
            # Total books
            stats['total_books'] = conn.execute("SELECT COUNT(*) as count FROM books").fetchone()['count']
            
            # Total authors
            stats['total_authors'] = conn.execute("SELECT COUNT(*) as count FROM authors").fetchone()['count']
            
            # Total series
            stats['total_series'] = conn.execute("SELECT COUNT(*) as count FROM series").fetchone()['count']
            
            # Total tags
            stats['total_tags'] = conn.execute("SELECT COUNT(*) as count FROM tags").fetchone()['count']
            
            # Format distribution
            cursor = conn.execute("""
                SELECT UPPER(format) as format, COUNT(*) as count 
                FROM data 
                GROUP BY UPPER(format) 
                ORDER BY count DESC
            """)
            stats['format_distribution'] = {row['format']: row['count'] for row in cursor}
            
            return stats