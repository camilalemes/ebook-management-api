# app/routers/books_readonly.py
"""Read-only book listing router for ebook management."""

import os
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, computed_field

from ..services.calibre_service import get_calibre_service, CalibreService
from ..services.library_service import get_library_service, LibraryService

router = APIRouter(tags=["books"])


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


@router.get("/libraries/{location_id}/books", response_model=BookCollection)
async def list_books(
        location_id: str,
        calibre_service: CalibreService = Depends(get_calibre_service),
        library_service: LibraryService = Depends(get_library_service)
):
    """List books from specified location (calibre or replica)."""
    
    if location_id == "calibre":
        # Read from Calibre database (via metadata.db in replica)
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
            logging.error(f"Error retrieving Calibre books: {str(e)}")
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
        
        return BookCollection(books=books, total=len(books))
    
    else:
        raise HTTPException(status_code=404, detail=f"Location {location_id} not found")


@router.get("/books/search")
async def search_books(
        q: str,
        calibre_service: CalibreService = Depends(get_calibre_service)
):
    """Search books in the Calibre library."""
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
        metadata = calibre_service.get_book_metadata(book_id)
        if not metadata:
            raise HTTPException(status_code=404, detail=f"Book with ID {book_id} not found")
        return metadata
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
    cover_path = calibre_service.get_cover_path(book_id)

    if not cover_path or not os.path.exists(cover_path):
        raise HTTPException(status_code=404, detail=f"Cover for book {book_id} not found")

    return FileResponse(cover_path)


@router.get("/books/{book_id}/download")
async def download_book(
        book_id: int,
        format: Optional[str] = None,
        calibre_service: CalibreService = Depends(get_calibre_service)
):
    """Download a book file in the specified format."""
    try:
        # Get book metadata to find available formats
        books_data = calibre_service.get_books()
        book = None
        
        for b in books_data:
            if b["id"] == book_id:
                book = b
                break
        
        if not book:
            raise HTTPException(status_code=404, detail=f"Book with ID {book_id} not found")
        
        formats = book.get("formats", [])
        if not formats:
            raise HTTPException(status_code=404, detail=f"No files available for book {book_id}")
        
        # Find the requested format or use the first available
        file_path = None
        if format:
            # Look for specific format
            format_lower = format.lower()
            for fmt in formats:
                if fmt.lower().endswith(f'.{format_lower}'):
                    file_path = fmt
                    break
            if not file_path:
                raise HTTPException(
                    status_code=404, 
                    detail=f"Format '{format}' not available for book {book_id}. Available formats: {[os.path.splitext(f)[1].lstrip('.') for f in formats]}"
                )
        else:
            # Use first available format
            file_path = formats[0]
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"Book file not found: {file_path}")
        
        # Get clean filename for download
        filename = os.path.basename(file_path)
        if not filename or filename.startswith('.'):
            # Generate filename from book title and format
            title = book.get("title", "Unknown")
            authors = book.get("authors", ["Unknown"])
            author = authors[0] if isinstance(authors, list) else str(authors)
            ext = os.path.splitext(file_path)[1]
            filename = f"{title} - {author}{ext}"
        
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
    if location_id == "calibre":
        # Redirect to main download endpoint for Calibre books
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