"""
Enhanced book router using direct Calibre database access for optimal performance.
"""
import os
import math
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, computed_field

from ..services.calibre_db_service import CalibreDbService
from ..config import settings

router = APIRouter(tags=["books"])


class Book(BaseModel):
    """Enhanced book model with all metadata."""
    id: int
    title: str
    authors: List[str] = []
    series_name: Optional[str] = None
    series_index: Optional[float] = None
    publisher: Optional[str] = None
    comments: Optional[str] = None
    rating: Optional[int] = None
    tags: List[str] = []
    formats: List[str] = []
    isbn: Optional[str] = None
    uuid: Optional[str] = None
    date_added: Optional[str] = None
    last_modified: Optional[str] = None
    cover_available: bool = False
    path: Optional[str] = None


class BookCollection(BaseModel):
    """Paginated collection of books."""
    books: List[Book]
    total: int
    page: int = 1
    page_size: int = 50
    total_pages: int = 1


class LibraryInfo(BaseModel):
    """Library information."""
    id: str
    name: str
    description: str
    path: str
    total_books: int


class LibrariesResponse(BaseModel):
    """Response containing available libraries."""
    libraries: List[LibraryInfo]


def get_calibre_db_service(library_path: str) -> CalibreDbService:
    """Get a CalibreDbService instance for the specified library path."""
    return CalibreDbService(library_path)


def get_library_paths() -> List[str]:
    """Get configured library paths."""
    if not hasattr(settings, 'LIBRARY_PATHS') or not settings.LIBRARY_PATHS:
        raise HTTPException(status_code=500, detail="No library paths configured")
    
    library_paths = [path.strip() for path in settings.LIBRARY_PATHS.split(',') if path.strip()]
    if not library_paths:
        raise HTTPException(status_code=500, detail="No valid library paths found")
    
    return library_paths


@router.get("/libraries", response_model=LibrariesResponse)
async def get_available_libraries():
    """Get list of available library locations with statistics."""
    library_paths = get_library_paths()
    libraries = []
    
    for i, library_path in enumerate(library_paths):
        try:
            db_service = get_calibre_db_service(library_path)
            stats = db_service.get_library_stats()
            
            # Determine library name based on path
            library_name = f"Library {i + 1}"
            if "Books" in library_path:
                library_name = "Main Library"
            elif "NAS" in library_path or "192.168" in library_path:
                library_name = "NAS Library"
            
            libraries.append(LibraryInfo(
                id=f"library{i + 1}",
                name=library_name,
                description=f"Calibre library at {library_path}",
                path=library_path,
                total_books=stats['total_books']
            ))
        except Exception as e:
            # Skip libraries that can't be accessed
            continue
    
    if not libraries:
        raise HTTPException(status_code=500, detail="No accessible libraries found")
    
    return LibrariesResponse(libraries=libraries)


@router.get("/libraries/{library_id}/books", response_model=BookCollection)
async def list_books(
    library_id: str,
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(50, ge=1, le=200, description="Number of books per page"),
    search: Optional[str] = Query(None, description="Search term to filter books"),
    tag_filter: Optional[str] = Query(None, description="Filter books by tag (e.g., 'mistyebook')")
):
    """List books from specified library with pagination and filtering."""
    library_paths = get_library_paths()
    
    # Parse library ID
    try:
        if library_id == "library1":
            library_index = 0
        elif library_id.startswith("library"):
            library_index = int(library_id[7:]) - 1
        else:
            raise ValueError("Invalid library ID format")
        
        if library_index < 0 or library_index >= len(library_paths):
            raise ValueError("Library index out of range")
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Library {library_id} not found")
    
    library_path = library_paths[library_index]
    
    try:
        db_service = get_calibre_db_service(library_path)
        
        # Calculate offset
        offset = (page - 1) * page_size
        
        # Get paginated results
        books_data, total_count = db_service.get_books_paginated(
            offset=offset,
            limit=page_size,
            search=search,
            tag_filter=tag_filter
        )
        
        # Convert to API models
        books = []
        for book_data in books_data:
            book = Book(
                id=book_data['id'],
                title=book_data['title'],
                authors=book_data['authors'],
                series_name=book_data['series_name'],
                series_index=book_data['series_index'],
                publisher=book_data['publisher'],
                comments=book_data['comments'],
                rating=book_data['rating'],
                tags=book_data['tags'],
                formats=book_data['formats'],
                isbn=book_data['isbn'],
                uuid=book_data['uuid'],
                date_added=book_data['date_added'],
                last_modified=book_data['last_modified'],
                cover_available=book_data['cover_path'] is not None,
                path=book_data['path']
            )
            books.append(book)
        
        # Calculate total pages
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
        
        return BookCollection(
            books=books,
            total=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
        
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Calibre database not found in {library_path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error accessing library: {str(e)}")


@router.get("/libraries/{library_id}/books/{book_id}", response_model=Book)
async def get_book_details(library_id: str, book_id: int):
    """Get detailed information about a specific book."""
    library_paths = get_library_paths()
    
    # Parse library ID  
    try:
        if library_id == "library1":
            library_index = 0
        elif library_id.startswith("library"):
            library_index = int(library_id[7:]) - 1
        else:
            raise ValueError("Invalid library ID format")
        
        if library_index < 0 or library_index >= len(library_paths):
            raise ValueError("Library index out of range")
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Library {library_id} not found")
    
    library_path = library_paths[library_index]
    
    try:
        db_service = get_calibre_db_service(library_path)
        book_data = db_service.get_book_by_id(book_id)
        
        if not book_data:
            raise HTTPException(status_code=404, detail=f"Book {book_id} not found")
        
        return Book(
            id=book_data['id'],
            title=book_data['title'],
            authors=book_data['authors'],
            series_name=book_data['series_name'],
            series_index=book_data['series_index'],
            publisher=book_data['publisher'],
            comments=book_data['comments'],
            rating=book_data['rating'],
            tags=book_data['tags'],
            formats=book_data['formats'],
            isbn=book_data['isbn'],
            uuid=book_data['uuid'],
            date_added=book_data['date_added'],
            last_modified=book_data['last_modified'],
            cover_available=book_data['cover_path'] is not None,
            path=book_data['path']
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving book: {str(e)}")


@router.get("/libraries/{library_id}/books/{book_id}/cover")
async def get_book_cover(library_id: str, book_id: int):
    """Get the cover image for a book."""
    library_paths = get_library_paths()
    
    # Parse library ID
    try:
        if library_id == "library1":
            library_index = 0
        elif library_id.startswith("library"):
            library_index = int(library_id[7:]) - 1
        else:
            raise ValueError("Invalid library ID format")
        
        if library_index < 0 or library_index >= len(library_paths):
            raise ValueError("Library index out of range")
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Library {library_id} not found")
    
    library_path = library_paths[library_index]
    
    try:
        db_service = get_calibre_db_service(library_path)
        cover_path = db_service.get_cover_path(book_id)
        
        if not cover_path or not os.path.exists(cover_path):
            raise HTTPException(status_code=404, detail=f"Cover for book {book_id} not found")
        
        return FileResponse(cover_path, media_type='image/jpeg')
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving cover: {str(e)}")


@router.get("/libraries/{library_id}/stats")
async def get_library_stats(library_id: str):
    """Get statistics about the library."""
    library_paths = get_library_paths()
    
    # Parse library ID
    try:
        if library_id == "library1":
            library_index = 0
        elif library_id.startswith("library"):
            library_index = int(library_id[7:]) - 1
        else:
            raise ValueError("Invalid library ID format")
        
        if library_index < 0 or library_index >= len(library_paths):
            raise ValueError("Library index out of range")
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Library {library_id} not found")
    
    library_path = library_paths[library_index]
    
    try:
        db_service = get_calibre_db_service(library_path)
        return db_service.get_library_stats()
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting stats: {str(e)}")