# 🪟 Windows PC Setup Guide

Your Windows PC will host the OneDrive Calibre library and serve files via SMB shares to your Linux server.

## 📁 Required SMB Shares

You need to create **TWO** SMB shares on your Windows PC:

### 1. CalibreLibrary Share (OneDrive, Read-Only)

**Location**: Your OneDrive Calibre folder  
**Typical path**: `C:\Users\YourName\OneDrive\CalibreLibrary`

**PowerShell setup (Run as Administrator):**
```powershell
# Share your OneDrive Calibre library (read-only)
New-SmbShare -Name "CalibreLibrary" -Path "C:\Users\$env:USERNAME\OneDrive\CalibreLibrary" -ReadAccess Everyone
```

**GUI Alternative:**
1. Right-click your OneDrive Calibre folder
2. Properties → Sharing tab → Advanced Sharing
3. Share name: `CalibreLibrary`
4. Permissions: Everyone (Read only)

### 2. EbookReplicas Share (Fallback Storage, Read/Write)

**Location**: Local folder for fallback replica  
**Suggested path**: `C:\EbookReplicas`

**PowerShell setup (Run as Administrator):**
```powershell
# Create directory for fallback replica
New-Item -ItemType Directory -Path "C:\EbookReplicas" -Force

# Share the fallback replica folder (read/write)
New-SmbShare -Name "EbookReplicas" -Path "C:\EbookReplicas" -FullAccess Everyone
```

**GUI Alternative:**
1. Create folder `C:\EbookReplicas`
2. Right-click → Properties → Sharing → Advanced Sharing
3. Share name: `EbookReplicas`
4. Permissions: Everyone (Full Control)

## 🔧 Windows Configuration

### Enable SMB File Sharing

1. **Enable SMB in Windows Features:**
   - Open "Turn Windows features on or off"
   - Enable "SMB 1.0/CIFS File Sharing Support" (if needed for compatibility)
   - Enable "SMB Direct" (for better performance)

2. **Network Discovery:**
   - Control Panel → Network and Sharing Center
   - Change advanced sharing settings
   - Turn on network discovery
   - Turn on file and printer sharing

### Firewall Configuration

**Allow SMB through Windows Firewall:**
```powershell
# Run as Administrator
New-NetFirewallRule -DisplayName "SMB-In" -Direction Inbound -Protocol TCP -LocalPort 445
New-NetFirewallRule -DisplayName "NetBIOS-In" -Direction Inbound -Protocol TCP -LocalPort 139
```

**Or via GUI:**
1. Windows Firewall → Allow an app through firewall
2. Enable "File and Printer Sharing"

## 🔍 Testing SMB Shares

### From Windows (Local Test):
```cmd
# Test access to your own shares
net view \\localhost
dir \\localhost\CalibreLibrary
dir \\localhost\EbookReplicas
```

### From Linux Server:
```bash
# Test SMB connectivity from your server
smbclient -L //YOUR_PC_IP -U guest

# Test mounting (replace YOUR_PC_IP)
sudo mkdir -p /tmp/test-calibre
sudo mount -t cifs //YOUR_PC_IP/CalibreLibrary /tmp/test-calibre -o ro,guest
ls /tmp/test-calibre
sudo umount /tmp/test-calibre
```

## 📊 Folder Structure

Your Windows PC will look like this:
```
C:\
├── Users\YourName\OneDrive\
│   └── CalibreLibrary\          # ← SMB Share "CalibreLibrary" (read-only)
│       ├── metadata.db
│       ├── Author Name\
│       │   └── Book Title (123)\
│       │       ├── book.epub
│       │       ├── cover.jpg
│       │       └── metadata.opf
│       └── ...
└── EbookReplicas\               # ← SMB Share "EbookReplicas" (read/write)
    ├── epubs\
    ├── mobi\
    ├── pdf\
    └── ...
```

## 🚀 Environment Variables

Update your server's `.env` file with your Windows PC details:

```env
# Your Windows PC configuration
PC_IP=192.168.50.245        # Your PC's IP address
SMB_USER=guest              # Use 'guest' for simple setup
SMB_PASS=                   # Empty for guest access

# Or use your Windows credentials:
# SMB_USER=YourWindowsUsername
# SMB_PASS=YourWindowsPassword
```

## 🔐 Security Options

### Option 1: Guest Access (Simplest)
- Uses `guest` user with no password
- Suitable for home networks
- Already configured in the docker-compose

### Option 2: Windows Credentials
- Use your Windows username/password
- More secure but requires credential management
- Update docker-compose environment:
  ```yaml
  - SMB_USER=YourWindowsUsername
  - SMB_PASS=YourWindowsPassword
  ```

### Option 3: Dedicated SMB User
Create a dedicated user for SMB access:
```powershell
# Create new user (Run as Administrator)
New-LocalUser -Name "smbuser" -Password (ConvertTo-SecureString "YourPassword" -AsPlainText -Force)
Add-LocalGroupMember -Group "Users" -Member "smbuser"
```

## ⚠️ Common Issues & Solutions

### "Access Denied" Errors:
- Ensure SMB sharing is enabled
- Check Windows Firewall settings
- Verify share permissions (Everyone with appropriate access)

### "Network Path Not Found":
- Check PC IP address is correct
- Ensure PC is on the same network as server
- Test with `ping YOUR_PC_IP` from server

### Performance Issues:
- Enable SMB Direct in Windows Features
- Use SMB 3.0+ (default in Windows 10/11)
- Ensure good network connection between PC and server

### OneDrive Sync Issues:
- Ensure OneDrive is actively syncing
- Check OneDrive settings for selective sync
- Verify Calibre library is fully synced

## 🔄 Power Management

**Important**: Your PC needs to be powered on for the server to access the Calibre library.

**Recommendations:**
- Configure "Sleep" settings to keep network active
- Use "Fast Startup" for quicker wake-up
- Consider Wake-on-LAN if you want remote power control

**Power Settings:**
1. Control Panel → Power Options
2. Change plan settings → Advanced settings
3. Network adapters → Allow computer to sleep: Disabled (if you want always-on access)

## ✅ Verification Checklist

- [ ] OneDrive Calibre library is syncing
- [ ] `CalibreLibrary` SMB share created (read-only)
- [ ] `EbookReplicas` SMB share created (read/write)
- [ ] Windows Firewall allows SMB
- [ ] Network discovery enabled
- [ ] SMB shares accessible from Linux server
- [ ] PC stays powered on (or appropriate power settings)

Your Windows PC is now ready to serve your Calibre library to your Linux homelab server!