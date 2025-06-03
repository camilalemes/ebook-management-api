# Calibre Sync API

A FastAPI application that synchronizes Calibre libraries to external devices and provides a REST API for managing your ebook collection.

## Features

- **Synchronize books**: Copy your Calibre library to multiple external devices with intelligent organization
- **View books**: Browse books from your Calibre library or any synchronized device
- **Book management**: Add and delete books directly through the API
- **Smart renaming**: Files are automatically renamed using the "Title - Author.ext" format based on Calibre metadata
- **Format organization**: Different ebook formats are stored in appropriate subdirectories
- **Intelligent syncing**: Only new/changed files are copied, and files removed from Calibre are also removed from replicas
- **Dry run mode**: Test synchronization without making any changes

## Installation

1. Clone the repository:
```bash
git clone https://github.com/camilalemes/ebook-management-api.git
cd ebook-management-api
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure the application by creating a `.env` file:
```
CALIBRE_LIBRARY_PATH=/path/to/calibre/library
REPLICA_PATHS=/path/to/replica1,/path/to/replica2
CALIBRE_CMD_PATH=/usr/bin/calibredb  # Optional, defaults to "calibredb"
```

## Usage

Start the server:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Access the API documentation at: http://localhost:8000/docs

### API Endpoints

- **GET /libraries/{location_id}/books** - List books in Calibre or replica locations (e.g. replica1, replica2)
- **POST /sync/trigger** - Trigger synchronization between Calibre and replica locations
- **GET /sync/status** - Check synchronization status
- **POST /books/add** - Add a new book to the Calibre library
- **DELETE /books/{book_id}** - Delete a book from the Calibre library
- **GET /books/{book_id}/metadata** - Get book metadata
- **GET /books/{book_id}/cover** - Get book cover image

## Synchronization Logic

The application:
1. Scans your Calibre library and destination folders
2. Organizes books by format in appropriate directories
3. Renames files using metadata from Calibre
4. Ignores database and configuration files (.db, .json)
5. Updates only when content has changed (using file hashing)

## Requirements

- Python 3.9+
- Calibre installed and accessible via command line
- FastAPI and its dependencies

## Development

The application is structured as follows:
- `app/main.py` - Main FastAPI application
- `app/routers/` - API route handlers
- `app/services/` - Core business logic
- `app/config.py` - Application configuration
