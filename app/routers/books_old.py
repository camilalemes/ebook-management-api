# app/routers/books.py
import os
import shutil
import tempfile
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, computed_field

from ..services.calibre_service import get_calibre_service, CalibreService

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
        if self.size is not None:
            kb_size = self.size / 1024
            return f"{kb_size:.0f} KB"
        return None

    @computed_field
    def formatted_date(self) -> Optional[str]:
        """Return date formatted as dd/MM/yyyy HH:mm"""
        if self.last_modified is not None:
            dt = datetime.fromtimestamp(self.last_modified)
            return dt.strftime("%d/%m/%Y %H:%M") + "h"
        return None


class BookCollection(BaseModel):
    books: List[Book]
    total: int


@router.get("/libraries/{location_id}/books", response_model=BookCollection)
async def list_books(
        location_id: str,
        calibre_service: CalibreService = Depends(get_calibre_service),
        sync_service: SyncService = Depends(get_sync_service)
):
    if location_id == "calibre":
        # Calibre code remains unchanged as it already works correctly
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

    elif location_id.startswith("replica"):
        try:
            replica_index = int(location_id[7:]) - 1
            if replica_index < 0 or replica_index >= len(sync_service.replica_paths):
                raise ValueError("Invalid replica index")
        except ValueError:
            raise HTTPException(status_code=404, detail=f"Location {location_id} not found")

        replica_path = sync_service.replica_paths[replica_index]
        replica_files = sync_service.get_replica_files(replica_path)

        # Group books by title
        book_groups = {}

        for filename, file_data in replica_files.items():
            base_filename = os.path.splitext(filename)[0]
            ext = file_data.get("ext", "unknown").lower()
            path = file_data.get("path", "")

            # Smart parsing: don't split on " - " if it's likely part of the title
            title = base_filename
            author = "Unknown"

            # Only split on " - " if it's likely a title-author separator
            if " - " in base_filename:
                parts = base_filename.split(" - ")
                
                # Heuristics to determine if the last part is an author:
                # 1. If there are only 2 parts and the last part looks like an author name
                # 2. Avoid splitting known title patterns
                
                if len(parts) == 2:
                    potential_title, potential_author = parts[0].strip(), parts[1].strip()
                    
                    # Check if the potential author looks like a real author name
                    author_indicators = [
                        # Has typical author name patterns
                        len(potential_author.split()) <= 4,  # Authors usually have 1-4 names
                        not any(word in potential_author.lower() for word in [
                            'parte', 'volume', 'vol', 'livro', 'book', 'series', 'série',
                            'edition', 'edição', 'clássicos', 'biblioteca', 'coleção'
                        ]),
                        # Not obviously part of a title
                        not potential_author.lower().startswith(('primeira', 'segunda', 'terceira', 'vol', 'book', 'part')),
                        # Contains typical name patterns
                        any(char.isupper() for char in potential_author)  # Has capital letters (names)
                    ]
                    
                    # Only split if at least 3 out of 4 heuristics suggest it's an author
                    if sum(author_indicators) >= 3:
                        title = potential_title
                        author = potential_author
                    # Otherwise keep the full filename as title
                    
                # For more than 2 parts, be more conservative - keep full title unless very confident
                elif len(parts) > 2:
                    last_part = parts[-1].strip()
                    # Only split if the last part is very clearly an author (short and has capital letters)
                    if (len(last_part.split()) <= 3 and 
                        any(char.isupper() for char in last_part) and
                        not any(word in last_part.lower() for word in ['vol', 'part', 'book', 'série', 'edition'])):
                        title = " - ".join(parts[:-1]).strip()
                        author = last_part

            # Create a unique key for the book based on title
            # This ensures different formats of the same book are grouped together
            book_key = title.lower()

            # Add to existing book entry or create a new one
            if book_key in book_groups:
                if ext not in book_groups[book_key]["formats"]:
                    book_groups[book_key]["formats"].append(ext)
                book_groups[book_key]["paths"].append(path)
                book_groups[book_key]["sizes"].append(file_data.get("size", 0))
                book_groups[book_key]["mtimes"].append(file_data.get("mtime", 0))
            else:
                book_groups[book_key] = {
                    "title": title,
                    "authors": [author] if author != "Unknown" else ["Unknown"],
                    "formats": [ext],
                    "paths": [path],
                    "sizes": [file_data.get("size", 0)],
                    "mtimes": [file_data.get("mtime", 0)]
                }

        # Get Calibre books to match IDs
        calibre_books = calibre_service.get_books()
        
        # Convert grouped data to Book objects
        books = []
        for book_key, book_data in book_groups.items():
            size = max(book_data["sizes"]) if book_data["sizes"] else 0
            mtime = max(book_data["mtimes"]) if book_data["mtimes"] else 0
            path = book_data["paths"][0] if book_data["paths"] else None

            # Find all matching books in Calibre library (to handle multiple versions)
            replica_title = book_data["title"].strip().lower()
            replica_authors = [author.strip().lower() for author in book_data["authors"]]
            
            import logging
            logger = logging.getLogger("book_matching")
            logger.info(f"Looking for matches for replica book: '{replica_title}' by {replica_authors}")
            
            # Normalize titles for better matching (handle punctuation differences)
            def normalize_for_matching(title):
                import re
                # Remove/normalize punctuation that might vary
                normalized = re.sub(r'[:\-|–—]', ' ', title)  # Replace colons, dashes with spaces
                normalized = re.sub(r'[^\w\s]', ' ', normalized)  # Remove other punctuation
                normalized = re.sub(r'\s+', ' ', normalized)  # Normalize whitespace
                return normalized.strip()
            
            # Find all potential matches (not just the best one)
            matched_calibre_books = []
            
            for calibre_book in calibre_books:
                calibre_title = calibre_book.get("title", "").strip().lower()
                calibre_authors_raw = calibre_book.get("authors", [])
                
                # Normalize calibre authors to list of lowercase strings
                if isinstance(calibre_authors_raw, str):
                    calibre_authors = [calibre_authors_raw.strip().lower()]
                else:
                    calibre_authors = [str(author).strip().lower() for author in calibre_authors_raw]
                
                calibre_normalized = normalize_for_matching(calibre_title)
                replica_normalized = normalize_for_matching(replica_title)
                
                # Calculate match score
                title_match = (calibre_title == replica_title or 
                              calibre_normalized == replica_normalized)
                author_match = False
                
                if replica_authors and replica_authors[0] != "unknown" and calibre_authors:
                    # Check if any replica author matches any calibre author (partial matches allowed)
                    author_match = any(
                        any(replica_author in calibre_author or calibre_author in replica_author or 
                            # Also check for similarity in names (handle accents, etc.)
                            abs(len(replica_author) - len(calibre_author)) <= 3 and 
                            sum(c1 == c2 for c1, c2 in zip(replica_author, calibre_author)) >= min(len(replica_author), len(calibre_author)) * 0.8
                            for calibre_author in calibre_authors)
                        for replica_author in replica_authors
                    )
                
                # Score the match
                score = 0
                if title_match:
                    score += 10
                if author_match:
                    score += 5
                
                # Also try partial title matching for cases where formats might differ
                if not title_match:
                    # Use normalized titles for word comparison
                    replica_words = set(replica_normalized.split())
                    calibre_words = set(calibre_normalized.split())
                    common_words = replica_words & calibre_words
                    if len(common_words) >= 2 and len(common_words) / max(len(replica_words), len(calibre_words)) > 0.6:
                        score += 3
                
                # If this is a good match, add it to our list
                # Require strong match (exact title + author OR very high score)
                if score >= 15 or (score >= 10 and title_match):  # More stringent matching
                    matched_calibre_books.append({
                        "id": calibre_book["id"],
                        "title": calibre_title,
                        "score": score
                    })
                    logger.debug(f"Found match (score {score}): Calibre book ID {calibre_book['id']} - '{calibre_title}'")
            
            # Create replica book entries for each matched Calibre book
            if matched_calibre_books:
                logger.info(f"Found {len(matched_calibre_books)} matching versions in Calibre library")
                for match in matched_calibre_books:
                    books.append(Book(
                        id=match["id"],
                        title=book_data["title"],
                        authors=book_data["authors"],
                        formats=book_data["formats"],
                        size=size,
                        last_modified=mtime,
                        path=path
                    ))
            else:
                logger.warning(f"No good match found for '{replica_title}', using fallback ID")
                # Use fallback pseudo ID if no matches found
                fallback_id = abs(hash(book_key)) % 1000000000
                books.append(Book(
                    id=fallback_id,
                    title=book_data["title"],
                    authors=book_data["authors"],
                    formats=book_data["formats"],
                    size=size,
                    last_modified=mtime,
                    path=path
                ))

        return BookCollection(books=books, total=len(books))
    else:
        raise HTTPException(status_code=404, detail=f"Location {location_id} not found")


@router.get("/books/{book_id}/metadata")
async def get_book_metadata(
        book_id: int,
        calibre_service: CalibreService = Depends(get_calibre_service)
):
    """Get detailed metadata for a book"""
    metadata = calibre_service.get_book_metadata(book_id)
    if not metadata:
        raise HTTPException(status_code=404, detail=f"Book with ID {book_id} not found")

    return {"metadata": metadata}


@router.put("/books/{book_id}/metadata")
async def update_book_metadata(
        book_id: int,
        background_tasks: BackgroundTasks,
        # Add metadata parameters here
):
    """Update book metadata (not implemented)"""
    # This would require implementing metadata update logic in calibre_service
    raise HTTPException(status_code=501, detail="Metadata update not implemented yet")


@router.post("/books/add")
async def add_book(
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),
        tags: str = Form(None),
        calibre_service: CalibreService = Depends(get_calibre_service)
):
    """Add a new book to the Calibre library"""
    # Create a temporary file to save the upload
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        try:
            # Save the upload to the temporary file
            shutil.copyfileobj(file.file, temp_file)
            temp_file_path = temp_file.name

            # Process tags if provided
            tags_list = tags.split(',') if tags else None

            # Add the book to Calibre
            book_id = calibre_service.add_book(temp_file_path, tags_list)

            if not book_id:
                raise HTTPException(status_code=500, detail="Failed to add book to library")

            # Trigger sync in background
            background_tasks.add_task(perform_sync)

            return {"status": "success", "book_id": book_id}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error adding book: {str(e)}")
        finally:
            # Clean up the temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)


@router.delete("/books/{book_id}")
async def delete_book(
        book_id: int,
        background_tasks: BackgroundTasks,
        calibre_service: CalibreService = Depends(get_calibre_service)
):
    """Delete a book from the Calibre library"""
    success = calibre_service.remove_book(book_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"Book with ID {book_id} not found or could not be deleted")

    # Trigger sync in background to remove from replicas
    background_tasks.add_task(perform_sync)

    return {"status": "success", "message": f"Book {book_id} deleted"}



@router.get("/books/{book_id}/cover")
async def get_book_cover(
        book_id: int,
        calibre_service: CalibreService = Depends(get_calibre_service)
):
    """Get the cover image for a book"""
    cover_path = calibre_service.get_cover_path(book_id)

    if not cover_path or not os.path.exists(cover_path):
        raise HTTPException(status_code=404, detail=f"Cover for book {book_id} not found")

    return FileResponse(cover_path)