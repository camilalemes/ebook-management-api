# 🏠 Homelab Integration Guide

Integration instructions for adding Ebook Management API to your existing lemoes-home setup.

## 🔧 Quick Integration

### 1. Copy to your homelab directory:

```bash
# Copy the service to your homelab
cp -r /home/misty/dev/ebook-management-api/ebook-management /home/misty/dev/lemoes-home/

# Or create a symlink for development
ln -s /home/misty/dev/ebook-management-api/ebook-management /home/misty/dev/lemoes-home/ebook-management
```

### 2. Add to your main docker-compose.yaml:

```yaml
include:
  # ... your existing services ...
  - ebook-management/docker-compose.yaml
```

### 3. Add environment variables:

Add these to your main `.env` file:

```env
# Ebook Management Configuration
PC_IP=192.168.50.245      # Your Windows PC IP
PC_SMB_USER=guest         # Windows SMB user (or camilablemes@outlook.com)
PC_SMB_PASS=              # Windows SMB password (or app password)
```

**Note**: NAS access uses your existing `${MEDIA_PATH}` host mount, no additional network config needed.

## 🌐 Network Integration

The service will integrate with your existing infrastructure:

- **Network**: Uses your existing `home` bridge network
- **Domain**: `ebook.lemoes-nest.home` (matches your domain pattern)
- **Traefik**: Automatic routing and SSL (if configured)
- **Homepage**: Appears in Media group with Calibre/Jellyfin
- **Watchtower**: Automatic updates enabled

## 📋 PC Setup Requirements

### SMB Shares to create on your PC:

1. **CalibreLibrary** (OneDrive folder, read-only):
   ```powershell
   # Windows PowerShell (run as Administrator)
   New-SmbShare -Name "CalibreLibrary" -Path "C:\Users\YourName\OneDrive\CalibreLibrary" -ReadAccess Everyone
   ```

2. **EbookReplicas** (fallback storage, read/write):
   ```powershell
   # Create directory and share
   mkdir C:\EbookReplicas
   New-SmbShare -Name "EbookReplicas" -Path "C:\EbookReplicas" -FullAccess Everyone
   ```

## 🗄️ NAS Setup

Create a folder for ebook replicas in your `${MEDIA_PATH}` location:
- **Folder**: `${MEDIA_PATH}/ebook-replicas`
- **Access**: Read/Write for your homelab user
- **Mount**: Direct host mount (like other media services)

## 🚀 Deployment

### Add to your homelab:

1. **Update main docker-compose.yaml**:
   ```yaml
   include:
     # ... existing services ...
     - ebook-management/docker-compose.yaml
   ```

2. **Deploy**:
   ```bash
   cd /home/misty/dev/lemoes-home
   docker-compose up -d ebook-api ebook-network-mounts
   ```

3. **Check status**:
   ```bash
   docker-compose ps | grep ebook
   docker-compose logs ebook-network-mounts
   ```

## 📊 Homepage Dashboard Integration

The service will automatically appear in your Homepage dashboard:

- **Group**: Media (alongside Jellyfin, Calibre, etc.)
- **URL**: `http://ebook.lemoes-nest.home`
- **Widget**: Health status and API info
- **Weight**: 15 (positioned with other media services)

## 🔍 Monitoring Integration

### Watchtower
- Automatic updates enabled with label `com.centurylinklabs.watchtower.enable=true`

### Health Checks
- Built-in health checks for both API and network mounts
- Monitor with: `docker-compose ps` or your existing monitoring

### Logs
- Centralized logging in `${CONFIG_PATH}/ebook-management-api/logs/`
- Network mount status in `ebook-network-mounts` container logs

## 🛠️ Customization

### Domain Configuration
If you use a different domain pattern, update the Traefik rule:
```yaml
- traefik.http.routers.ebook-api.rule=Host("ebook.your-domain.home")
```

### Homepage Grouping
Change the homepage group if desired:
```yaml
- homepage.group=Books  # Instead of Media
```

### Storage Paths
Adjust NAS paths in environment variables:
```env
NAS_SHARE_PATH=/path/to/your/ebook/storage
```

## 🔧 Troubleshooting

### Check network connectivity:
```bash
# From your server
ping 192.168.50.245  # PC
ping 192.168.50.216  # NAS

# Test SMB access
smbclient -L //192.168.50.245 -U guest

# Test NAS SMB access
smbclient -L //192.168.50.216 -U admin
```

### View mount status:
```bash
docker-compose logs ebook-network-mounts
docker-compose exec ebook-network-mounts mountpoint -q /mnt/calibre-library && echo "OK" || echo "FAILED"
```

### API health check:
```bash
curl http://ebook.lemoes-nest.home/health
# or
curl http://localhost:8000/health  # if accessing directly
```

## 🎯 Integration Benefits

✅ **Seamless integration** with your existing homelab  
✅ **Matches your domain and network patterns**  
✅ **Automatic service discovery** via Traefik  
✅ **Homepage dashboard integration**  
✅ **Watchtower automatic updates**  
✅ **No local storage** - pure network mounts  
✅ **Health monitoring** and logging  

Your ebook management service will feel like a native part of your lemoes-home infrastructure!