"""Custom exceptions for the Calibre Sync API."""

from typing import Any, Dict, Optional
from fastapi import HTTPException, status


class CalibreAPIException(HTTPException):
    """Base exception for all Calibre API errors."""
    
    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: str = None,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.error_code = error_code or "UNKNOWN_ERROR"
        self.extra_data = extra_data or {}


class CalibreServiceException(CalibreAPIException):
    """Exception for Calibre service related errors."""
    
    def __init__(self, detail: str, error_code: str = "CALIBRE_SERVICE_ERROR", **kwargs):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
            error_code=error_code,
            **kwargs
        )


class BookNotFoundException(CalibreAPIException):
    """Exception raised when a book is not found."""
    
    def __init__(self, book_id: int, **kwargs):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Book with ID {book_id} not found",
            error_code="BOOK_NOT_FOUND",
            extra_data={"book_id": book_id},
            **kwargs
        )


class LibraryNotFoundException(CalibreAPIException):
    """Exception raised when a library is not found."""
    
    def __init__(self, library_path: str, **kwargs):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Library not found at path: {library_path}",
            error_code="LIBRARY_NOT_FOUND",
            extra_data={"library_path": library_path},
            **kwargs
        )


class InvalidFileException(CalibreAPIException):
    """Exception raised when an uploaded file is invalid."""
    
    def __init__(self, detail: str, filename: str = None, **kwargs):
        extra_data = {"filename": filename} if filename else {}
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            error_code="INVALID_FILE",
            extra_data=extra_data,
            **kwargs
        )


class SyncException(CalibreAPIException):
    """Exception raised during sync operations."""
    
    def __init__(self, detail: str, error_code: str = "SYNC_ERROR", **kwargs):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
            error_code=error_code,
            **kwargs
        )


class ValidationException(CalibreAPIException):
    """Exception raised for validation errors."""
    
    def __init__(self, detail: str, field: str = None, **kwargs):
        extra_data = {"field": field} if field else {}
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
            error_code="VALIDATION_ERROR",
            extra_data=extra_data,
            **kwargs
        )


class CalibreCommandException(CalibreServiceException):
    """Exception raised when calibredb command fails."""
    
    def __init__(self, command: str, error_output: str, **kwargs):
        super().__init__(
            detail=f"Calibre command failed: {command}",
            error_code="CALIBRE_COMMAND_ERROR",
            extra_data={
                "command": command,
                "error_output": error_output
            },
            **kwargs
        )


class ConfigurationException(CalibreAPIException):
    """Exception raised for configuration errors."""
    
    def __init__(self, detail: str, config_key: str = None, **kwargs):
        extra_data = {"config_key": config_key} if config_key else {}
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
            error_code="CONFIGURATION_ERROR",
            extra_data=extra_data,
            **kwargs
        )