#!/bin/bash

# Pure Server Setup Script - No Local Storage
# Server only runs Docker containers, all data via network shares

set -e

echo "🖥️  Pure Server Setup for Ebook Management API"
echo "=============================================="
echo "Architecture:"
echo "  📱 PC: OneDrive Calibre + Fallback Replica (SMB shares)"
echo "  🖥️  Server: Docker containers only (no local storage)"  
echo "  🗄️  NAS: Primary replica (NFS/SMB share)"
echo

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

prompt_with_default() {
    local prompt="$1"
    local default="$2"
    local result
    read -p "$prompt [$default]: " result
    echo "${result:-$default}"
}

echo -e "${BLUE}📋 Network Configuration...${NC}"
echo

# PC Configuration
PC_IP=$(prompt_with_default "Your PC's IP address" "192.168.1.100")
SMB_USER=$(prompt_with_default "SMB username (leave empty for guest)" "")
SMB_PASS=$(prompt_with_default "SMB password (leave empty for guest)" "")

# NAS Configuration  
NAS_IP=$(prompt_with_default "Your NAS IP address" "192.168.1.200")
NAS_SHARE_PATH=$(prompt_with_default "NAS share path for replicas" "/volume1/ebook-replicas")

# Domain configuration
DOMAIN=$(prompt_with_default "Your domain (for reverse proxy)" "yourdomain.local")
SUBDOMAIN=$(prompt_with_default "Subdomain for the app" "ebook")

echo
echo -e "${YELLOW}⚙️  Creating configuration...${NC}"

# Create .env file
cat > .env << EOF
# Pure Server Configuration (No Local Storage)
PC_IP=$PC_IP
SMB_USER=$SMB_USER
SMB_PASS=$SMB_PASS

# NAS Configuration
NAS_IP=$NAS_IP
NAS_SHARE_PATH=$NAS_SHARE_PATH

# Calibre Library Configuration  
CALIBRE_LIBRARY_PATH=/app/data/calibre-library
REPLICA_PATHS=/app/data/replicas/pc-fallback,/app/data/replicas/nas
CALIBRE_CMD_PATH=calibredb

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_VERSION=1.0.0
API_DEBUG=false

# Logging
LOG_LEVEL=INFO
LOG_FILE=/app/logs/app.log

# Network
DOMAIN=$DOMAIN
SUBDOMAIN=$SUBDOMAIN
EOF

# Create logs directory (only local storage needed)
mkdir -p logs

echo -e "${BLUE}📋 PC Setup Instructions:${NC}"
echo "=========================="
echo
echo "You need to create TWO SMB shares on your PC:"
echo
echo "1. 📚 CalibreLibrary (OneDrive folder, read-only):"
if command -v powershell &> /dev/null || [[ "$OSTYPE" == "msys" ]]; then
    echo "   PowerShell (run as Administrator):"
    echo "   New-SmbShare -Name 'CalibreLibrary' -Path 'C:\\Users\\YourName\\OneDrive\\CalibreLibrary' -ReadAccess Everyone"
    echo
    echo "2. 💾 EbookReplicas (fallback storage, read/write):"
    echo "   New-SmbShare -Name 'EbookReplicas' -Path 'C:\\EbookReplicas' -FullAccess Everyone"
    echo "   # Create the directory first: mkdir C:\\EbookReplicas"
else
    echo "   Windows: Right-click folders → Properties → Sharing → Share"
    echo "   Linux: Configure in /etc/samba/smb.conf"
fi
echo
echo "Share names must be exactly:"
echo "   \\\\$PC_IP\\CalibreLibrary"
echo "   \\\\$PC_IP\\EbookReplicas"
echo

echo -e "${BLUE}📋 NAS Setup Instructions:${NC}"
echo "=========================="
echo
echo "3. 🗄️  Create NFS/SMB share on NAS:"
echo "   Path: $NAS_SHARE_PATH"
echo "   Access: Read/Write for server IP"
echo "   Protocol: NFS v4 (recommended) or SMB"
echo

echo -e "${BLUE}📋 Testing Network Access:${NC}"
echo "=========================="
echo
echo "4. Test connectivity from server:"
echo "   # Test PC connectivity:"
echo "   ping $PC_IP"
echo
echo "   # Test NAS connectivity:"  
echo "   ping $NAS_IP"
echo
echo "   # Test SMB shares from PC:"
echo "   smbclient -L //$PC_IP -U guest"
echo
echo "   # Test NFS share from NAS:"
echo "   showmount -e $NAS_IP"
echo

# Docker network setup
echo -e "${YELLOW}🌐 Setting up Docker network...${NC}"
if command -v docker &> /dev/null; then
    if ! docker network ls | grep -q ebook-network; then
        docker network create ebook-network
        echo "Created ebook-network"
    else
        echo "Network ebook-network already exists"
    fi
else
    echo "Docker not available, skipping network creation"
fi

echo -e "${GREEN}🚀 Deployment Ready!${NC}"
echo
echo "Architecture Summary:"
echo "┌─────────────────────────────┐    ┌─────────────────┐    ┌─────────────────┐"
echo "│        Personal PC          │    │   Home Server   │    │      NAS        │"
echo "│                             │    │   (Docker Only) │    │                 │"
echo "│ 📁 OneDrive/CalibreLibrary  │────┤ 🐳 ebook-api    │────┤ 📚 Primary      │"
echo "│ 💾 EbookReplicas (Fallback) │    │                 │    │    Replica      │"
echo "└─────────────────────────────┘    └─────────────────┘    └─────────────────┘"
echo
echo "Deployment commands:"
echo "  # Start the service:"
echo "  docker-compose -f docker-compose.pure-server.yml up -d"
echo
echo "  # View logs:"
echo "  docker-compose -f docker-compose.pure-server.yml logs -f"
echo
echo "  # Check service status:"
echo "  docker-compose -f docker-compose.pure-server.yml ps"
echo
echo "  # Monitor network mounts:"
echo "  docker-compose -f docker-compose.pure-server.yml logs network-monitor"
echo
echo "URLs after deployment:"
echo "  Health check: http://your-server-ip:8000/health"
echo "  API docs: http://your-server-ip:8000/docs"
echo "  With reverse proxy: https://$SUBDOMAIN.$DOMAIN"
echo

echo -e "${YELLOW}⚠️  Important Notes:${NC}"
echo "===================="
echo "✅ Server has NO local file storage (pure Docker)"
echo "✅ OneDrive library accessed via PC SMB share"
echo "✅ PC fallback replica via SMB share"
echo "✅ NAS primary replica via NFS/SMB"
echo "⚠️  PC must be online for Calibre library access"
echo "⚠️  NAS should always be online for primary replica"
echo "⚠️  Monitor network-monitor logs for connectivity issues"
echo

# Optional: Pre-flight checks
echo -e "${BLUE}🔍 Pre-flight Checks:${NC}"
echo "===================="

echo -n "PC connectivity: "
if ping -c 1 "$PC_IP" &> /dev/null; then
    echo -e "${GREEN}✅ OK${NC}"
else
    echo -e "${RED}❌ FAILED${NC}"
fi

echo -n "NAS connectivity: "
if ping -c 1 "$NAS_IP" &> /dev/null; then
    echo -e "${GREEN}✅ OK${NC}"
else
    echo -e "${RED}❌ FAILED${NC}"
fi

echo

# Optional: Deploy now
read -p "Would you like to start the deployment now? (y/N): " DEPLOY_NOW
if [[ $DEPLOY_NOW =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}🚀 Starting deployment...${NC}"
    
    # Check prerequisites
    if ping -c 1 "$PC_IP" &> /dev/null && ping -c 1 "$NAS_IP" &> /dev/null; then
        echo -e "${GREEN}✅ Network connectivity OK${NC}"
        docker-compose -f docker-compose.pure-server.yml up -d
        echo -e "${GREEN}✅ Deployment started!${NC}"
        echo
        echo "Monitor the startup:"
        echo "docker-compose -f docker-compose.pure-server.yml logs -f network-mounts"
    else
        echo -e "${RED}❌ Network connectivity issues detected${NC}"
        echo "Please ensure both PC and NAS are online and accessible"
        echo "Try deployment again once network issues are resolved"
    fi
fi

echo -e "${GREEN}🎉 Pure server setup complete!${NC}"