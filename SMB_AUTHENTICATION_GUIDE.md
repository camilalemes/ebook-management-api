# 🔐 SMB Authentication Guide for Windows Passwordless Accounts

This guide covers SMB authentication options when using a passwordless Microsoft account with PIN/Windows Hello.

## 🚨 **The Challenge**

If you're using a **passwordless Microsoft account** (with PIN or Windows Hello), you can't directly use your PIN for SMB authentication because:

- PIN is local device authentication only
- SMB requires network-based password authentication
- Linux servers can't authenticate using Windows Hello/PIN over SMB

## ✅ **Authentication Solutions**

### **Option 1: App Password (Recommended for Security)**

Create a Microsoft App Password specifically for SMB access:

#### **Steps:**
1. **Go to Microsoft Account Security:**
   - Visit: https://account.microsoft.com/security
   - Sign in with your Microsoft account (`camilablemes@outlook.com`)

2. **Navigate to Advanced Security:**
   - Go to **Security** → **Advanced security options**
   - Look for **App passwords** section

3. **Create App Password:**
   - Click **Create a new app password**
   - Name it "SMB File Sharing" or "Homelab Access"
   - Copy the generated password (you won't see it again!)

4. **Use in Configuration:**
   ```env
   SMB_USER=camilablemes@outlook.com
   SMB_PASS=YourGeneratedAppPassword
   ```

#### **Pros:**
- ✅ Secure - dedicated password for file sharing
- ✅ Can be revoked independently
- ✅ Works with Microsoft accounts

#### **Cons:**
- ❌ Requires Microsoft account configuration
- ❌ Password stored in config files

---

### **Option 2: Guest Access (Simplest)**

Enable guest access on your Windows SMB shares for password-free authentication:

#### **PowerShell Setup (Run as Administrator):**
```powershell
# Enable SMB protocols
Set-SmbServerConfiguration -EnableSMB1Protocol $false -EnableSMB2Protocol $true

# Create shares with guest access
New-SmbShare -Name "CalibreLibrary" -Path "C:\Users\camil\OneDrive\CalibreLibrary" -ReadAccess "Everyone"
New-SmbShare -Name "EbookReplicas" -Path "C:\EbookReplicas" -FullAccess "Everyone"

# Enable guest access (if needed)
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Lsa" -Name "LimitBlankPasswordUse" -Value 0
```

#### **GUI Alternative:**
1. **Create folders:**
   - OneDrive Calibre folder (already exists)
   - `C:\EbookReplicas` (create new folder)

2. **Share folders:**
   - Right-click folder → Properties → Sharing tab
   - Click "Advanced Sharing"
   - Check "Share this folder"
   - Set share name: `CalibreLibrary` or `EbookReplicas`
   - Click "Permissions" → Add "Everyone" with appropriate access

3. **Set permissions:**
   - `CalibreLibrary`: Everyone = Read
   - `EbookReplicas`: Everyone = Full Control

#### **Configuration:**
```env
SMB_USER=guest
SMB_PASS=
```

#### **Pros:**
- ✅ No password required
- ✅ Simple setup
- ✅ Works immediately

#### **Cons:**
- ❌ Less secure (anyone on network can access)
- ❌ May not work on newer Windows versions
- ❌ Some Windows security policies disable guest access

---

### **Option 3: Dedicated Local User (Most Secure)**

Create a dedicated Windows user account specifically for SMB file sharing:

#### **PowerShell Setup (Run as Administrator):**
```powershell
# Create dedicated SMB user
$Password = ConvertTo-SecureString "StrongPassword123!" -AsPlainText -Force
New-LocalUser -Name "smbuser" -Password $Password -Description "SMB file sharing user" -UserMayNotChangePassword

# Add to Users group
Add-LocalGroupMember -Group "Users" -Member "smbuser"

# Grant specific share access
Grant-SmbShareAccess -Name "CalibreLibrary" -AccountName "smbuser" -AccessRight Read -Force
Grant-SmbShareAccess -Name "EbookReplicas" -AccountName "smbuser" -AccessRight Full -Force
```

#### **Configuration:**
```env
SMB_USER=smbuser
SMB_PASS=StrongPassword123!
```

#### **Pros:**
- ✅ Most secure option
- ✅ Isolated from main user account
- ✅ Can set specific permissions
- ✅ Easy to manage/revoke

#### **Cons:**
- ❌ Requires creating additional user
- ❌ Password stored in config files
- ❌ More complex setup

---

## 🧪 **Testing SMB Access**

### **From Windows (Local Test):**
```cmd
# Test your shares are accessible
net view \\localhost
dir \\localhost\CalibreLibrary
dir \\localhost\EbookReplicas
```

### **From Linux Server:**
```bash
# Test connectivity
ping 192.168.50.245

# Test SMB access with different methods
# Option 1: App Password
smbclient -L //192.168.50.245 -U camilablemes@outlook.com

# Option 2: Guest Access  
smbclient -L //192.168.50.245 -U guest

# Option 3: Dedicated User
smbclient -L //192.168.50.245 -U smbuser

# Test mounting (replace with your chosen method)
sudo mkdir -p /tmp/test-mount
sudo mount -t cifs //192.168.50.245/CalibreLibrary /tmp/test-mount -o username=guest,password=
ls /tmp/test-mount
sudo umount /tmp/test-mount
```

## 🔍 **Troubleshooting**

### **Common Issues:**

#### **"Access Denied" Errors:**
- Verify SMB sharing is enabled in Windows Features
- Check Windows Firewall allows SMB (ports 139, 445)
- Ensure share permissions include your chosen user/Everyone

#### **"Network Path Not Found":**
- Verify PC IP address (192.168.50.245)
- Check PC and server are on same network
- Test with `ping 192.168.50.245` from server

#### **Guest Access Not Working:**
- Windows 10/11 may disable guest access by default
- Try Option 1 (App Password) or Option 3 (Dedicated User)

#### **Microsoft Account Issues:**
- App passwords may not be available on all account types
- Business/work accounts may have different policies
- Try local user approach if app passwords don't work

### **Windows Firewall Configuration:**
```powershell
# Allow SMB through Windows Firewall
New-NetFirewallRule -DisplayName "SMB-In" -Direction Inbound -Protocol TCP -LocalPort 445
New-NetFirewallRule -DisplayName "NetBIOS-In" -Direction Inbound -Protocol TCP -LocalPort 139
```

### **Enable Network Discovery:**
1. Control Panel → Network and Sharing Center
2. Change advanced sharing settings
3. Turn on network discovery
4. Turn on file and printer sharing

## 📊 **Security Comparison**

| Method | Security Level | Complexity | Reliability |
|--------|---------------|------------|-------------|
| **App Password** | 🟢 High | 🟡 Medium | 🟢 High |
| **Guest Access** | 🔴 Low | 🟢 Low | 🟡 Medium |
| **Dedicated User** | 🟢 High | 🟡 Medium | 🟢 High |

## 💡 **Recommendation for Your Setup**

For your **passwordless Microsoft account (`camilablemes@outlook.com`)**, I recommend trying in this order:

1. **Start with Option 2 (Guest Access)** - simplest for home network
2. **If guest fails, use Option 1 (App Password)** - secure and reliable
3. **Option 3 (Dedicated User)** as last resort if others don't work

## 🔧 **Final Configuration**

After choosing your method, update your `.env` file:

```env
# Your chosen authentication method
PC_IP=192.168.50.245
SMB_USER=guest                    # or camilablemes@outlook.com or smbuser
SMB_PASS=                         # or YourAppPassword or StrongPassword123!
NAS_IP=192.168.50.216
NAS_SHARE_PATH=/volume1/ebook-replicas
```

## ✅ **Verification Checklist**

- [ ] Windows SMB shares created (`CalibreLibrary`, `EbookReplicas`)
- [ ] Authentication method chosen and configured
- [ ] Windows Firewall allows SMB traffic
- [ ] Network discovery enabled
- [ ] SMB access tested from Linux server
- [ ] Docker environment variables updated
- [ ] File permissions verified (read/write as appropriate)

Your SMB authentication is now ready for homelab integration!