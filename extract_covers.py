#!/usr/bin/env python3
"""
Pre-extract all covers from ebooks to improve performance.
Run this script to extract covers for all books upfront.
"""

import os
import sys
import time
from pathlib import Path

# Add the app directory to Python path
sys.path.append(os.path.dirname(__file__))

from app.services.calibre_service import get_calibre_service

def extract_all_covers():
    """Extract covers for all books in the library."""
    print("🎨 Starting cover extraction for all books...")
    
    calibre_service = get_calibre_service()
    books = calibre_service.get_books()
    
    total_books = len(books)
    extracted = 0
    skipped = 0
    errors = 0
    
    print(f"📚 Found {total_books} books to process")
    
    for i, book in enumerate(books, 1):
        book_id = book['id']
        title = book.get('title', 'Unknown')
        
        try:
            # Check if cover already exists
            covers_dir = os.path.join(calibre_service.library_path, '.covers')
            cover_path = os.path.join(covers_dir, f"cover_{book_id}.jpg")
            
            if os.path.exists(cover_path):
                print(f"⏭️  [{i:3d}/{total_books}] Skipping {title} (cover exists)")
                skipped += 1
                continue
            
            # Extract cover
            print(f"🎨 [{i:3d}/{total_books}] Extracting cover for: {title}")
            result_path = calibre_service.get_cover_path(book_id)
            
            if result_path:
                extracted += 1
                print(f"✅ [{i:3d}/{total_books}] Extracted: {title}")
            else:
                errors += 1
                print(f"❌ [{i:3d}/{total_books}] Failed: {title}")
                
        except Exception as e:
            errors += 1
            print(f"💥 [{i:3d}/{total_books}] Error for {title}: {e}")
    
    print(f"\n🎉 Cover extraction complete!")
    print(f"📊 Results:")
    print(f"   ✅ Extracted: {extracted}")
    print(f"   ⏭️  Skipped: {skipped}")
    print(f"   ❌ Errors: {errors}")
    print(f"   📚 Total: {total_books}")
    
    if extracted > 0:
        print(f"\n🚀 Covers are now cached! The UI should load much faster.")

if __name__ == "__main__":
    extract_all_covers()