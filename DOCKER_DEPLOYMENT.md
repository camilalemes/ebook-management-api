# Docker Deployment Guide

## Quick Start

1. **Build and run with docker-compose:**
   ```bash
   docker-compose up -d
   ```

2. **Or build manually:**
   ```bash
   docker build -t ebook-management-api .
   docker run -p 8000:8000 ebook-management-api
   ```

## Configuration

### Environment Variables

Create a `.env` file with your configuration:

```env
CALIBRE_LIBRARY_PATH=/app/data/calibre-library
REPLICA_PATHS=/app/data/replicas/pc,/app/data/replicas/nas
CALIBRE_CMD_PATH=calibredb
LOG_LEVEL=INFO
```

### Volume Mounting

Update the `docker-compose.yml` volumes section with your actual paths:

```yaml
volumes:
  # Main Calibre library (read-only recommended)
  - /your/calibre/library/path:/app/data/calibre-library:ro
  
  # Replica locations
  - /your/pc/replica/path:/app/data/replicas/pc
  - /your/nas/replica/path:/app/data/replicas/nas
  
  # Logs (optional)
  - ./logs:/app/logs
```

## Storage Configuration Options

### 1. OneDrive Integration (PC to Server)

**For OneDrive on Personal PC with App on Server:**

**Option A: SMB/NFS Share (Recommended)**
- Share OneDrive Calibre folder from your PC via SMB/NFS
- Server mounts the share directly from your PC
- No duplication, real-time access when PC is on

**Windows SMB Share Setup:**
```powershell
# Share the OneDrive folder
New-SmbShare -Name "CalibreLibrary" -Path "C:\Users\YourName\OneDrive\CalibreLibrary" -ReadAccess Everyone
```

**Docker Compose with SMB:**
```yaml
volumes:
  - type: volume
    source: calibre-smb
    target: /app/data/calibre-library
    read_only: true
    volume:
      driver: local
      driver_opts:
        type: cifs
        o: "addr=YOUR_PC_IP,ro,guest"
        device: "//YOUR_PC_IP/CalibreLibrary"
```

**Pros:**
- No storage duplication on server
- Real-time access to OneDrive library
- PC remains source of truth

**Cons:**
- Requires PC to be online
- Network dependency

**Option B: Manual Sync Script**
- Create a script to periodically download from OneDrive
- Use rclone or similar tools
- Example with rclone:
  ```bash
  # Install rclone and configure OneDrive
  rclone sync onedrive:CalibreLibrary /app/data/calibre-library
  ```

### 2. Network Storage (NAS)

**NFS Mount:**
```bash
# On host system
sudo mount -t nfs your-nas-ip:/path/to/calibre /mnt/nas-calibre
```

**SMB/CIFS Mount:**
```bash
# On host system  
sudo mount -t cifs //your-nas-ip/calibre /mnt/nas-calibre -o username=your-user
```

**Docker Compose with NFS:**
```yaml
volumes:
  - type: volume
    source: calibre-nfs
    target: /app/data/calibre-library
    volume:
      nocopy: true
      driver_opts:
        type: nfs
        o: addr=your-nas-ip,rw
        device: :/path/to/calibre
```

### 3. Recommended Setup for Your Homelab

```yaml
services:
  ebook-api:
    # ... other config ...
    volumes:
      # OneDrive synced Calibre library (read-only)
      - /home/user/OneDrive/CalibreLibrary:/app/data/calibre-library:ro
      
      # Local PC replica
      - /home/user/ebook-replicas/pc:/app/data/replicas/pc
      
      # NAS replica (primary accessible from anywhere)
      - /mnt/nas/ebook-replicas:/app/data/replicas/nas
      
    environment:
      - CALIBRE_LIBRARY_PATH=/app/data/calibre-library
      - REPLICA_PATHS=/app/data/replicas/pc,/app/data/replicas/nas
```

## Security Considerations

1. **Read-only Calibre library:** Mount the main library as read-only to prevent accidental modifications
2. **User permissions:** The container runs as non-root user `appuser`
3. **Network access:** Only expose necessary ports
4. **File permissions:** Ensure proper ownership of mounted volumes

## Troubleshooting

### Common Issues

1. **Permission denied:**
   ```bash
   # Fix ownership of mounted directories
   sudo chown -R 1000:1000 /path/to/replica/folders
   ```

2. **Calibre command not found:**
   - Calibre is installed in the Docker image
   - Check CALIBRE_CMD_PATH environment variable

3. **OneDrive sync issues:**
   - Verify OneDrive client is running and synced
   - Check file permissions on synced folder
   - Consider using `rsync` for one-way sync if needed

### Health Checks

The container includes health checks. Monitor with:
```bash
docker-compose ps
docker-compose logs ebook-api
```

## Scaling and High Availability

For production use in your homelab:

1. **Reverse Proxy:** Use Traefik or nginx for SSL and routing
2. **Monitoring:** Add Prometheus metrics
3. **Backups:** Regular backup of replica locations
4. **Updates:** Use watchtower for automatic updates

## Network Architecture

```
Internet
   ↓
Your Router/Firewall
   ↓
Home Server (Docker Host)
   ├── OneDrive Sync ← Calibre Library
   ├── Container: ebook-api
   ├── Local Replica (PC backup)
   └── NAS Mount ← Primary accessible replica
```

This setup allows:
- Access from anywhere via your homelab
- Local backups on PC
- Primary storage on NAS for reliability
- OneDrive as source of truth for Calibre library