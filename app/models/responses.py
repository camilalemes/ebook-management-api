"""Response models for the Calibre Sync API."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, computed_field, ConfigDict


class BaseResponse(BaseModel):
    """Base response model with common fields."""
    
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True
    )
    
    success: bool = Field(default=True, description="Whether the operation was successful")
    message: Optional[str] = Field(default=None, description="Optional message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


class ErrorResponse(BaseModel):
    """Error response model."""
    
    model_config = ConfigDict(extra="forbid")
    
    success: bool = Field(default=False)
    error_code: str = Field(description="Machine-readable error code")
    detail: str = Field(description="Human-readable error message")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    extra_data: Optional[Dict[str, Any]] = Field(default=None)


class BookMetadata(BaseModel):
    """Book metadata model."""
    
    model_config = ConfigDict(extra="allow")
    
    id: int = Field(description="Book ID in Calibre library")
    title: str = Field(description="Book title")
    authors: List[str] = Field(default_factory=list, description="List of authors")
    publisher: Optional[str] = Field(default=None, description="Publisher")
    published: Optional[str] = Field(default=None, description="Publication date")
    isbn: Optional[str] = Field(default=None, description="ISBN")
    tags: List[str] = Field(default_factory=list, description="Book tags")
    rating: Optional[int] = Field(default=None, ge=0, le=10, description="Book rating (0-10)")
    comments: Optional[str] = Field(default=None, description="Book comments/description")
    series: Optional[str] = Field(default=None, description="Series name")
    series_index: Optional[float] = Field(default=None, ge=0, description="Series index")
    language: Optional[str] = Field(default=None, description="Book language")
    formats: List[str] = Field(default_factory=list, description="Available formats")


class Book(BaseModel):
    """Book model with computed fields."""
    
    model_config = ConfigDict(extra="forbid")
    
    id: int = Field(description="Book ID")
    title: str = Field(description="Book title")
    authors: List[str] = Field(default_factory=list, description="List of authors")
    formats: List[str] = Field(default_factory=list, description="Available formats")
    size: Optional[int] = Field(default=None, ge=0, description="File size in bytes")
    last_modified: Optional[float] = Field(default=None, description="Last modification timestamp")
    path: Optional[str] = Field(default=None, description="File path")

    @computed_field
    @property
    def formatted_size(self) -> Optional[str]:
        """Return size formatted in human-readable format."""
        if self.size is None:
            return None
        
        if self.size < 1024:
            return f"{self.size} B"
        elif self.size < 1024 * 1024:
            return f"{self.size / 1024:.1f} KB"
        elif self.size < 1024 * 1024 * 1024:
            return f"{self.size / (1024 * 1024):.1f} MB"
        else:
            return f"{self.size / (1024 * 1024 * 1024):.1f} GB"

    @computed_field
    @property
    def formatted_date(self) -> Optional[str]:
        """Return date formatted as human-readable string."""
        if self.last_modified is None:
            return None
        
        try:
            dt = datetime.fromtimestamp(self.last_modified)
            return dt.strftime("%d/%m/%Y %H:%M")
        except (ValueError, OSError):
            return None


class BookCollection(BaseResponse):
    """Response model for book collections."""
    
    books: List[Book] = Field(description="List of books")
    total: int = Field(ge=0, description="Total number of books")
    
    def model_post_init(self, __context: Any) -> None:
        """Ensure total matches the actual book count."""
        if self.total != len(self.books):
            self.total = len(self.books)


class BookMetadataResponse(BaseResponse):
    """Response model for book metadata."""
    
    metadata: BookMetadata = Field(description="Book metadata")


class AddBookRequest(BaseModel):
    """Request model for adding a book."""
    
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True
    )
    
    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    authors: Optional[str] = Field(default=None, description="Comma-separated authors")
    publisher: Optional[str] = Field(default=None, max_length=200)
    published: Optional[str] = Field(default=None, max_length=50)
    isbn: Optional[str] = Field(default=None, max_length=20)
    language: Optional[str] = Field(default=None, max_length=10)
    series: Optional[str] = Field(default=None, max_length=200)
    series_index: Optional[float] = Field(default=None, ge=0)
    comments: Optional[str] = Field(default=None, max_length=5000)
    tags: Optional[str] = Field(default=None, description="Comma-separated tags")


class AddBookResponse(BaseResponse):
    """Response model for adding a book."""
    
    book_id: int = Field(description="ID of the newly added book")
    title: str = Field(description="Title of the added book")
    authors: List[str] = Field(description="Authors of the added book")


class DeleteBookResponse(BaseResponse):
    """Response model for deleting a book."""
    
    deleted_id: int = Field(description="ID of the deleted book")


class SyncStats(BaseModel):
    """Statistics for sync operations."""
    
    model_config = ConfigDict(extra="forbid")
    
    added: int = Field(ge=0, description="Number of files added")
    updated: int = Field(ge=0, description="Number of files updated")
    deleted: int = Field(ge=0, description="Number of files deleted")
    unchanged: int = Field(ge=0, description="Number of files unchanged")
    ignored: int = Field(ge=0, description="Number of files ignored")
    errors: int = Field(ge=0, description="Number of errors encountered")
    
    # File details
    added_files: List[str] = Field(default_factory=list, description="List of added files")
    updated_files: List[str] = Field(default_factory=list, description="List of updated files")
    deleted_files: List[str] = Field(default_factory=list, description="List of deleted files")
    ignored_files: List[str] = Field(default_factory=list, description="List of ignored files")
    error_files: List[str] = Field(default_factory=list, description="List of files with errors")
    
    @computed_field
    @property
    def total_processed(self) -> int:
        """Total number of files processed."""
        return self.added + self.updated + self.deleted + self.unchanged + self.ignored


class SyncResult(BaseModel):
    """Result of sync operation for a replica."""
    
    model_config = ConfigDict(extra="allow")
    
    replica_path: str = Field(description="Path to the replica")
    stats: Optional[SyncStats] = Field(default=None, description="Sync statistics")
    error: Optional[str] = Field(default=None, description="Error message if sync failed")
    duration: Optional[float] = Field(default=None, ge=0, description="Sync duration in seconds")


class SyncStatusResponse(BaseResponse):
    """Response model for sync status."""
    
    status: str = Field(description="Current sync status")
    last_sync: Optional[datetime] = Field(default=None, description="Last sync timestamp")
    is_running: bool = Field(default=False, description="Whether sync is currently running")
    results: List[SyncResult] = Field(default_factory=list, description="Sync results for each replica")
    total_duration: Optional[float] = Field(default=None, ge=0, description="Total sync duration")


class ReplicaComparison(BaseModel):
    """Comparison result for a replica."""
    
    model_config = ConfigDict(extra="forbid")
    
    name: str = Field(description="Replica name")
    path: str = Field(description="Replica path")
    status: str = Field(description="Comparison status")
    unique_to_main_library: int = Field(ge=0, description="Books only in main library")
    unique_to_replica: int = Field(ge=0, description="Books only in replica")
    common_books: int = Field(ge=0, description="Books in both libraries")
    unique_to_main_library_books: Optional[List[Book]] = Field(default=None)
    unique_to_replica_books: Optional[List[Book]] = Field(default=None)
    error: Optional[str] = Field(default=None, description="Error message if comparison failed")
    total_calibre_books: Optional[int] = Field(default=None, ge=0)
    total_replica_books: Optional[int] = Field(default=None, ge=0)


class ComparisonResponse(BaseResponse):
    """Response model for library comparison."""
    
    current_library_path: str = Field(description="Path to the current Calibre library")
    replicas: List[ReplicaComparison] = Field(description="Comparison results for each replica")


class HealthCheckResponse(BaseResponse):
    """Health check response."""
    
    version: str = Field(description="API version")
    calibre_available: bool = Field(description="Whether Calibre is available")
    library_accessible: bool = Field(description="Whether library is accessible")
    replica_count: int = Field(ge=0, description="Number of configured replicas")