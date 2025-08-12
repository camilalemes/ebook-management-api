# 📚 Ebook Management API

A comprehensive FastAPI-based system for managing Calibre ebook libraries with intelligent synchronization, Docker support, and modern Angular frontend integration. Perfect for homelab deployments and multi-device ebook management.

## ✨ Features

### Core Functionality
- **📖 Library Management**: Browse, search, and manage your Calibre ebook collection
- **🔄 Intelligent Sync**: Automated synchronization to multiple replica locations with change detection
- **📱 Multi-Device Support**: Access your library from anywhere via your homelab
- **☁️ OneDrive Integration**: Sync with OneDrive-hosted Calibre libraries
- **🏠 NAS Support**: Primary storage on Network Attached Storage for reliability
- **🔍 Library Comparison**: Compare main library with replicas to find differences

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

## ⚙️ Configuration

### Environment Variables

```env
# Calibre Library Configuration
CALIBRE_LIBRARY_PATH=/path/to/calibre/library
REPLICA_PATHS=/path/to/replica1,/path/to/replica2
CALIBRE_CMD_PATH=calibredb

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_DEBUG=false

# Logging
LOG_LEVEL=INFO
LOG_FILE=/app/logs/app.log
```

### Storage Options

1. **OneDrive Library**: Install OneDrive client and sync locally
2. **NAS Integration**: Mount via NFS/SMB for network storage
3. **Local Storage**: Direct file system access

## 🚀 API Endpoints

### Books Management
- `GET /books` - List all books (alphabetically sorted)
- `GET /books/{book_id}` - Get specific book details
- `POST /books/add` - Add new book with file upload
- `DELETE /books/{book_id}` - Remove book from library
- `GET /books/{book_id}/cover` - Get book cover image

### Synchronization
- `POST /sync/trigger` - Start sync process
- `POST /sync/dry-run` - Test sync without changes  
- `GET /sync/status` - Check sync status and results

### Library Comparison
- `POST /comparison/compare` - Compare library with replicas
- `GET /comparison/results` - Get comparison results

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
│   │   ├── books.py         # Book management
│   │   ├── sync.py          # Synchronization
│   │   └── comparison.py    # Library comparison
│   ├── services/            # Business logic
│   │   ├── calibre_service.py
│   │   └── sync_service.py
│   └── models/              # Data models
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

## 📊 Monitoring & Logging

- **Health Checks**: `/health` endpoint for monitoring
- **Structured Logging**: JSON logs with rotation
- **Sync Statistics**: Detailed operation reports
- **Error Handling**: Comprehensive exception handling

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