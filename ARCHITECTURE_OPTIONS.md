# 🏗️ Server Deployment Architecture Options

Since your OneDrive Calibre library is on your personal PC and the app will run on your server, here are the recommended approaches:

## 🎯 Recommended Architecture: Pure Docker Server

```
┌─────────────────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│        Personal PC          │    │   Home Server   │    │      NAS        │
│                             │    │   (Docker Only) │    │                 │
│ ┌─────────────┐ ┌─────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │  OneDrive   │ │ Fallback│ │    │ │ Docker App  │ │    │ │   Primary   │ │
│ │   Calibre   │ │ Replica │ │◄───┼►│   (No       │◄┼────┼►│  Replica    │ │
│ │  Library    │ │         │ │    │ │  Storage)   │ │    │ │ (Always On) │ │
│ └─────────────┘ └─────────┘ │    │ └─────────────┘ │    │ └─────────────┘ │
│      (Source)    (Backup)   │    │                 │    │                 │
└─────────────────────────────┘    └─────────────────┘    └─────────────────┘
```

### Option 1: SMB/NFS Share from PC (Recommended)

**Setup on Personal PC:**
1. **Enable file sharing** for your OneDrive Calibre folder
2. **Windows SMB Share:**
   ```powershell
   # Share the OneDrive Calibre folder
   New-SmbShare -Name "CalibreLibrary" -Path "C:\Users\YourName\OneDrive\CalibreLibrary" -ReadAccess Everyone
   ```

3. **Linux/Ubuntu SMB Share:**
   ```bash
   # Install Samba
   sudo apt install samba
   
   # Edit /etc/samba/smb.conf
   [calibre-library]
   path = /home/user/OneDrive/CalibreLibrary
   read only = yes
   browsable = yes
   guest ok = yes
   ```

**Docker Compose on Server:**
```yaml
services:
  ebook-api:
    # ... other config ...
    volumes:
      # Mount SMB share from your PC
      - type: volume
        source: calibre-smb
        target: /app/data/calibre-library
        read_only: true
        volume:
          driver: local
          driver_opts:
            type: cifs
            o: "addr=YOUR_PC_IP,ro,username=guest,password="
            device: "//YOUR_PC_IP/CalibreLibrary"
      
      # NAS replicas
      - /mnt/nas/ebook-replicas:/app/data/replicas/nas
```

## 🔄 Alternative Options

### Option 2: Periodic Sync with rclone

**Setup rclone on server:**
```bash
# Install rclone
curl https://rclone.org/install.sh | sudo bash

# Configure OneDrive
rclone config
# Follow prompts to set up OneDrive access
```

**Sync script (run periodically):**
```bash
#!/bin/bash
# sync-onedrive.sh
rclone sync onedrive:CalibreLibrary /app/data/calibre-library --log-level INFO
```

**Cron job for automatic sync:**
```bash
# Every 4 hours
0 */4 * * * /path/to/sync-onedrive.sh
```

### Option 3: OneDrive on Server

**Install OneDrive client on server:**
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install onedrive

# Configure OneDrive
onedrive --configure

# Selective sync just the Calibre library
onedrive --synchronize --single-directory 'CalibreLibrary'
```

**Docker Compose:**
```yaml
services:
  ebook-api:
    volumes:
      # OneDrive synced on server
      - /home/user/OneDrive/CalibreLibrary:/app/data/calibre-library:ro
```

### Option 4: Git-LFS or Syncthing

**For version control approach:**
- Use Git-LFS for the Calibre library
- Automatic sync between PC and server
- Version history of library changes

## 📋 Comparison Matrix

| Option | Pros | Cons | Complexity |
|--------|------|------|------------|
| **SMB/NFS Share** | Real-time access, no duplication | Requires PC to be on | Medium |
| **rclone Periodic** | Works with PC off, cloud backup | Sync delays, requires tokens | Low |
| **OneDrive on Server** | Real-time sync, always available | Uses server storage | Low |
| **Git-LFS** | Version control, distributed | Complex for binaries | High |

## 🎯 Recommended Setup for Your Use Case

### Primary Recommendation: SMB Share + NAS
```yaml
# docker-compose.production.yml
version: '3.8'

services:
  ebook-api:
    build: .
    container_name: ebook-management-api
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - CALIBRE_LIBRARY_PATH=/app/data/calibre-library
      - REPLICA_PATHS=/app/data/replicas/nas,/app/data/replicas/backup
    volumes:
      # OneDrive from PC via SMB (read-only)
      - type: volume
        source: calibre-source
        target: /app/data/calibre-library
        read_only: true
      
      # Primary NAS replica (always accessible)
      - /mnt/nas/ebook-replicas:/app/data/replicas/nas
      
      # Local server backup
      - /srv/ebooks/backup:/app/data/replicas/backup
      
    depends_on:
      - calibre-mount

  # Helper service to ensure SMB mount is available
  calibre-mount:
    image: alpine:latest
    command: >
      sh -c "
      apk add --no-cache cifs-utils &&
      mkdir -p /mnt/calibre &&
      mount -t cifs //YOUR_PC_IP/CalibreLibrary /mnt/calibre -o ro,guest &&
      tail -f /dev/null
      "
    privileged: true
    volumes:
      - calibre-source:/mnt/calibre

volumes:
  calibre-source:
    driver: local
```

### Fallback Strategy
```
1. Primary: SMB share from PC (when PC is on)
2. Fallback: Local cache on server (when PC is off)
3. Always available: NAS replica for access
```

## 🔧 Implementation Steps

1. **Set up SMB share on your PC**
2. **Configure server to mount the share**
3. **Deploy Docker containers**
4. **Set up monitoring for share availability**
5. **Configure sync schedules**

## 📊 Monitoring & Availability

**Health check script:**
```bash
#!/bin/bash
# Check if PC share is available
if ! ping -c 1 YOUR_PC_IP &> /dev/null; then
    echo "PC not reachable, using cached library"
    # Switch to cached mode
fi
```

This architecture ensures:
- ✅ **Real-time access** when PC is on
- ✅ **Always available** via NAS replica
- ✅ **No duplicate storage** on server
- ✅ **Automatic failover** when PC is off