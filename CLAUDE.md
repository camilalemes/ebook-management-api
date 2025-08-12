# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a FastAPI-based ebook management system with a modern Angular frontend. The system consists of:
- **Backend API**: FastAPI application that manages Calibre libraries and synchronization
- **Frontend UI**: Angular 20 application with Material Design interface

The application provides REST endpoints for managing ebook collections and handles intelligent synchronization between Calibre libraries and replica locations.

## Development Commands

### Backend (FastAPI)

**Install dependencies:**
```bash
pip install -r requirements.txt
```

**Start the development server:**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Alternative start method:**
```bash
python app/main.py
```

### Frontend (Angular)

**Navigate to frontend directory:**
```bash
cd ebook-ui
```

**Install dependencies:**
```bash
npm install
```

**Start development server:**
```bash
npm start
```

**Build for production:**
```bash
npm run build:prod
```

The Angular app runs on `http://localhost:4200` and connects to the API at `http://localhost:8000`.

## Architecture

### Backend Components (FastAPI)

- **FastAPI Application**: `app/main.py` - Main application entry point with router registration
- **Configuration**: `app/config.py` - Pydantic settings with environment variable management
- **Routers**: `app/routers/` - API endpoints organized by functionality:
  - `books.py` - Book management (CRUD operations, metadata, covers)
  - `sync.py` - Synchronization triggers and status
  - `comparison.py` - Library comparison functionality
- **Services**: `app/services/` - Business logic layer:
  - `calibre_service.py` - Calibre database interaction via calibredb CLI
  - `sync_service.py` - File synchronization and organization logic

### Frontend Components (Angular 20)

- **Standalone Components**: Modern Angular architecture without NgModules
- **Main Components**:
  - `book-list/` - Book browsing with search and filtering
  - `book-detail-dialog/` - Modal for viewing detailed book information
  - `add-book/` - Form for uploading new books
  - `sync/` - Sync management and status monitoring
- **Services**: `services/api.service.ts` - HTTP client for API communication
- **Models**: TypeScript interfaces for type safety
- **Material Design**: Angular Material components for consistent UI

### Key Architecture Patterns

- Uses dependency injection pattern for service instantiation
- Environment configuration through Pydantic settings with `.env` file support
- CLI integration with Calibre through subprocess calls to `calibredb`
- File-based synchronization with intelligent change detection using hashing
- Background task support for long-running operations

### Configuration Requirements

The application requires a `.env` file with:
- `CALIBRE_LIBRARY_PATH` - Path to the Calibre library
- `REPLICA_PATHS` - Comma-separated list of sync destination paths
- `CALIBRE_CMD_PATH` - Optional path to calibredb executable (defaults to "calibredb")

### Synchronization Logic

The sync system:
1. Scans Calibre library using calibredb commands
2. Organizes files by format in subdirectories (epub/, pdf/, etc.)
3. Renames files using "Title - Author.ext" format from Calibre metadata
4. Uses file hashing to detect changes and avoid unnecessary copies
5. Removes files from replicas when deleted from Calibre library

## Testing

No test framework is currently configured. Tests would typically be added using pytest.