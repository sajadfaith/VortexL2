# VortexL2

**L2TPv3 Ethernet Tunnel Manager for Ubuntu/Debian**

A modular, production-quality CLI tool for managing multiple L2TPv3 tunnels and TCP/UDP port forwarding using HAProxy.

```
 __      __        _            _     ___  
 \ \    / /       | |          | |   |__ \ 
  \ \  / /__  _ __| |_ _____  _| |      ) |
   \ \/ / _ \| '__| __/ _ \ \/ / |     / / 
    \  / (_) | |  | ||  __/>  <| |____/ /_ 
     \/ \___/|_|   \__\___/_/\_\______|____|
                                    v2.0.0
```

## ✨ Features

- 🔧 Interactive TUI management panel with Rich
- 🌐 **Multiple L2TPv3 tunnels** on a single server
- 🚀 **High-performance port forwarding via HAProxy**
- 🔄 Systemd integration for persistence
- 📦 One-liner installation
- 🛡️ Duplicate validation for tunnel IDs, session IDs, and IPs
- 🛡️ Secure configuration with 0600 permissions
- 🎯 Fully configurable tunnel IDs

## 📦 Quick Install

```bash
bash <(curl -Ls https://raw.githubusercontent.com/iliya-Developer/VortexL2/main/install.sh)
```

## 🚀 First Run

### 1. Open the Management Panel

```bash
sudo vortexl2
```

### 2. Create Tunnels

Each tunnel needs:
- **Side**: IRAN (receives traffic) or KHAREJ (external server)
- **Tunnel Name**: A unique identifier (e.g., `tunnel1`, `kharej-hetzner`)
- **Local IP**: This server's public IP
- **Remote IP**: The other server's public IP
- **Interface IP**: Tunnel interface IP (e.g., `10.30.30.1/30`)
- **Tunnel IDs**: Unique IDs for the L2TP connection

### 3. Configure Both Sides

Both servers need matching tunnel configurations with swapped values:

| Parameter | IRAN Side | KHAREJ Side |
|-----------|-----------|-------------|
| Local IP | 1.2.3.4 | 5.6.7.8 |
| Remote IP | 5.6.7.8 | 1.2.3.4 |
| Interface IP | 10.30.30.1/30 | 10.30.30.2/30 |
| Tunnel ID | 1000 | 2000 |
| Peer Tunnel ID | 2000 | 1000 |
| Session ID | 10 | 20 |
| Peer Session ID | 20 | 10 |

### 4. Add Port Forwards (IRAN side only)

Select "Port Forwards" and add ports like: `443,80,2053`

HAProxy will automatically handle all port forwarding with excellent performance.

## 📋 Commands

| Command | Description |
|---------|-------------|
| `sudo vortexl2` | Open management panel |
| `sudo vortexl2 apply` | Apply all tunnels (for systemd boot) |
| `sudo vortexl2 --version` | Show version |

## 🔧 Services

VortexL2 uses two systemd services:

| Service | Description |
|---------|-------------|
| `vortexl2-tunnel.service` | Creates L2TP tunnels on boot |
| `vortexl2-forward-daemon.service` | Manages HAProxy port forwarding |

```bash
# Check service status
sudo systemctl status vortexl2-tunnel
sudo systemctl status vortexl2-forward-daemon
sudo systemctl status haproxy

# View logs
journalctl -u vortexl2-tunnel -f
journalctl -u vortexl2-forward-daemon -f
```

## 🚀 HAProxy Port Forwarding (v2.0)

VortexL2 v2.0 uses **HAProxy** for production-grade port forwarding:

### Advantages over previous versions:
- **10x faster** than Python asyncio forwarding
- **Lower latency** with C-based implementation
- **Higher throughput** - handles 10,000+ concurrent connections
- **Better resource usage** - lower CPU and memory consumption
- **Production-ready** - used by AWS, Netflix, and major organizations

### Configuration Location:
```
/etc/haproxy/haproxy.cfg    # HAProxy main config (managed by VortexL2)
/etc/haproxy/haproxy.cfg.bak # Automatic backup of original config
```

### Check HAProxy Status:
```bash
# Check if HAProxy is running
sudo systemctl status haproxy

# List forwarded ports
ss -tlnp | grep haproxy

# View HAProxy stats
echo "show stat" | socat stdio /var/run/haproxy.sock
```

## 🔍 Troubleshooting

### Check Tunnel Status

```bash
# Show L2TP tunnels
ip l2tp show tunnel

# Show L2TP sessions
ip l2tp show session

# Check interface (l2tpeth0, l2tpeth1, etc.)
ip addr show l2tpeth0

# Test connectivity through tunnel
ping 10.30.30.2  # From IRAN side
```

### Check Port Forwards

```bash
# List listening ports (HAProxy)
ss -tlnp | grep haproxy

# Check services
sudo systemctl status haproxy
sudo systemctl status vortexl2-forward-daemon
```

### Common Issues

**❌ Tunnel not working**
1. Ensure both sides have matching tunnel IDs (swapped peer values)
2. Check firewall allows IP protocol 115 (L2TPv3)
3. Verify kernel modules are loaded: `lsmod | grep l2tp`

**❌ Port forward not working**
1. Verify tunnel is up: `ping 10.30.30.2`
2. Check HAProxy status: `systemctl status haproxy`
3. Check forward-daemon service: `systemctl status vortexl2-forward-daemon`
4. Check HAProxy config: `cat /etc/haproxy/haproxy.cfg`

**❌ Interface l2tpeth0 not found**
1. Ensure session is created (not just tunnel)
2. Check kernel modules: `modprobe l2tp_eth`
3. Recreate tunnel from panel

## 🔧 Configuration

Tunnels are stored in `/etc/vortexl2/tunnels/`:

```yaml
# /etc/vortexl2/tunnels/tunnel1.yaml
name: tunnel1
local_ip: "1.2.3.4"
remote_ip: "5.6.7.8"
interface_ip: "10.30.30.1/30"
remote_forward_ip: "10.30.30.2"
tunnel_id: 1000
peer_tunnel_id: 2000
session_id: 10
peer_session_id: 20
interface_index: 0
forwarded_ports:
  - 443
  - 80
  - 2053
```

## 🏗️ Architecture

### Port Forwarding (HAProxy)

```
                    ┌─────────────────┐
                    │   IRAN Server   │
                    │                 │
                    │  ┌───────────┐  │
 Users ──────────►  │  │  HAProxy  │  │
 (443,80,2053)      │  │  (fast)   │  │
                    │  └─────┬─────┘  │
                    │        │        │
                    │  ┌─────▼─────┐  │
                    │  │ l2tpeth0  │  │
                    │  │10.30.30.1 │  │
                    │  └─────┬─────┘  │
                    └────────┼────────┘
                             │
                      L2TPv3 Tunnel
                      (encap ip)
                             │
                    ┌────────┼────────┐
                    │  ┌─────▼─────┐  │
                    │  │ l2tpeth0  │  │
                    │  │10.30.30.2 │  │
                    │  └───────────┘  │
                    │                 │
                    │  KHAREJ Server  │
                    │   5.6.7.8       │
                    └─────────────────┘
```

## 📁 Project Structure

```
VortexL2/
├── vortexl2/
│   ├── __init__.py          # Package info (v2.0.0)
│   ├── main.py              # CLI entry point
│   ├── config.py            # Multi-tunnel configuration
│   ├── tunnel.py            # L2TPv3 tunnel operations
│   ├── forward.py           # Port forward interface
│   ├── haproxy_manager.py   # HAProxy configuration manager
│   ├── forward_daemon.py    # Background forwarding daemon
│   └── ui.py                # Rich TUI interface
├── systemd/
│   ├── vortexl2-tunnel.service         # Tunnel boot service
│   └── vortexl2-forward-daemon.service # HAProxy forward daemon
├── install.sh               # Installation script
├── requirements.txt         # Python dependencies
└── README.md                # This file
```

## ⚠️ Security Notice

**L2TPv3 provides NO encryption!**

The tunnel transports raw Ethernet frames over IP without any encryption. This is suitable for:
- ✅ Bypassing network restrictions
- ✅ Creating L2 connectivity
- ❌ NOT secure for sensitive data in transit

For encrypted traffic, consider:
- Adding IPsec on top of L2TPv3
- Using WireGuard as an alternative
- Encrypting application-level traffic (TLS/HTTPS)

## 🔄 Uninstall

```bash
# Stop services
sudo systemctl stop vortexl2-tunnel vortexl2-forward-daemon haproxy
sudo systemctl disable vortexl2-tunnel vortexl2-forward-daemon

# Remove files
sudo rm -rf /opt/vortexl2
sudo rm /usr/local/bin/vortexl2
sudo rm /etc/systemd/system/vortexl2-*
sudo rm -rf /etc/vortexl2
sudo rm -rf /var/lib/vortexl2
sudo rm -rf /var/log/vortexl2

# Restore original HAProxy config if needed
sudo cp /etc/haproxy/haproxy.cfg.bak /etc/haproxy/haproxy.cfg

# Reload systemd
sudo systemctl daemon-reload
```

## 📄 License

MIT License

## 👤 Author

Telegram: @iliyadevsh