# app/routers/comparison_router.py

import os
import subprocess
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Body, Depends
from pydantic import BaseModel, Field

# Assuming your CalibreService and get_calibre_service are here:
# Adjust the import path based on your project structure
from ..services.calibre_service import CalibreService, get_calibre_service

# If settings are needed directly, e.g. for logging config or base paths
# from ..config import settings

logger = logging.getLogger("comparison_router")
# Ensure logging is configured in your main app or here if standalone
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


# --- Pydantic Models for Request and Response ---

class BookDetail(BaseModel):
    """Detailed information about a book for the API response."""
    id: Optional[int] = Field(None, description="Book ID within its specific library.")
    title: Optional[str] = Field(None, description="Title of the book.")
    authors: List[str] = Field(default_factory=list, description="List of authors of the book.")
    formats: List[str] = Field(default_factory=list, description="List of available formats/file paths for the book.")

    class Config:
        # Deprecated in Pydantic V2, use model_config instead if on V2
        # orm_mode = True # If you were to map directly from ORM objects
        # For Pydantic V2:
        from_attributes = True


class CompareLibrariesRequest(BaseModel):
    """Request model for comparing libraries."""
    other_library_path: str = Field(..., description="Absolute path to the other Calibre library to compare against.")


class ComparisonResultResponse(BaseModel):
    """Response model for the library comparison result."""
    message: str = Field("Library comparison successful.", description="Status message of the comparison.")
    current_library_path: str = Field(..., description="Path of the primary Calibre library.")
    other_library_path: str = Field(..., description="Path of the Calibre library used for comparison.")
    unique_to_current_library: List[BookDetail] = Field(default_factory=list,
                                                        description="Books found only in the current library.")
    unique_to_other_library: List[BookDetail] = Field(default_factory=list,
                                                      description="Books found only in the other library.")


# --- FastAPI Router Definition ---

router = APIRouter(
    prefix="/libraries",  # All routes in this router will start with /libraries
    tags=["Library Comparison"],  # Tag for API documentation
)

# Dependency to get CalibreService instance
# This handles service initialization and initial error checks (e.g., config, calibredb path)
async def get_calibre_service_dependency() -> CalibreService:
    try:
        service = get_calibre_service()
        return service
    except ValueError as e:  # Specific error from get_calibre_service for config issues
        logger.error(f"Configuration error preventing CalibreService initialization: {e}")
        raise HTTPException(status_code=503, detail=f"Calibre Service not configured: {str(e)}")
    except FileNotFoundError as e:  # If calibredb is not found during service init
        logger.error(f"Calibredb command not found during service initialization: {e}")
        raise HTTPException(status_code=503,
                            detail="Calibredb command not found. Ensure Calibre is installed and CALIBRE_CMD_PATH is correctly set.")
    except Exception as e:  # Catch any other unexpected errors during service init
        logger.exception("Unexpected error during CalibreService initialization.")
        raise HTTPException(status_code=500, detail=f"Unexpected error initializing Calibre service: {str(e)}")


@router.post(
    "/compare",
    response_model=ComparisonResultResponse,
    summary="Compare two Calibre libraries",
    description="Compares the books in the main Calibre library (configured in the service) "
                "with another Calibre library specified by its path."
)
async def compare_libraries_endpoint(
        request_data: CompareLibrariesRequest = Body(...),
        calibre_service: CalibreService = Depends(get_calibre_service_dependency)
):
    """
    Compares the Calibre library configured in this service with another library.

    - **other_library_path**: The absolute file system path to the secondary Calibre library.
      This path must be accessible by the server running this API.
    """
    other_path = request_data.other_library_path

    # Basic validation for the other library path
    if not other_path or not os.path.isabs(other_path):
        raise HTTPException(
            status_code=400,
            detail="The 'other_library_path' must be a non-empty absolute path."
        )
    # The CalibreService.compare_with_library itself also checks if it's a directory.
    # If you want an earlier check:
    # if not os.path.isdir(other_path):
    #     raise HTTPException(
    #         status_code=404, # Or 400 for bad input
    #         detail=f"The specified other_library_path does not exist or is not a directory: {other_path}"
    #     )

    try:
        logger.info(f"Initiating comparison between '{calibre_service.library_path}' and '{other_path}'.")

        # Call the comparison function from the service
        # The compare_with_library method itself handles Calibre-specific errors for the 'other' library
        comparison_data = calibre_service.compare_with_library(other_library_path=other_path)

        # Convert the raw dictionary lists from the service to Pydantic models
        # This ensures the response conforms to the BookDetail schema
        unique_current_books = [BookDetail.model_validate(book) for book in
                                comparison_data.get("unique_to_current_library", [])]
        unique_other_books = [BookDetail.model_validate(book) for book in
                              comparison_data.get("unique_to_other_library", [])]

        return ComparisonResultResponse(
            current_library_path=calibre_service.library_path,
            other_library_path=other_path,
            unique_to_current_library=unique_current_books,
            unique_to_other_library=unique_other_books
        )
    except FileNotFoundError as e:  # Should ideally be caught by dependency or service init
        logger.error(f"Calibredb command not found during comparison operation: {e}")
        raise HTTPException(status_code=503,
                            detail="Calibredb command not found. Ensure Calibre is installed and configured.")
    except subprocess.CalledProcessError as e:
        error_detail = f"A Calibredb command failed: {e.cmd}. Error: {e.stderr.strip() if e.stderr else 'No stderr output.'}"
        logger.error(error_detail)
        raise HTTPException(status_code=500, detail=error_detail)
    except ValueError as e:  # Catch ValueErrors that might be raised by the service (e.g., invalid path from within service)
        logger.warning(f"Validation error during comparison: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(
            f"An unexpected error occurred during library comparison between '{calibre_service.library_path}' and '{other_path}'.")
        raise HTTPException(status_code=500, detail=f"An unexpected internal error occurred: {str(e)}")

@router.get(
    "/compare-all",
    summary="Compare Calibre library with all replica locations",
    description="Compares the main Calibre library with all configured replica locations."
)
async def compare_all_libraries(
        calibre_service: CalibreService = Depends(get_calibre_service_dependency)
):
    """
    Compares the main Calibre library with all configured replica locations.
    Returns a summary of unique books in each location.
    """
    try:
        from ..services.sync_service import get_sync_service
        sync_service = get_sync_service()
        
        # Get all replica paths
        replica_paths = sync_service.replica_paths
        if not replica_paths:
            return {
                "message": "No replica locations configured for comparison",
                "current_library_path": calibre_service.library_path,
                "replicas": []
            }
        
        results = {
            "current_library_path": calibre_service.library_path,
            "replicas": []
        }
        
        logger.info(f"Comparing main library with {len(replica_paths)} replica locations")
        
        # Get Calibre books once to avoid repeated calls
        calibre_books = calibre_service.get_books()
        logger.info(f"Loaded {len(calibre_books)} books from main Calibre library")
        
        for i, replica_path in enumerate(replica_paths):
            replica_name = f"Replica {i+1}"
            try:
                logger.info(f"Comparing with {replica_name}: {replica_path}")
                
                # Get replica books using the books router logic
                # Import and use the books router function directly
                from . import books as books_router
                replica_location = f"replica{i+1}"
                
                # Call the list_books function for this replica
                try:
                    replica_books_collection = await books_router.list_books(replica_location, calibre_service, sync_service)
                    replica_books = replica_books_collection.books
                except Exception as e:
                    logger.warning(f"Could not get replica books for {replica_name}: {e}")
                    replica_books = []
                
                # Filter out system files from replica books
                filtered_replica_books = [book for book in replica_books 
                                         if not (book.title.lower() in ['metadata', 'metadata.db'] or 
                                                any(fmt.lower() == 'db' for fmt in book.formats))]
                
                # Since parsing is now fixed, use simple ID-based comparison
                calibre_ids = {book["id"] for book in calibre_books}
                replica_ids = {book.id for book in filtered_replica_books}
                
                # Find differences using direct ID comparison
                unique_to_calibre = calibre_ids - replica_ids
                unique_to_replica = replica_ids - calibre_ids
                common_ids = calibre_ids & replica_ids
                
                # Get detailed book information for unique books
                unique_to_calibre_books = []
                for book in calibre_books:
                    if book["id"] in unique_to_calibre:
                        # Extract formats as extensions from full paths
                        format_extensions = []
                        for fmt_path in book.get("formats", []):
                            try:
                                ext = os.path.splitext(fmt_path)[1].lstrip('.').upper()
                                if ext and ext not in format_extensions:
                                    format_extensions.append(ext)
                            except:
                                continue
                        
                        unique_to_calibre_books.append({
                            "id": book["id"],
                            "title": book["title"],
                            "authors": book.get("authors", []),
                            "formats": format_extensions,
                            "location": "Calibre Library Only"
                        })
                        if len(unique_to_calibre_books) >= 20:  # Show more books for detailed view
                            break
                
                unique_to_replica_books = []
                for book in filtered_replica_books:
                    if book.id in unique_to_replica:
                        # Format file extensions consistently (uppercase)
                        formatted_formats = [fmt.upper() for fmt in book.formats] if book.formats else []
                        
                        unique_to_replica_books.append({
                            "id": book.id,
                            "title": book.title,
                            "authors": book.authors,
                            "formats": formatted_formats,
                            "size": getattr(book, 'formatted_size', None),
                            "last_modified": getattr(book, 'formatted_date', None),
                            "location": f"{replica_name} Only"
                        })
                        if len(unique_to_replica_books) >= 20:
                            break
                
                # Use the already filtered replica books count
                filtered_replica_count = len(filtered_replica_books)
                
                results["replicas"].append({
                    "name": replica_name,
                    "path": replica_path,
                    "unique_to_main_library": len(unique_to_calibre),
                    "unique_to_replica": len(unique_to_replica),
                    "unique_to_main_library_books": unique_to_calibre_books,
                    "unique_to_replica_books": unique_to_replica_books,
                    "status": "success",
                    "total_calibre_books": len(calibre_books),
                    "total_replica_books": filtered_replica_count,
                    "common_books": len(common_ids)
                })
                
                logger.info(f"Completed comparison with {replica_name}: {len(calibre_books)} Calibre books, {len(replica_books)} replica books, {len(common_ids)} common")
                
            except Exception as e:
                logger.error(f"Error comparing with {replica_name} ({replica_path}): {e}")
                results["replicas"].append({
                    "name": replica_name,
                    "path": replica_path,
                    "status": "error",
                    "error": str(e)
                })
        
        return results
        
    except Exception as e:
        logger.exception("Error during library comparison")
        raise HTTPException(status_code=500, detail=f"Error comparing libraries: {str(e)}")


# You would then include this router in your main FastAPI application:
# In your main.py or app.py:
# from app.routers import comparison_router
# app.include_router(comparison_router.router)