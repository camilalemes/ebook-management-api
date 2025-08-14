# Ebook Management API

This is a **read-only** FastAPI application for browsing and managing ebook collections. It provides access to ebook metadata and files from replica locations (typically a NAS) without performing any write operations.

## Features

- **Read-Only Access**: Browse ebook collections without modifying files
- **Replica Support**: Read from synchronized replica directories
- **Metadata Display**: Show book information, covers, and file details
- **Search Functionality**: Search through book titles and authors
- **Health Monitoring**: API health checks and status monitoring

## Architecture

This app works in conjunction with the **Calibre Sync API**:

- **Ebook Management API** (this app): Runs on server, provides read-only book listing from NAS replica
- **Calibre Sync API**: Runs on Windows PC, handles write operations and sync to replicas

## Configuration

### Environment Variables

- `REPLICA_PATHS`: Comma-separated list of replica paths to read from
- `CALIBRE_LIBRARY_PATH`: Path to metadata.db (usually in first replica)
- `LOG_LEVEL`: Logging level (default: "INFO")
- `LOG_FILE`: Path to log file (optional)

### Docker Deployment

See the `ebook-management/docker-compose.yaml` file for Traefik integration and homelab deployment.

## API Endpoints

### Books
- `GET /libraries/{location_id}/books` - List books from location (calibre or replica1, replica2, etc.)
- `GET /books/search?q={query}` - Search books
- `GET /books/{book_id}/metadata` - Get book metadata
- `GET /books/{book_id}/cover` - Get book cover image

### Health
- `GET /health` - Application health check
- `GET /` - API information

## Development

### Local Development

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set environment variables**:
   ```bash
   export REPLICA_PATHS="/path/to/replica1,/path/to/replica2"
   export CALIBRE_LIBRARY_PATH="/path/to/replica1"  # For metadata.db access
   ```

3. **Run the application**:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

### Usage Notes

- This app only **reads** from replica directories
- It does not perform sync operations or modify files
- Sync operations are handled by the separate **Calibre Sync API** running on Windows PC
- The app reads Calibre metadata from `metadata.db` in replica locations
- Books are displayed based on the organized file structure created by the sync process