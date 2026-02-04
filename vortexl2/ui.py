"""
VortexL2 Terminal User Interface

Rich-based TUI with ASCII banner and menu system.
"""

import os
import sys
from typing import Optional, List

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.prompt import Prompt, Confirm
    from rich import box
except ImportError:
    print("Error: 'rich' library is required. Install with: pip install rich")
    sys.exit(1)

from . import __version__
from .config import TunnelConfig, ConfigManager


console = Console()


ASCII_BANNER = r"""
 __      __        _            _     ___  
 \ \    / /       | |          | |   |__ \ 
  \ \  / /__  _ __| |_ _____  _| |      ) |
   \ \/ / _ \| '__| __/ _ \ \/ / |     / / 
    \  / (_) | |  | ||  __/>  <| |____/ /_ 
     \/ \___/|_|   \__\___/_/\_\______|____|
"""


def clear_screen():
    """Clear terminal screen."""
    os.system('clear' if os.name != 'nt' else 'cls')


def show_banner():
    """Display the ASCII banner with developer info."""
    clear_screen()
    
    banner_text = Text(ASCII_BANNER, style="bold cyan")
    
    # Print banner
    console.print(banner_text)
    
    # Developer info bar
    console.print(Panel(
        f"[bold white]Telegram:[/] [cyan]@iliyadevsh[/]  |  [bold white]Version:[/] [red]{__version__}[/]  |  [bold white]GitHub:[/] [cyan]github.com/iliya-Developer[/]",
        title="[bold white]VortexL2 - L2TPv3 Tunnel Manager[/]",
        border_style="cyan",
        box=box.ROUNDED
    ))
    console.print()


def show_main_menu() -> str:
    """Display main menu and get user choice."""
    menu_items = [
        ("1", "Install/Verify Prerequisites"),
        ("2", "Create Tunnel"),
        ("3", "Delete Tunnel"),
        ("4", "List Tunnels"),
        ("5", "Port Forwards"),
        ("6", "View Logs"),
        ("0", "Exit"),
    ]
    
    table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    table.add_column("Option", style="bold cyan", width=4)
    table.add_column("Description", style="white")
    
    for opt, desc in menu_items:
        table.add_row(f"[{opt}]", desc)
    
    console.print(Panel(table, title="[bold white]Main Menu[/]", border_style="blue"))
    
    return Prompt.ask("\n[bold cyan]Select option[/]", default="0")


def show_forwards_menu() -> str:
    """Display forwards submenu."""
    menu_items = [
        ("1", "Add Port Forwards"),
        ("2", "Remove Port Forwards"),
        ("3", "List Port Forwards"),
        ("4", "Restart All Forwards"),
        ("5", "Stop All Forwards"),
        ("6", "Start All Forwards"),
        ("0", "Back to Main Menu"),
    ]
    
    table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    table.add_column("Option", style="bold cyan", width=4)
    table.add_column("Description", style="white")
    
    for opt, desc in menu_items:
        table.add_row(f"[{opt}]", desc)
    
    console.print(Panel(table, title="[bold white]Port Forwards[/]", border_style="green"))
    
    return Prompt.ask("\n[bold cyan]Select option[/]", default="0")


def show_tunnel_list(manager: ConfigManager):
    """Display list of all configured tunnels with status."""
    from .tunnel import TunnelManager
    
    tunnels = manager.get_all_tunnels()
    
    if not tunnels:
        console.print("[yellow]No tunnels configured.[/]")
        return
    
    table = Table(title="Configured Tunnels", box=box.ROUNDED)
    table.add_column("#", style="dim", width=3)
    table.add_column("Name", style="magenta")
    table.add_column("Local IP", style="green")
    table.add_column("Remote IP", style="cyan")
    table.add_column("Interface", style="yellow")
    table.add_column("Tunnel ID", style="white")
    table.add_column("Status", style="white")
    
    for i, config in enumerate(tunnels, 1):
        tunnel_mgr = TunnelManager(config)
        is_running = tunnel_mgr.check_tunnel_exists()
        status = "[green]Running[/]" if is_running else "[red]Stopped[/]"
        
        table.add_row(
            str(i),
            config.name,
            config.local_ip or "-",
            config.remote_ip or "-",
            config.interface_name,
            str(config.tunnel_id),
            status
        )
    
    console.print(table)


def prompt_tunnel_name() -> Optional[str]:
    """Prompt for new tunnel name."""
    console.print("\n[dim]Enter a unique name for the tunnel (alphanumeric and dashes only)[/]")
    name = Prompt.ask("[bold magenta]Tunnel Name[/]", default="tunnel1")
    
    # Sanitize name
    name = "".join(c if c.isalnum() or c == "-" else "-" for c in name.lower())
    return name if name else None


def prompt_select_tunnel(manager: ConfigManager) -> Optional[str]:
    """Prompt user to select a tunnel from list."""
    tunnels = manager.list_tunnels()
    
    if not tunnels:
        console.print("[yellow]No tunnels available.[/]")
        return None
    
    console.print("\n[bold white]Available Tunnels:[/]")
    for i, name in enumerate(tunnels, 1):
        console.print(f"  [bold cyan][{i}][/] {name}")
    console.print(f"  [bold cyan][0][/] Cancel")
    
    choice = Prompt.ask("\n[bold cyan]Select tunnel[/]", default="0")
    
    try:
        idx = int(choice)
        if idx == 0:
            return None
        if 1 <= idx <= len(tunnels):
            return tunnels[idx - 1]
    except ValueError:
        # Maybe they typed the name directly
        if choice in tunnels:
            return choice
    
    console.print("[red]Invalid selection[/]")
    return None


def prompt_tunnel_side() -> Optional[str]:
    """Prompt for tunnel side (Iran or Kharej)."""
    console.print("\n[bold white]Select Server Side:[/]")
    console.print("  [bold cyan][1][/] [green]IRAN[/] (receives connections, port forwarding)")
    console.print("  [bold cyan][2][/] [magenta]KHAREJ[/] (remote endpoint)")
    console.print("  [bold cyan][0][/] Cancel")
    
    choice = Prompt.ask("\n[bold cyan]Select side[/]", default="1")
    
    if choice == "1":
        return "IRAN"
    elif choice == "2":
        return "KHAREJ"
    else:
        return None


def prompt_tunnel_config(config: TunnelConfig, side: str) -> bool:
    """Prompt user for tunnel configuration based on side."""
    console.print(f"\n[bold white]Configure Tunnel: {config.name}[/]")
    console.print(f"[bold]Side: [{'green' if side == 'IRAN' else 'magenta'}]{side}[/][/]")
    console.print("[dim]Enter configuration values. Press Enter to use defaults.[/]\n")
    
    # Set defaults based on side
    if side == "IRAN":
        default_interface_ip = "10.30.30.1/24"
        default_remote_forward = "10.30.30.2"
        default_tunnel_id = 1000
        default_peer_tunnel_id = 2000
        default_session_id = 10
        default_peer_session_id = 20
    else:  # KHAREJ
        default_interface_ip = "10.30.30.2/24"
        default_remote_forward = "10.30.30.1"
        default_tunnel_id = 2000
        default_peer_tunnel_id = 1000
        default_session_id = 20
        default_peer_session_id = 10
    
    # Local IP
    default_local = config.local_ip or ""
    local_ip = Prompt.ask(
        "[bold green]Local Server Public IP[/] (this server)",
        default=default_local if default_local else None
    )
    if not local_ip:
        console.print("[red]Local IP is required[/]")
        return False
    config.local_ip = local_ip
    
    # Remote IP
    default_remote = config.remote_ip or ""
    if side == "IRAN":
        remote_label = "[bold cyan]Kharej Server Public IP[/]"
    else:
        remote_label = "[bold cyan]Iran Server Public IP[/]"
    
    remote_ip = Prompt.ask(
        remote_label,
        default=default_remote if default_remote else None
    )
    if not remote_ip:
        console.print("[red]Remote IP is required[/]")
        return False
    config.remote_ip = remote_ip
    
    # Interface IP
    console.print(f"\n[dim]Configure tunnel interface IP (for {config.interface_name})[/]")
    interface_ip = Prompt.ask(
        "[bold yellow]Interface IP (CIDR)[/]",
        default=default_interface_ip
    )
    config.interface_ip = interface_ip
    
    # Remote forward target IP (only relevant for Iran)
    if side == "IRAN":
        remote_forward = Prompt.ask(
            "[bold yellow]Remote Forward Target IP[/]",
            default=default_remote_forward
        )
        config.remote_forward_ip = remote_forward
    else:
        config.remote_forward_ip = default_remote_forward
    
    # Tunnel IDs
    console.print("\n[dim]Configure L2TPv3 tunnel IDs (press Enter to use defaults)[/]")
    
    # Tunnel ID
    tunnel_id_input = Prompt.ask(
        "[bold yellow]Tunnel ID[/]",
        default=str(default_tunnel_id)
    )
    config.tunnel_id = int(tunnel_id_input)
    
    # Peer Tunnel ID
    peer_tunnel_id_input = Prompt.ask(
        "[bold yellow]Peer Tunnel ID[/]",
        default=str(default_peer_tunnel_id)
    )
    config.peer_tunnel_id = int(peer_tunnel_id_input)
    
    # Session ID
    session_id_input = Prompt.ask(
        "[bold yellow]Session ID[/]",
        default=str(default_session_id)
    )
    config.session_id = int(session_id_input)
    
    # Peer Session ID
    peer_session_id_input = Prompt.ask(
        "[bold yellow]Peer Session ID[/]",
        default=str(default_peer_session_id)
    )
    config.peer_session_id = int(peer_session_id_input)
    
    console.print("\n[green]✓ Configuration saved![/]")
    return True


def prompt_ports() -> str:
    """Prompt user for ports to forward."""
    console.print("\n[dim]Enter ports as comma-separated list (e.g., 443,80,2053)[/]")
    return Prompt.ask("[bold cyan]Ports[/]")


def prompt_select_tunnel_for_forwards(manager: ConfigManager) -> Optional[TunnelConfig]:
    """Prompt to select a tunnel for port forwarding."""
    tunnels = manager.get_all_tunnels()
    
    if not tunnels:
        console.print("[yellow]No tunnels available. Create one first.[/]")
        return None
    
    if len(tunnels) == 1:
        return tunnels[0]
    
    console.print("\n[bold white]Select tunnel for port forwards:[/]")
    for i, tunnel in enumerate(tunnels, 1):
        console.print(f"  [bold cyan][{i}][/] {tunnel.name}")
    console.print(f"  [bold cyan][0][/] Cancel")
    
    choice = Prompt.ask("\n[bold cyan]Select tunnel[/]", default="1")
    
    try:
        idx = int(choice)
        if idx == 0:
            return None
        if 1 <= idx <= len(tunnels):
            return tunnels[idx - 1]
    except ValueError:
        pass
    
    console.print("[red]Invalid selection[/]")
    return None


def show_success(message: str):
    """Display success message."""
    console.print(f"\n[bold green]✓[/] {message}")


def show_error(message: str):
    """Display error message."""
    console.print(f"\n[bold red]✗[/] {message}")


def show_warning(message: str):
    """Display warning message."""
    console.print(f"\n[bold yellow]![/] {message}")


def show_info(message: str):
    """Display info message."""
    console.print(f"\n[bold cyan]ℹ[/] {message}")


def show_forwards_list(forwards: list):
    """Display port forwards in a table."""
    if not forwards:
        console.print("[yellow]No port forwards configured[/]")
        return
    
    table = Table(title="Port Forwards", box=box.ROUNDED)
    table.add_column("Port", style="cyan", justify="right")
    table.add_column("Remote Target", style="white")
    table.add_column("Status", style="white")
    table.add_column("Enabled", style="white")
    
    for fwd in forwards:
        status_style = "green" if fwd["status"] == "active" else "red"
        enabled_style = "green" if fwd["enabled"] == "enabled" else "yellow"
        
        table.add_row(
            str(fwd["port"]),
            fwd["remote"],
            f"[{status_style}]{fwd['status']}[/]",
            f"[{enabled_style}]{fwd['enabled']}[/]"
        )
    
    console.print(table)


def show_output(output: str, title: str = "Output"):
    """Display command output in a panel."""
    console.print(Panel(output, title=title, border_style="dim"))


def wait_for_enter():
    """Wait for user to press Enter."""
    console.print()
    Prompt.ask("[dim]Press Enter to continue[/]", default="")


def confirm(message: str, default: bool = False) -> bool:
    """Ask for confirmation."""
    return Confirm.ask(message, default=default)
