# WSL Ubuntu 24.04 Installation Guide

This guide documents the complete setup process for n8n-installer on WSL Ubuntu 24.04 with Windows 11 Home, including solutions to common networking issues.

## Environment Setup

- **Host OS:** Windows 11 Home
- **WSL Distribution:** Ubuntu 24.04
- **WSL Mode:** NAT with port forwarding
- **VPN:** wsl-vpnkit (for HTTPS through Kaspersky VPN)
- **Custom SSH Port:** 2223 (forwarded from Windows)

## Installation Issues & Solutions

### Issue 1: UFW Firewall Blocked Custom SSH Port (2223)

**Problem:** After running `sudo bash ./scripts/install.sh`, SSH access on port 2223 stopped working.

**Root Cause:** The installation script configured UFW to allow only standard ports (22, 80, 443) but not the custom SSH port 2223.

**Solution:**

1. **Code Fix** - Added to `scripts/01_system_preparation.sh:28`:
   ```bash
   ufw allow ssh
   ufw allow 2223/tcp comment 'WSL SSH Custom Port'
   ufw allow http
   ufw allow https
   ```

2. **Manual Fix** (if already installed):
   ```bash
   sudo ufw allow 2223/tcp comment 'WSL SSH Custom Port'
   sudo ufw reload
   ```

### Issue 2: Windows Firewall Not Allowing HTTP/HTTPS Traffic

**Problem:** Ports 80 and 443 were not accessible from the internet.

**Root Cause:** Windows Firewall and HyperV firewall were not configured to allow inbound traffic on ports 80/443.

**Solution on Windows PowerShell (Administrator):**

```powershell
# HyperV Firewall rules
New-NetFirewallHyperVRule `
    -Name "WSL-HTTP-HyperV" `
    -DisplayName "WSL HTTP Server HyperV Port 80" `
    -Direction Inbound `
    -VMCreatorId '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' `
    -Protocol TCP `
    -LocalPorts 80 `
    -Action Allow

New-NetFirewallHyperVRule `
    -Name "WSL-HTTPS-HyperV" `
    -DisplayName "WSL HTTPS Server HyperV Port 443" `
    -Direction Inbound `
    -VMCreatorId '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' `
    -Protocol TCP `
    -LocalPorts 443 `
    -Action Allow

# Standard Windows Firewall rules
New-NetFirewallRule -DisplayName "Allow HTTP Inbound" -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow
New-NetFirewallRule -DisplayName "Allow HTTPS Inbound" -Direction Inbound -Protocol TCP -LocalPort 443 -Action Allow
```

### Issue 3: Docker Port Binding Conflicts with Windows Port Proxy

**Problem:** Docker failed to start with error:
```
Error: ports are not available: exposing port TCP 0.0.0.0:80 -> 127.0.0.1:0: bind: Only one usage of each socket address is normally permitted
```

**Root Cause:** Windows IP Helper service (iphlpsvc) was occupying ports 80/443 for port forwarding before Docker could bind to them inside WSL.

**Solution:**

1. **Code Fix** - Modified `docker-compose.yml:212-214`:
   ```yaml
   # Before (caused conflicts):
   ports:
     - "0.0.0.0:80:80"

   # After (works correctly):
   ports:
     - "80:80"    # Without IP binding = listens on all interfaces
     - "443:443"
     - "7687:7687"
   ```

2. **Correct Installation Sequence:**

   **Step 1 - On Windows PowerShell (Administrator):**
   ```powershell
   # Remove any existing port proxy rules
   netsh interface portproxy delete v4tov4 listenport=80 listenaddress=0.0.0.0
   netsh interface portproxy delete v4tov4 listenport=443 listenaddress=0.0.0.0

   # Verify ports are free
   netstat -ano | findstr ":80 " | findstr "LISTENING"
   netstat -ano | findstr ":443 " | findstr "LISTENING"
   ```

   **Step 2 - In WSL Ubuntu:**
   ```bash
   cd /home/ssh_p_ub_wsl6/localai/n8n-installer-yk
   sudo python3 start_services.py
   ```

   **Step 3 - After Docker starts successfully, on Windows PowerShell (Administrator):**
   ```powershell
   # Get WSL IP address
   $wslIp = (wsl hostname -I).Split()[0].Trim()
   Write-Host "WSL IP: $wslIp" -ForegroundColor Green

   # Configure port forwarding
   netsh interface portproxy add v4tov4 listenport=80 listenaddress=0.0.0.0 connectport=80 connectaddress=$wslIp
   netsh interface portproxy add v4tov4 listenport=443 listenaddress=0.0.0.0 connectport=443 connectaddress=$wslIp
   netsh interface portproxy add v4tov4 listenport=2223 listenaddress=0.0.0.0 connectport=2223 connectaddress=$wslIp

   # Verify configuration
   netsh interface portproxy show all
   ```

### Issue 4: IP Helper Service Conflicts

**Problem:** Even after removing port proxy rules, ports remained occupied by process ID 5060 (svchost.exe - iphlpsvc).

**Solution on Windows PowerShell (Administrator):**
```powershell
# Restart IP Helper service to clear port bindings
Restart-Service iphlpsvc

# Wait a few seconds
Start-Sleep -Seconds 3

# Then proceed with Step 1 from Issue 3
```

## Complete Installation Procedure

### Prerequisites

1. WSL Ubuntu 24.04 installed
2. wsl-vpnkit configured (if using VPN)
3. Windows 11 with administrator access

### Installation Steps

**1. Initial Installation (in WSL):**
```bash
cd /path/to/n8n-installer-yk
sudo bash ./scripts/install.sh
```

**2. Fix UFW (if port 2223 was already configured):**
```bash
sudo ufw allow 2223/tcp comment 'WSL SSH Custom Port'
sudo ufw reload
```

**3. Configure Windows Firewall (PowerShell as Administrator):**
```powershell
# HyperV rules for ports 80, 443, 2223
New-NetFirewallHyperVRule -Name "WSL-SSH-HyperV" -DisplayName "WSL SSH Server HyperV Port 2223" -Direction Inbound -VMCreatorId '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' -Protocol TCP -LocalPorts 2223 -Action Allow

New-NetFirewallHyperVRule -Name "WSL-HTTP-HyperV" -DisplayName "WSL HTTP Server HyperV Port 80" -Direction Inbound -VMCreatorId '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' -Protocol TCP -LocalPorts 80 -Action Allow

New-NetFirewallHyperVRule -Name "WSL-HTTPS-HyperV" -DisplayName "WSL HTTPS Server HyperV Port 443" -Direction Inbound -VMCreatorId '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' -Protocol TCP -LocalPorts 443 -Action Allow

# Standard Windows Firewall rules
New-NetFirewallRule -DisplayName "Allow HTTP Inbound" -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow
New-NetFirewallRule -DisplayName "Allow HTTPS Inbound" -Direction Inbound -Protocol TCP -LocalPort 443 -Action Allow
```

**4. Restart IP Helper and clear port forwarding:**
```powershell
Restart-Service iphlpsvc
Start-Sleep -Seconds 3

netsh interface portproxy delete v4tov4 listenport=80 listenaddress=0.0.0.0
netsh interface portproxy delete v4tov4 listenport=443 listenaddress=0.0.0.0
```

**5. Start Docker services (in WSL):**
```bash
cd /home/ssh_p_ub_wsl6/localai/n8n-installer-yk
sudo python3 start_services.py
```

**6. Configure port forwarding AFTER Docker starts (PowerShell):**
```powershell
$wslIp = (wsl hostname -I).Split()[0].Trim()
Write-Host "WSL IP: $wslIp" -ForegroundColor Green

netsh interface portproxy add v4tov4 listenport=80 listenaddress=0.0.0.0 connectport=80 connectaddress=$wslIp
netsh interface portproxy add v4tov4 listenport=443 listenaddress=0.0.0.0 connectport=443 connectaddress=$wslIp
netsh interface portproxy add v4tov4 listenport=2223 listenaddress=0.0.0.0 connectport=2223 connectaddress=$wslIp

netsh interface portproxy show all
```

## Network Architecture

```
Internet (ports 80/443)
  ↓
Windows 11 Firewall (HyperV + Standard rules)
  ↓
Windows IP Helper (iphlpsvc - portproxy)
  ↓
WSL Ubuntu 24.04 (172.30.118.76:80/443)
  ↓
Docker Network
  ↓
Caddy Reverse Proxy (ports 80/443)
  ↓
n8n, Supabase, and other services
```

## After Windows Reboot

WSL IP address changes after reboot, so you must reconfigure port forwarding:

**On Windows PowerShell (Administrator):**
```powershell
# Remove old rules
netsh interface portproxy delete v4tov4 listenport=80 listenaddress=0.0.0.0
netsh interface portproxy delete v4tov4 listenport=443 listenaddress=0.0.0.0
netsh interface portproxy delete v4tov4 listenport=2223 listenaddress=0.0.0.0

# Get new WSL IP
$wslIp = (wsl hostname -I).Split()[0].Trim()
Write-Host "WSL IP: $wslIp" -ForegroundColor Green

# Add new rules
netsh interface portproxy add v4tov4 listenport=80 listenaddress=0.0.0.0 connectport=80 connectaddress=$wslIp
netsh interface portproxy add v4tov4 listenport=443 listenaddress=0.0.0.0 connectport=443 connectaddress=$wslIp
netsh interface portproxy add v4tov4 listenport=2223 listenaddress=0.0.0.0 connectport=2223 connectaddress=$wslIp
```

## Verification

**1. Check Docker services (in WSL):**
```bash
docker compose -p localai ps
```

**2. Test Caddy locally (in WSL):**
```bash
curl -I http://127.0.0.1:80 -H "Host: n8n.ittelo.biz"
```

**3. Test from Windows:**
```powershell
curl http://localhost:80 -H "Host: n8n.ittelo.biz"
```

**4. Test from internet:**
```bash
curl -I https://n8n.ittelo.biz
curl -I https://supabase.ittelo.biz
```

**5. Monitor Caddy logs for SSL certificate acquisition:**
```bash
docker compose -p localai logs caddy -f | cat
```

## SSL Certificates

Caddy will automatically obtain SSL certificates from Let's Encrypt using HTTP-01 challenge. This process takes 5-10 minutes after the first request to each domain.

**Monitor progress:**
```bash
docker compose -p localai logs caddy --tail=50 | grep -E "certificate|acme|tls"
```

## Troubleshooting

### Ports still occupied after IP Helper restart

Check what's listening:
```powershell
netstat -ano | findstr ":80 " | findstr "LISTENING"
netstat -ano | findstr ":443 " | findstr "LISTENING"

# Find process details
tasklist /svc | findstr "<PID>"
```

### Docker fails to bind ports

Check if Windows portproxy is active:
```powershell
netsh interface portproxy show all
```

If any rules exist for ports 80/443, delete them before starting Docker:
```powershell
netsh interface portproxy delete v4tov4 listenport=80 listenaddress=0.0.0.0
netsh interface portproxy delete v4tov4 listenport=443 listenaddress=0.0.0.0
```

### 502 Bad Gateway from Caddy

This is normal for services that are not configured or not running. Check which services are actually enabled in your `.env` file:
```bash
grep COMPOSE_PROFILES .env
```

Only services listed in `COMPOSE_PROFILES` will be started.

### Let's Encrypt cannot validate domain

Ensure:
1. DNS points to your external IP: `nslookup n8n.ittelo.biz`
2. Port 80 is accessible from internet: `curl -I http://n8n.ittelo.biz`
3. Router forwards ports 80/443 to Windows machine
4. Windows Firewall allows inbound traffic on 80/443
5. Port forwarding is configured correctly on Windows

## Files Modified

- `scripts/01_system_preparation.sh` - Added UFW rule for port 2223
- `docker-compose.yml` - Changed port binding from `"0.0.0.0:80:80"` to `"80:80"`

## Important Notes

1. **Order of operations is critical:** Delete portproxy → Start Docker → Configure portproxy
2. **WSL IP changes after reboot** - must reconfigure portproxy rules
3. **PyYAML required:** `pip3 install pyyaml` (already done during troubleshooting)
4. **Security:** Your domains are being scanned from the internet - this is normal but ensure all services have proper authentication

## Next Steps

- Wait 5-10 minutes for SSL certificates to be issued
- Access services via HTTPS:
  - https://n8n.ittelo.biz/
  - https://supabase.ittelo.biz/
  - (other configured services)
- Set up automatic port forwarding script for Windows startup (optional)
