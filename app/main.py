# app/main.py
"""Main FastAPI application with enhanced error handling, logging, and middleware."""

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, Any

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import uvicorn

# Add the project root to sys.path to make imports work
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

# Import application components
from app.config import settings
from app.exceptions import CalibreAPIException
from app.middleware import setup_middleware
from app.models import ErrorResponse, HealthCheckResponse
from app.routers import books_enhanced
from app.utils.logging import setup_logging, get_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger = get_logger(__name__)
    logger.info("📚 Starting Ebook Management API")
    logger.info(f"📚 Library paths: {settings.LIBRARY_PATHS}")
    logger.info(f"📂 Library paths: {len(settings.library_paths_list)} configured")
    logger.info(f"🌐 API running on {settings.API_HOST}:{settings.API_PORT}")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down Ebook Management API")


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    # Setup logging first
    setup_logging(
        level=settings.LOG_LEVEL,
        log_file=settings.LOG_FILE,
        max_file_size=settings.LOG_ROTATION_SIZE,
        backup_count=settings.LOG_BACKUP_COUNT
    )
    
    logger = get_logger(__name__)
    
    # Create FastAPI app
    app = FastAPI(
        title="Ebook Management API",
        description="Read-only API for browsing and managing ebook collections",
        version=settings.API_VERSION,
        debug=settings.API_DEBUG,
        lifespan=lifespan,
        docs_url="/docs" if settings.API_DEBUG else None,
        redoc_url="/redoc" if settings.API_DEBUG else None,
    )
    
    # Setup middleware
    setup_middleware(app)
    
    # Setup exception handlers
    setup_exception_handlers(app)
    
    # Include routers - using enhanced version with Calibre directory structure
    app.include_router(books_enhanced.router, prefix="/api/v1")  # Enhanced version
    
    # Add libraries endpoint
    @app.get("/api/v1/libraries")
    async def get_available_libraries():
        """Get list of available libraries."""
        return {
            "libraries": [
                {
                    "id": "calibre",
                    "name": "Calibre Library",
                    "description": "Main Calibre library with preserved directory structure"
                }
            ]
        }
    
    # Add root endpoints
    setup_root_endpoints(app)
    
    logger.info("✅ FastAPI application configured successfully")
    return app


def setup_exception_handlers(app: FastAPI) -> None:
    """Setup custom exception handlers."""
    
    @app.exception_handler(CalibreAPIException)
    async def calibre_exception_handler(request: Request, exc: CalibreAPIException):
        """Handle custom Calibre API exceptions."""
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error_code=exc.error_code,
                detail=exc.detail,
                extra_data=exc.extra_data
            ).model_dump()
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle Pydantic validation errors."""
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error_code="VALIDATION_ERROR",
                detail="Request validation failed",
                extra_data={"errors": exc.errors()}
            ).model_dump()
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle unexpected exceptions."""
        logger = get_logger(__name__)
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error_code="INTERNAL_SERVER_ERROR",
                detail="An unexpected error occurred" if not settings.API_DEBUG else str(exc)
            ).model_dump()
        )


def setup_root_endpoints(app: FastAPI) -> None:
    """Setup root-level endpoints."""
    
    @app.get("/", response_model=Dict[str, Any])
    async def root():
        """Root endpoint with API information."""
        return {
            "message": "Welcome to Ebook Management API",
            "version": settings.API_VERSION,
            "docs_url": "/docs" if settings.API_DEBUG else None,
            "health_url": "/health"
        }
    
    @app.get("/health", response_model=HealthCheckResponse)
    async def health_check():
        """Health check endpoint."""
        from app.services.calibre_service_enhanced import get_calibre_service_enhanced
        
        try:
            calibre_service = get_calibre_service_enhanced()
            # Try to access Calibre to verify it's working
            calibre_service.get_books()  # This will raise an exception if Calibre is not available
            calibre_available = True
            library_accessible = True
        except Exception as e:
            logger = get_logger(__name__)
            logger.warning(f"Health check failed: {e}")
            calibre_available = False
            library_accessible = False
        
        return HealthCheckResponse(
            message="API is running",
            version=settings.API_VERSION,
            calibre_available=calibre_available,
            library_accessible=library_accessible,
            library_count=len(settings.library_paths_list)
        )


# Create the application instance
app = create_application()


def main() -> None:
    """Run the application."""
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True
    )


if __name__ == '__main__':
    main()