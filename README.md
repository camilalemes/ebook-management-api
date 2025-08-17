# 📚 Ebook Management API

A comprehensive FastAPI-based system for managing Calibre ebook libraries with intelligent synchronization, Docker support, and modern Angular frontend integration. Perfect for homelab deployments and multi-device ebook management.

## ✨ Features

### Core Functionality
- **📖 Multi-Library Support**: Browse multiple Calibre libraries simultaneously
- **⚡ Direct Database Access**: Optimized performance with direct SQLite metadata.db access
- **🌐 Network Library Support**: SMB/NFS mounted libraries with network optimizations
- **🔍 Advanced Search & Filtering**: Search by title, author, or filter by tags
- **📄 Pagination**: Efficient browsing with configurable page sizes
- **📱 Multi-Device Access**: RESTful API accessible from any device
- **🏷️ Tag Management**: Extract and filter by metadata tags

### Smart Organization
- **📝 Metadata-Based Renaming**: Files renamed using "Title - Author.ext" format from Calibre metadata
- **📁 Format Organization**: Automatic organization by file type (epub/, pdf/, mobi/, etc.)
- **🔍 Alphabetical Sorting**: Books listed in alphabetical order by title
- **🚫 Selective Sync**: Ignores system files while preserving essential Calibre metadata

### Advanced Features
- **🧪 Dry Run Mode**: Test synchronization without making changes
- **📊 Detailed Reporting**: Comprehensive sync results with file-level details
- **🔧 Health Monitoring**: Built-in health checks and status monitoring
- **🐳 Docker Ready**: Full containerization support for easy deployment
- **🌐 Modern UI**: Angular 20 frontend with Material Design


## 🛠️ Manual Installation

### Prerequisites
- Python 3.11+
- Calibre installed and accessible via command line
- Node.js 18+ (for frontend)

### Backend Setup

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your paths
   ```

3. **Start the API server:**
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

### Frontend Setup

1. **Navigate to UI directory:**
   ```bash
   cd /path/to/ebook-management-ui
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Start development server:**
   ```bash
   npm start
   ```

## 🐳 Docker Quick Start (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd ebook-management-api

# Create configuration
cp .env.example .env
# Edit .env with your library paths

# Build and run with docker-compose
docker-compose up -d

# Or build and run manually
docker build -t ebook-management-api .
docker run -d \
  --name ebook-api \
  -p 8000:8000 \
  -v /path/to/your/libraries:/libraries:ro \
  -e LIBRARY_PATHS=/libraries/library1,/libraries/library2 \
  -e PUID=1000 \
  -e PGID=1000 \
  ebook-management-api
```

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| **Library Configuration** |
| `LIBRARY_PATHS` | Comma-separated paths to Calibre libraries | `""` | `/libraries/main,/libraries/backup` |
| `CALIBRE_CMD_PATH` | Path to calibredb executable | `calibredb` | `/usr/bin/calibredb` |
| **API Configuration** |
| `API_HOST` | API server host | `0.0.0.0` | `0.0.0.0` |
| `API_PORT` | API server port | `8000` | `8000` |
| `API_DEBUG` | Enable debug mode | `false` | `true` |
| `API_VERSION` | API version string | `1.0.0` | `1.0.0` |
| **CORS Configuration** |
| `CORS_ORIGINS` | Allowed CORS origins (comma-separated) | `http://localhost:3000,http://localhost:4200` | `https://ebooks.example.com` |
| **Logging Configuration** |
| `LOG_LEVEL` | Logging level | `INFO` | `DEBUG` |
| `LOG_FILE` | Log file path (optional) | `None` | `/app/logs/app.log` |
| `LOG_ROTATION_SIZE` | Log rotation size in bytes | `10485760` | `50MB` |
| `LOG_BACKUP_COUNT` | Number of backup log files | `5` | `10` |
| **Performance Configuration** |
| `CACHE_TTL` | Cache TTL in seconds | `300` | `600` |
| `SYNC_BATCH_SIZE` | Sync batch size | `100` | `50` |
| `SYNC_TIMEOUT` | Sync timeout in seconds | `3600` | `1800` |
| **Docker Configuration** |
| `PUID` | User ID for file permissions | `1000` | `1000` |
| `PGID` | Group ID for file permissions | `1000` | `1000` |
| `TZ` | Timezone | `UTC` | `America/New_York` |

### Docker Compose Example

```yaml
version: '3.8'
services:
  ebook-api:
    image: ebook-management-api:latest
    container_name: ebook-api
    ports:
      - "8000:8000"
    volumes:
      - /path/to/calibre/libraries:/libraries:ro
      - ./logs:/app/logs
      - ./config:/config
    environment:
      - LIBRARY_PATHS=/libraries/main,/libraries/backup
      - API_DEBUG=false
      - LOG_LEVEL=INFO
      - CORS_ORIGINS=http://localhost:4200,https://ebooks.yourdomain.com
      - PUID=1000
      - PGID=1000
      - TZ=UTC
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Storage Options

1. **OneDrive Library**: Install OneDrive client and sync locally
2. **NAS Integration**: Mount via NFS/SMB for network storage
3. **Local Storage**: Direct file system access

## 🚀 API Endpoints

### Books Management
- `GET /libraries` - List available library locations
- `GET /libraries/{library_id}/books` - List books with pagination and search
- `GET /books/{book_id}/metadata` - Get detailed book metadata
- `GET /libraries/{library_id}/books/{book_id}/cover` - Get book cover image
- `GET /books/{book_id}/download` - Download book in preferred format
- `GET /books/search` - Search books by title or author

### Query Parameters
- `page` - Page number for pagination (default: 1)
- `page_size` - Items per page (default: 50, max: 200)
- `search` - Search term for filtering by title/author
- `tag_filter` - Filter books by specific tag (e.g., 'mistyebook')

### System
- `GET /health` - Health check endpoint
- `GET /` - API information and version

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Angular UI    │    │   FastAPI       │    │   Calibre       │
│   (Port 4200)   │◄──►│   Backend       │◄──►│   Library       │
│                 │    │   (Port 8000)   │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   Sync Service  │
                       │                 │
                       └─────────┬───────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
              ┌──────────┐ ┌──────────┐ ┌──────────┐
              │ OneDrive │ │ NAS      │ │ Local    │
              │ Source   │ │ Primary  │ │ Backup   │
              └──────────┘ └──────────┘ └──────────┘
```

## 📁 Project Structure

```
ebook-management-api/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration management
│   ├── routers/             # API endpoints
│   │   └── books_enhanced.py # Optimized book management with direct DB access
│   ├── services/            # Business logic
│   │   ├── calibre_db_service.py  # Direct SQLite database service
│   │   └── library_service.py     # Multi-library management
│   ├── models/              # Pydantic data models
│   ├── middleware/          # Custom middleware
│   ├── exceptions/          # Custom exceptions
│   └── utils/               # Utilities (logging, etc.)
├── Dockerfile               # Container configuration
├── docker-compose*.yml      # Container orchestration
├── requirements.txt         # Python dependencies
├── setup-homelab.sh        # Interactive setup script
└── DOCKER_DEPLOYMENT.md    # Docker documentation
```

## 🔧 Development

### Running Tests
```bash
pytest tests/
```

### Code Style
```bash
black app/
flake8 app/
```

### Database Migrations
The application uses Calibre's existing database structure and doesn't require separate migrations.

## 🚀 Deployment

### Production Deployment

```bash
# Build production image
docker build -t ebook-management-api:latest .

# Deploy with environment file
docker run -d \
  --name ebook-api \
  --restart unless-stopped \
  -p 8000:8000 \
  -v /path/to/calibre/libraries:/libraries:ro \
  -v /path/to/logs:/app/logs \
  --env-file .env \
  ebook-management-api:latest
```

### Reverse Proxy Configuration

#### Nginx
```nginx
server {
    listen 80;
    server_name ebooks.yourdomain.com;
    
    location /api/v1/ {
        proxy_pass http://localhost:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Optional: Serve UI from same domain
    location / {
        proxy_pass http://localhost:4200;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

#### Traefik
```yaml
# docker-compose.yml
version: '3.8'
services:
  ebook-api:
    image: ebook-management-api:latest
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.ebook-api.rule=Host(`ebooks.yourdomain.com`) && PathPrefix(`/api/v1`)"
      - "traefik.http.services.ebook-api.loadbalancer.server.port=8000"
    networks:
      - traefik
```

## 📊 Monitoring & Logging

### Health Monitoring
- **Health Check Endpoint**: `GET /health` - Returns API status and library accessibility
- **Metrics**: Built-in performance metrics and request logging
- **Docker Health Checks**: Integrated container health monitoring

### Logging Configuration
- **Structured Logging**: JSON format with configurable levels
- **Log Rotation**: Automatic rotation based on size and retention policy
- **Request Logging**: Full HTTP request/response logging with timing
- **Error Tracking**: Comprehensive exception handling and logging

### Monitoring Endpoints
- `GET /health` - Application health status
- `GET /` - API information and version
- `GET /docs` - Interactive API documentation (Swagger UI)
- `GET /redoc` - Alternative API documentation

## 🔧 Troubleshooting

### Common Issues

**Library Path Not Found**
```bash
# Check library paths are accessible
docker exec ebook-api ls -la /libraries

# Verify permissions
docker exec ebook-api stat /libraries/your-library
```

**Permission Denied Errors**
```bash
# Fix file permissions (run as root or with sudo)
chown -R 1000:1000 /path/to/calibre/libraries
chmod -R 755 /path/to/calibre/libraries

# Or adjust PUID/PGID in docker-compose
environment:
  - PUID=1001  # Use your user ID
  - PGID=1001  # Use your group ID
```

**API Connection Issues**
```bash
# Check API is running
curl http://localhost:8000/health

# Check logs
docker logs ebook-api

# Verify network connectivity
docker exec ebook-api ping host.docker.internal
```

**Calibre Database Issues**
```bash
# Verify database accessibility
docker exec ebook-api sqlite3 /libraries/your-library/metadata.db ".tables"

# Check calibredb availability
docker exec ebook-api calibredb --version
```

### Debug Mode

Enable debug mode for detailed logging:
```env
API_DEBUG=true
LOG_LEVEL=DEBUG
```

### Performance Tuning

```env
# Increase cache TTL for better performance
CACHE_TTL=600

# Adjust batch size for large libraries
SYNC_BATCH_SIZE=50

# Tune timeout for slow networks
SYNC_TIMEOUT=1800
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: See [DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md) for Docker setup
- **Issues**: Report bugs via GitHub Issues
- **Discussions**: Use GitHub Discussions for questions

## 🎯 Roadmap

- [ ] Multi-user support with authentication
- [ ] Advanced search and filtering
- [ ] Book reading progress tracking
- [ ] Mobile app integration
- [ ] Automated metadata enhancement
- [ ] Backup scheduling and automation

---

**Perfect for**: Homelab enthusiasts, book collectors, and anyone wanting centralized ebook management with multi-device access.