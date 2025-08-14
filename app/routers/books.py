# app/routers/books_readonly.py
"""Read-only book listing router for ebook management."""

import os
import math
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, computed_field

from ..services.calibre_service import get_calibre_service, CalibreService
from ..services.library_service import get_library_service, LibraryService

router = APIRouter(tags=["books"])


@router.get("/libraries")
async def get_available_libraries():
    """Get list of available library locations."""
    # For now, return the main library. This can be extended to support multiple libraries
    libraries = [
        {"id": "library", "name": "Main Library", "description": "Primary ebook collection"}
        # Future: Add more libraries from configuration or database
        # {"id": "library2", "name": "Secondary Library", "description": "Additional collection"},
    ]
    return {"libraries": libraries}


def _get_file_size_for_format(book: dict, format_ext: str) -> Optional[int]:
    """Find file size for a given format extension."""
    from ..config import settings
    
    title = book.get("title", "Unknown")
    authors = book.get("authors", ["Unknown"])
    author = authors[0] if isinstance(authors, list) and authors else "Unknown"
    import re
    base_filename = f"{title} - {author}".replace("/", "-").replace("\\", "-").replace(":", "").replace("|", " ")
    # Collapse multiple spaces into double spaces (to match actual file naming)
    base_filename = re.sub(r' {3,}', '  ', base_filename)
    
    # Get the first library path from LIBRARY_PATHS
    library_paths = [path.strip() for path in settings.LIBRARY_PATHS.split(',') if path.strip()]
    library_path = library_paths[0] if library_paths else ""
    
    # Check root directory first (where mobi files usually are)
    if os.path.exists(library_path):
        for file in os.listdir(library_path):
            file_path = os.path.join(library_path, file)
            if (os.path.isfile(file_path) and 
                file.startswith(base_filename) and 
                file.lower().endswith(f'.{format_ext.lower()}')):
                try:
                    return os.path.getsize(file_path)
                except OSError:
                    continue
    
    # Check format directories
    format_dirs = ['epubs', 'pdfs', 'mobi', 'azw', 'azw3', 'txt', 'rtf', 'docx', 'kfx', 'original_epubs', 'original_mobi']
    for format_dir in format_dirs:
        format_path = os.path.join(library_path, format_dir)
        if os.path.exists(format_path):
            for file in os.listdir(format_path):
                if file.startswith(base_filename):
                    # Handle different file extensions based on directory
                    file_matches = False
                    if format_dir == 'original_epubs' and format_ext.lower() == 'epub' and file.lower().endswith('.original_epub'):
                        file_matches = True
                    elif format_dir == 'original_mobi' and format_ext.lower() == 'mobi' and file.lower().endswith('.original_mobi'):
                        file_matches = True
                    elif file.lower().endswith(f'.{format_ext.lower()}'):
                        file_matches = True
                    
                    if file_matches:
                        try:
                            return os.path.getsize(os.path.join(format_path, file))
                        except OSError:
                            continue
    
    return None


class Book(BaseModel):
    id: int
    title: str
    authors: List[str]
    formats: List[str] = []
    size: Optional[int] = None
    last_modified: Optional[float] = None
    path: Optional[str] = None

    @computed_field
    def formatted_size(self) -> Optional[str]:
        """Return size formatted in KB"""
        if self.size is None:
            return None
        return f"{self.size // 1024} KB"


class BookCollection(BaseModel):
    books: List[Book]
    total: int
    page: int = 1
    page_size: int = 50
    total_pages: int = 1


@router.get("/libraries/{location_id}/books", response_model=BookCollection)
async def list_books(
        location_id: str,
        page: int = Query(1, ge=1, description="Page number (1-based)"),
        page_size: int = Query(50, ge=1, le=200, description="Number of books per page (max 200)"),
        search: str = Query("", description="Search term to filter books by title or author"),
        calibre_service: CalibreService = Depends(get_calibre_service),
        library_service: LibraryService = Depends(get_library_service)
):
    """List books from specified location (calibre or replica)."""
    
    if location_id in ["library", "calibre"]:
        # Read from library database (via metadata.db in replica)
        try:
            books_data = calibre_service.get_books()
            books = []

            for book in books_data:
                # Handle authors correctly
                if isinstance(book.get("authors"), str):
                    authors = [book.get("authors")]
                elif isinstance(book.get("authors"), list):
                    authors = book.get("authors")
                else:
                    authors = ["Unknown"]


                # Fix format extraction - handle both file paths and extensions
                formats = []
                path = None
                size = None
                last_modified = None

                for fmt in book.get("formats", []):
                    try:
                        # Check if fmt is a file path or just an extension
                        if os.path.exists(fmt):
                            # It's a file path (original Calibre structure)
                            ext = os.path.splitext(fmt)[1].lstrip('.').lower()
                            if ext:
                                formats.append(ext)
                            if path is None:
                                path = fmt
                                stat = os.stat(fmt)
                                size = stat.st_size
                                last_modified = stat.st_mtime
                        else:
                            # It's just an extension (from filesystem detection)
                            formats.append(fmt.lower())
                            # Try to find actual file for size information
                            if size is None:
                                file_size = _get_file_size_for_format(book, fmt.lower())
                                if file_size:
                                    size = file_size
                    except (AttributeError, IndexError, FileNotFoundError):
                        continue

                books.append(Book(
                    id=book["id"],
                    title=book["title"],
                    authors=authors,
                    formats=formats,
                    size=size,
                    last_modified=last_modified,
                    path=path
                ))

            # Apply search filter if provided
            search_term = search.strip()
            if search_term:
                search_lower = search_term.lower()
                # Use filter with generator for memory efficiency
                def matches_search(book):
                    # Check title first (most common match)
                    if search_lower in book.title.lower():
                        return True
                    # Only check authors if title doesn't match
                    return any(search_lower in author.lower() for author in book.authors)
                
                books = [book for book in books if matches_search(book)]

            # Calculate pagination
            total_books = len(books)
            total_pages = math.ceil(total_books / page_size) if total_books > 0 else 1
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            paginated_books = books[start_index:end_index]

            return BookCollection(
                books=paginated_books, 
                total=total_books,
                page=page,
                page_size=page_size,
                total_pages=total_pages
            )
        except Exception as e:
            import logging
            logging.error(f"Error retrieving books: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrieving books: {str(e)}")

    elif location_id.startswith("library"):
        # Read from library directories
        try:
            library_index = int(location_id[7:]) - 1
            if library_index < 0 or library_index >= len(library_service.library_paths):
                raise ValueError("Invalid library index")
        except ValueError:
            raise HTTPException(status_code=404, detail=f"Location {location_id} not found")

        library_path = library_service.library_paths[library_index]
        library_files = library_service.get_library_files(library_path)
        
        books = []
        for file_data in library_files:
            books.append(Book(
                id=file_data['id'],
                title=file_data['title'],
                authors=file_data['authors'],
                formats=file_data['formats'],
                size=file_data['size'],
                last_modified=file_data['last_modified'],
                path=file_data['path']
            ))
        
        # Apply search filter if provided
        search_term = search.strip()
        if search_term:
            search_lower = search_term.lower()
            # Use filter with generator for memory efficiency
            def matches_search(book):
                # Check title first (most common match)
                if search_lower in book.title.lower():
                    return True
                # Only check authors if title doesn't match
                return any(search_lower in author.lower() for author in book.authors)
            
            books = [book for book in books if matches_search(book)]
        
        # Calculate pagination
        total_books = len(books)
        total_pages = math.ceil(total_books / page_size) if total_books > 0 else 1
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        paginated_books = books[start_index:end_index]

        return BookCollection(
            books=paginated_books, 
            total=total_books,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
    
    else:
        raise HTTPException(status_code=404, detail=f"Location {location_id} not found")


@router.get("/books/search")
async def search_books(
        q: str,
        calibre_service: CalibreService = Depends(get_calibre_service)
):
    """Search books in the library."""
    try:
        books_data = calibre_service.search_books(q)
        books = []

        for book in books_data:
            # Handle authors correctly
            if isinstance(book.get("authors"), str):
                authors = [book.get("authors")]
            elif isinstance(book.get("authors"), list):
                authors = book.get("authors")
            else:
                authors = ["Unknown"]

            # Fix format extraction
            formats = []
            path = None
            size = None
            last_modified = None

            for fmt in book.get("formats", []):
                try:
                    ext = os.path.splitext(fmt)[1].lstrip('.').lower()
                    if ext:
                        formats.append(ext)

                    if path is None and os.path.exists(fmt):
                        path = fmt
                        stat = os.stat(fmt)
                        size = stat.st_size
                        last_modified = stat.st_mtime
                except (AttributeError, IndexError, FileNotFoundError):
                    continue

            books.append(Book(
                id=book["id"],
                title=book["title"],
                authors=authors,
                formats=formats,
                size=size,
                last_modified=last_modified,
                path=path
            ))

        return BookCollection(books=books, total=len(books))
    except Exception as e:
        import logging
        logging.error(f"Error searching books: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error searching books: {str(e)}")


@router.get("/books/{book_id}/metadata")
async def get_book_metadata(
        book_id: int,
        calibre_service: CalibreService = Depends(get_calibre_service)
):
    """Get detailed metadata for a book."""
    try:
        # Get basic book information from the book list
        books_data = calibre_service.get_books()
        book = None
        
        for b in books_data:
            if b["id"] == book_id:
                book = b
                break
        
        if not book:
            raise HTTPException(status_code=404, detail=f"Book with ID {book_id} not found")
        
        # Create proper metadata response that the UI expects
        metadata = {
            "id": book["id"],
            "title": book.get("title", "Unknown"),
            "authors": book.get("authors", ["Unknown"]),
            "publisher": book.get("publisher"),
            "published": book.get("published"),
            "isbn": book.get("isbn"),
            "tags": book.get("tags", []),
            "rating": book.get("rating"),
            "comments": book.get("comments"),
            "series": book.get("series"),
            "series_index": book.get("series_index"),
            "language": book.get("language")
        }
        
        # Return in the format the UI expects
        return {"metadata": metadata}
        
    except Exception as e:
        import logging
        logging.error(f"Error retrieving book metadata: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving metadata: {str(e)}")


@router.get("/books/{book_id}/cover")
async def get_book_cover(
        book_id: int,
        calibre_service: CalibreService = Depends(get_calibre_service)
):
    """Get the cover image for a book."""
    try:
        cover_path = calibre_service.get_cover_path(book_id)

        if not cover_path or not os.path.exists(cover_path):
            # Log info for debugging but return proper 404
            import logging
            logging.info(f"No cover found for book ID {book_id}")
            raise HTTPException(status_code=404, detail=f"Cover for book {book_id} not found")

        return FileResponse(cover_path, media_type='image/jpeg')
        
    except Exception as e:
        import logging  
        logging.error(f"Error retrieving cover for book {book_id}: {str(e)}")
        raise HTTPException(status_code=404, detail=f"Cover for book {book_id} not found")


@router.get("/books/{book_id}/download")
async def download_book(
        book_id: int,
        format: Optional[str] = None,
        calibre_service: CalibreService = Depends(get_calibre_service)
):
    """Download a book file in the specified format."""
    try:
        # Get book metadata to find title and authors
        books_data = calibre_service.get_books()
        book = None
        
        for b in books_data:
            if b["id"] == book_id:
                book = b
                break
        
        if not book:
            raise HTTPException(status_code=404, detail=f"Book with ID {book_id} not found")
        
        # Get title and authors for filename matching
        title = book.get("title", "Unknown")
        authors = book.get("authors", ["Unknown"])
        author = authors[0] if isinstance(authors, list) else str(authors)
        
        # Create expected filename pattern: "Title - Author"
        import re
        base_filename = f"{title} - {author}".replace("/", "-").replace("\\", "-").replace(":", "").replace("|", " ")
        # Collapse multiple spaces into double spaces (to match actual file naming)
        base_filename = re.sub(r' {3,}', '  ', base_filename)
        
        # Get library path from config
        from ..config import settings
        # Get the first library path from LIBRARY_PATHS
        library_paths = [path.strip() for path in settings.LIBRARY_PATHS.split(',') if path.strip()]
        library_path = library_paths[0] if library_paths else ""
        
        # Search for files in the synchronized library structure
        available_files = []
        format_dirs = ['epubs', 'pdfs', 'mobi', 'azw', 'azw3', 'txt', 'rtf', 'docx', 'kfx', 'original_epubs', 'original_mobi']
        
        for format_dir in format_dirs:
            format_path = os.path.join(library_path, format_dir)
            if os.path.exists(format_path):
                for file in os.listdir(format_path):
                    if file.startswith(base_filename):
                        file_path = os.path.join(format_path, file)
                        if os.path.isfile(file_path):
                            available_files.append(file_path)
        
        # Also check root directory for files
        for file in os.listdir(library_path):
            if file.startswith(base_filename) and os.path.isfile(os.path.join(library_path, file)):
                available_files.append(os.path.join(library_path, file))
        
        if not available_files:
            raise HTTPException(status_code=404, detail=f"No files available for book {book_id}")
        
        # Find the requested format or use the first available
        file_path = None
        if format:
            # Look for specific format
            format_lower = format.lower()
            for file in available_files:
                if file.lower().endswith(f'.{format_lower}'):
                    file_path = file
                    break
            if not file_path:
                available_formats = [os.path.splitext(f)[1].lstrip('.') for f in available_files]
                raise HTTPException(
                    status_code=404, 
                    detail=f"Format '{format}' not available for book {book_id}. Available formats: {available_formats}"
                )
        else:
            # Use first available format, preferring epub
            for file in available_files:
                if file.lower().endswith('.epub'):
                    file_path = file
                    break
            if not file_path:
                file_path = available_files[0]
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"Book file not found: {file_path}")
        
        # Use the actual filename for download
        filename = os.path.basename(file_path)
        
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type='application/octet-stream'
        )
        
    except Exception as e:
        import logging
        logging.error(f"Error downloading book {book_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error downloading book: {str(e)}")


@router.get("/libraries/{location_id}/books/{book_id}/download")
async def download_book_from_library(
        location_id: str,
        book_id: int,
        format: Optional[str] = None,
        library_service: LibraryService = Depends(get_library_service)
):
    """Download a book file from a specific library location."""
    if location_id in ["library", "calibre"]:
        # Redirect to main download endpoint for library books
        return await download_book(book_id, format)
    
    elif location_id.startswith("library"):
        try:
            library_index = int(location_id[7:]) - 1
            if library_index < 0 or library_index >= len(library_service.library_paths):
                raise ValueError("Invalid library index")
        except ValueError:
            raise HTTPException(status_code=404, detail=f"Location {location_id} not found")

        library_path = library_service.library_paths[library_index]
        library_files = library_service.get_library_files(library_path)
        
        # Find the book by ID
        book_file = None
        for file_data in library_files:
            if file_data['id'] == book_id:
                book_file = file_data
                break
        
        if not book_file:
            raise HTTPException(status_code=404, detail=f"Book with ID {book_id} not found in {location_id}")
        
        file_path = book_file['path']
        
        # Check if specific format is requested
        if format:
            format_lower = format.lower()
            file_ext = os.path.splitext(file_path)[1].lstrip('.').lower()
            if file_ext != format_lower:
                raise HTTPException(
                    status_code=404, 
                    detail=f"Format '{format}' not available. Available format: {file_ext}"
                )
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"Book file not found: {file_path}")
        
        # Use the original filename for download
        filename = book_file['filename']
        
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type='application/octet-stream'
        )
    
    else:
        raise HTTPException(status_code=404, detail=f"Location {location_id} not found")