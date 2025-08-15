"""Enhanced books router with improved error handling, validation, and async patterns."""

import asyncio
import os
import tempfile
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse

from ..config import settings
from ..exceptions import (
    BookNotFoundException,
    InvalidFileException,
    CalibreServiceException,
    ValidationException
)
from ..models import (
    BookCollection,
    BookMetadataResponse,
    AddBookRequest,
    AddBookResponse,
    DeleteBookResponse,
    LibrariesResponse,
    Library
)
from ..services.calibre_service_enhanced import CalibreServiceEnhanced, get_calibre_service_enhanced
from ..utils.logging import get_logger

router = APIRouter(tags=["books"])
logger = get_logger(__name__)


async def validate_file_upload(file: UploadFile) -> None:
    """Validate uploaded file."""
    if not file.filename:
        raise InvalidFileException("No filename provided")
    
    # Check file extension
    file_ext = Path(file.filename).suffix.lower()
    allowed_extensions = settings.allowed_extensions_list
    
    if file_ext not in allowed_extensions:
        raise InvalidFileException(
            f"File type {file_ext} not allowed. Allowed types: {', '.join(allowed_extensions)}",
            filename=file.filename
        )
    
    # Check file size
    if hasattr(file, 'size') and file.size and file.size > settings.MAX_UPLOAD_SIZE:
        size_mb = file.size / (1024 * 1024)
        max_mb = settings.MAX_UPLOAD_SIZE / (1024 * 1024)
        raise InvalidFileException(
            f"File size {size_mb:.1f}MB exceeds maximum allowed size {max_mb:.1f}MB",
            filename=file.filename
        )


async def get_books_async(location_id: str = "calibre") -> List[dict]:
    """Get books asynchronously."""
    loop = asyncio.get_event_loop()
    
    # Get library paths from settings
    library_paths = settings.library_paths_list
    
    # Determine which library path to use based on location_id
    library_path = None
    if location_id == "calibre" and library_paths:
        library_path = library_paths[0]  # Main library
    elif location_id.startswith("library-") and library_paths:
        try:
            index = int(location_id.split("-")[1]) - 1
            if 0 <= index < len(library_paths):
                library_path = library_paths[index]
        except (ValueError, IndexError):
            pass
    
    if not library_path:
        raise ValidationException(f"Location '{location_id}' not supported", field="location_id")
    
    try:
        # Create a service instance for this specific library path
        calibre_service = CalibreServiceEnhanced(library_path=library_path)
        # Run the synchronous operation in a thread pool
        books_data = await loop.run_in_executor(None, calibre_service.get_books)
        return books_data
    except Exception as e:
        logger.error(f"Error retrieving books from {library_path}: {e}")
        raise CalibreServiceException(f"Failed to retrieve books: {str(e)}")


@router.get("/libraries", response_model=LibrariesResponse)
async def get_available_libraries():
    """Get list of available library locations."""
    try:
        libraries = []
        
        # Get library paths from settings
        library_paths = settings.library_paths_list
        
        for i, path in enumerate(library_paths):
            # Create library ID based on position or path
            if i == 0:
                lib_id = "calibre"
                lib_name = "Main Library"
                lib_desc = "Primary ebook collection"
            else:
                lib_id = f"library-{i+1}"
                lib_name = f"Library {i+1}"
                lib_desc = f"Additional ebook collection at {path}"
            
            libraries.append(Library(
                id=lib_id,
                name=lib_name,
                path=path,
                description=lib_desc
            ))
        
        return LibrariesResponse(libraries=libraries)
    
    except Exception as e:
        logger.error(f"Error getting available libraries: {e}")
        raise CalibreServiceException(f"Failed to get libraries: {str(e)}")


@router.get("/libraries/{location_id}/books", response_model=BookCollection)
async def list_books(
    location_id: str,
    page: int = 1,
    page_size: int = 50,
    search: Optional[str] = None,
    tag: Optional[str] = None
):
    """Get all books from the specified library with pagination, search, and tag filtering."""
    logger.info(f"Retrieving books from location: {location_id}, page: {page}, page_size: {page_size}, search: {search}, tag: {tag}")
    
    books_data = await get_books_async(location_id)
    
    # Apply search filter if provided
    if search and search.strip():
        search_term = search.strip().lower()
        filtered_books = []
        for book in books_data:
            # Search in title and authors
            title_match = search_term in book.get("title", "").lower()
            authors_match = False
            if isinstance(book.get("authors"), list):
                authors_match = any(search_term in author.lower() for author in book.get("authors", []))
            elif isinstance(book.get("authors"), str):
                authors_match = search_term in book.get("authors", "").lower()
            
            if title_match or authors_match:
                filtered_books.append(book)
        books_data = filtered_books
    
    # Apply tag filter if provided
    if tag and tag.strip():
        tag_filter = tag.strip().lower()
        filtered_books = []
        for book in books_data:
            book_tags = book.get("tags", [])
            if isinstance(book_tags, list):
                # Check if any of the book's tags match the filter (case-insensitive)
                if any(tag_filter in book_tag.lower() for book_tag in book_tags):
                    filtered_books.append(book)
        books_data = filtered_books
    
    total_books = len(books_data)
    
    # Apply pagination
    start_index = (page - 1) * page_size
    end_index = start_index + page_size
    paginated_books = books_data[start_index:end_index]
    
    # Process books data (simplified version)
    books = []
    for book in paginated_books:
        # Handle authors correctly
        if isinstance(book.get("authors"), str):
            authors = [book.get("authors")]
        elif isinstance(book.get("authors"), list):
            authors = book.get("authors")
        else:
            authors = ["Unknown"]

        # Get data directly from enhanced service - much cleaner!
        formats = book.get("formats", [])
        path = book.get("path")
        size = book.get("size")
        last_modified = book.get("last_modified")
        tags = book.get("tags", [])

        books.append({
            "id": book["id"],
            "title": book["title"],
            "authors": authors,
            "formats": formats,
            "size": size,
            "last_modified": last_modified,
            "path": path,
            "tags": tags
        })

    total_pages = max(1, (total_books + page_size - 1) // page_size) if total_books > 0 else 1
    logger.info(f"Retrieved {len(books)} books from {location_id} (page {page}/{total_pages}, total: {total_books})")
    return BookCollection(
        books=books, 
        total=total_books,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/books/{book_id}/metadata", response_model=BookMetadataResponse)
async def get_book_metadata(
    book_id: int,
    calibre_service: CalibreServiceEnhanced = Depends(get_calibre_service_enhanced)
):
    """Get detailed metadata for a book."""
    if book_id <= 0:
        raise ValidationException("Book ID must be positive", field="book_id")
    
    logger.info(f"Retrieving metadata for book ID: {book_id}")
    
    loop = asyncio.get_event_loop()
    try:
        metadata = await loop.run_in_executor(None, calibre_service.get_book_metadata_detailed, book_id)
        if not metadata:
            raise BookNotFoundException(book_id)
        
        return BookMetadataResponse(
            message="Metadata retrieved successfully",
            metadata=metadata
        )
    except Exception as e:
        logger.error(f"Error retrieving metadata for book {book_id}: {e}")
        if isinstance(e, BookNotFoundException):
            raise
        raise CalibreServiceException(f"Failed to retrieve metadata: {str(e)}")


@router.post("/books/add", response_model=AddBookResponse)
async def add_book(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    authors: Optional[str] = Form(None),
    publisher: Optional[str] = Form(None),
    published: Optional[str] = Form(None),
    isbn: Optional[str] = Form(None),
    language: Optional[str] = Form(None),
    series: Optional[str] = Form(None),
    series_index: Optional[float] = Form(None),
    comments: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    calibre_service: CalibreServiceEnhanced = Depends(get_calibre_service_enhanced)
):
    """Add a new book to the Calibre library."""
    logger.info(f"Adding new book: {file.filename}")
    
    # Validate the uploaded file
    await validate_file_upload(file)
    
    # Create temporary file
    temp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as temp_file:
            # Copy file content
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        # Process tags
        tags_list = [tag.strip() for tag in tags.split(',')] if tags else None
        
        # Add book to Calibre (run in thread pool)
        loop = asyncio.get_event_loop()
        book_id = await loop.run_in_executor(
            None, 
            calibre_service.add_book, 
            temp_file_path, 
            tags_list
        )
        
        if not book_id:
            raise CalibreServiceException("Failed to add book to library")
        
        # Parse authors
        authors_list = [author.strip() for author in authors.split(',')] if authors else ["Unknown"]
        
        logger.info(f"Successfully added book with ID: {book_id}")
        
        # Note: In a real implementation, you might want to trigger sync here
        # background_tasks.add_task(perform_sync)
        
        return AddBookResponse(
            message="Book added successfully",
            book_id=book_id,
            title=title or file.filename,
            authors=authors_list
        )
        
    except Exception as e:
        logger.error(f"Error adding book {file.filename}: {e}")
        if isinstance(e, (InvalidFileException, CalibreServiceException)):
            raise
        raise CalibreServiceException(f"Failed to add book: {str(e)}")
    
    finally:
        # Clean up temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except OSError as e:
                logger.warning(f"Failed to clean up temporary file {temp_file_path}: {e}")


@router.delete("/books/{book_id}", response_model=DeleteBookResponse)
async def delete_book(
    book_id: int,
    background_tasks: BackgroundTasks,
    calibre_service: CalibreServiceEnhanced = Depends(get_calibre_service_enhanced)
):
    """Delete a book from the Calibre library."""
    if book_id <= 0:
        raise ValidationException("Book ID must be positive", field="book_id")
    
    logger.info(f"Deleting book ID: {book_id}")
    
    loop = asyncio.get_event_loop()
    try:
        success = await loop.run_in_executor(None, calibre_service.remove_book, book_id)
        
        if not success:
            raise BookNotFoundException(book_id)
        
        logger.info(f"Successfully deleted book ID: {book_id}")
        
        # Note: In a real implementation, you might want to trigger sync here
        # background_tasks.add_task(perform_sync)
        
        return DeleteBookResponse(
            message="Book deleted successfully",
            deleted_id=book_id
        )
        
    except Exception as e:
        logger.error(f"Error deleting book {book_id}: {e}")
        if isinstance(e, BookNotFoundException):
            raise
        raise CalibreServiceException(f"Failed to delete book: {str(e)}")


@router.get("/books/{book_id}/cover")
async def get_book_cover(
    book_id: int,
    calibre_service: CalibreServiceEnhanced = Depends(get_calibre_service_enhanced)
):
    """Get the cover image for a book - now directly from cover.jpg."""
    if book_id <= 0:
        raise ValidationException("Book ID must be positive", field="book_id")
    
    logger.info(f"Retrieving cover for book ID: {book_id}")
    
    loop = asyncio.get_event_loop()
    try:
        cover_path = await loop.run_in_executor(None, calibre_service.get_cover_path, book_id)
        
        if not cover_path or not os.path.exists(cover_path):
            raise BookNotFoundException(book_id)
        
        return FileResponse(
            path=cover_path,
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=3600"}  # Cache for 1 hour
        )
        
    except Exception as e:
        logger.error(f"Error retrieving cover for book {book_id}: {e}")
        if isinstance(e, BookNotFoundException):
            raise
        raise CalibreServiceException(f"Failed to retrieve cover: {str(e)}")


@router.get("/books/search")
async def search_books(
    q: str,
    calibre_service: CalibreServiceEnhanced = Depends(get_calibre_service_enhanced)
):
    """Search books in the library."""
    if not q.strip():
        raise ValidationException("Search query cannot be empty", field="q")
    
    logger.info(f"Searching books with query: {q}")
    
    loop = asyncio.get_event_loop()
    try:
        books_data = await loop.run_in_executor(None, calibre_service.search_books, q)
        
        books = []
        for book in books_data:
            books.append({
                "id": book["id"],
                "title": book["title"],
                "authors": book["authors"],
                "formats": book["formats"],
                "size": book.get("size"),
                "last_modified": book.get("last_modified"),
                "path": book.get("path")
            })
        
        return BookCollection(books=books, total=len(books))
    except Exception as e:
        logger.error(f"Error searching books: {e}")
        raise CalibreServiceException(f"Failed to search books: {str(e)}")




@router.get("/books/{book_id}/download")
async def download_book(
    book_id: int,
    format: Optional[str] = None,
    calibre_service: CalibreServiceEnhanced = Depends(get_calibre_service_enhanced)
):
    """Download a book file in the specified format."""
    if book_id <= 0:
        raise ValidationException("Book ID must be positive", field="book_id")
    
    logger.info(f"Downloading book ID: {book_id}, format: {format}")
    
    loop = asyncio.get_event_loop()
    try:
        # Get book data and file path
        book = await loop.run_in_executor(None, calibre_service.get_book_by_id, book_id)
        if not book:
            raise BookNotFoundException(book_id)
        
        file_path = await loop.run_in_executor(None, calibre_service.get_book_file_path, book_id, format)
        
        if not file_path or not os.path.exists(file_path):
            available_formats = book.get('formats', [])
            raise CalibreServiceException(
                f"Format '{format}' not available for book {book_id}. Available formats: {available_formats}"
            )
        
        # Use the actual filename for download
        filename = os.path.basename(file_path)
        
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type='application/octet-stream'
        )
        
    except Exception as e:
        logger.error(f"Error downloading book {book_id}: {e}")
        if isinstance(e, (BookNotFoundException, CalibreServiceException)):
            raise
        raise CalibreServiceException(f"Failed to download book: {str(e)}")