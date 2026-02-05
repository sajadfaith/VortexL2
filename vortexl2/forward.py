"""
VortexL2 Port Forward Management

Handles asyncio-based TCP port forwarding with better reliability and control.
Uses pure Python async I/O instead of socat for better error handling and logging.
"""

from __future__ import annotations

import asyncio
import logging
import json
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime


# Setup logging
logger = logging.getLogger(__name__)

# Storage for forward servers
FORWARDS_STATE_FILE = Path("/var/lib/vortexl2/forwards.json")
FORWARDS_LOG_DIR = Path("/var/log/vortexl2")


@dataclass
class ForwardSession:
    """Represents an active port forwarding session."""
    port: int
    remote_ip: str
    remote_port: int
    local_reader: Optional[asyncio.StreamReader] = None
    local_writer: Optional[asyncio.StreamWriter] = None
    remote_reader: Optional[asyncio.StreamReader] = None
    remote_writer: Optional[asyncio.StreamWriter] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    bytes_sent: int = 0
    bytes_received: int = 0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON storage."""
        return {
            "port": self.port,
            "remote_ip": self.remote_ip,
            "remote_port": self.remote_port,
            "created_at": self.created_at,
            "bytes_sent": self.bytes_sent,
            "bytes_received": self.bytes_received,
        }


class ForwardServer:
    """Manages a single port forward server using asyncio."""
    
    def __init__(self, port: int, remote_ip: str, remote_port: int = None):
        """
        Initialize forward server.
        
        Args:
            port: Local port to listen on
            remote_ip: Remote IP to forward to
            remote_port: Remote port (defaults to same as local port)
        """
        self.port = port
        self.remote_ip = remote_ip
        self.remote_port = remote_port or port
        self.server: Optional[asyncio.Server] = None
        self.active_sessions: List[ForwardSession] = []
        self.running = False
        self.stats = {
            "connections": 0,
            "total_bytes_sent": 0,
            "total_bytes_received": 0,
            "errors": 0,
        }
    
    async def handle_client(self, local_reader: asyncio.StreamReader, 
                          local_writer: asyncio.StreamWriter):
        """Handle incoming client connection."""
        client_addr = local_writer.get_extra_info('peername')
        session = ForwardSession(
            port=self.port,
            remote_ip=self.remote_ip,
            remote_port=self.remote_port
        )
        self.active_sessions.append(session)
        self.stats["connections"] += 1
        
        try:
            logger.info(f"Client connected from {client_addr} on port {self.port}")
            
            # Connect to remote server
            try:
                remote_reader, remote_writer = await asyncio.wait_for(
                    asyncio.open_connection(self.remote_ip, self.remote_port),
                    timeout=10
                )
            except asyncio.TimeoutError:
                logger.error(f"Timeout connecting to {self.remote_ip}:{self.remote_port}")
                local_writer.close()
                await local_writer.wait_closed()
                self.stats["errors"] += 1
                return
            except Exception as e:
                logger.error(f"Failed to connect to {self.remote_ip}:{self.remote_port}: {e}")
                local_writer.close()
                await local_writer.wait_closed()
                self.stats["errors"] += 1
                return
            
            # Relay data in both directions
            forward_task = asyncio.create_task(
                self._relay_data(local_reader, remote_writer, session, "client->remote")
            )
            backward_task = asyncio.create_task(
                self._relay_data(remote_reader, local_writer, session, "remote->client")
            )
            
            # Wait for both tasks to complete
            await asyncio.gather(forward_task, backward_task)
            
        except Exception as e:
            logger.error(f"Error handling client {client_addr}: {e}")
            self.stats["errors"] += 1
        finally:
            # Cleanup
            if local_writer:
                local_writer.close()
                await local_writer.wait_closed()
            self.active_sessions.remove(session)
            logger.info(f"Client {client_addr} disconnected from port {self.port}")
    
    async def _relay_data(self, reader: asyncio.StreamReader, 
                         writer: asyncio.StreamWriter,
                         session: ForwardSession,
                         direction: str):
        """Relay data between two connections."""
        try:
            while True:
                data = await asyncio.wait_for(reader.read(4096), timeout=300)
                if not data:
                    break
                
                # Update statistics
                if "client->remote" in direction:
                    session.bytes_sent += len(data)
                    self.stats["total_bytes_sent"] += len(data)
                else:
                    session.bytes_received += len(data)
                    self.stats["total_bytes_received"] += len(data)
                
                writer.write(data)
                await writer.drain()
        except asyncio.TimeoutError:
            logger.debug(f"Timeout on {direction}")
        except Exception as e:
            logger.debug(f"Error relaying {direction}: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
    
    async def start(self) -> bool:
        """Start the forward server."""
        try:
            self.server = await asyncio.start_server(
                self.handle_client,
                '0.0.0.0',
                self.port,
                reuse_address=True
            )
            self.running = True
            logger.info(f"Forward server started on port {self.port} -> {self.remote_ip}:{self.remote_port}")
            
            # Start serving
            async with self.server:
                await self.server.serve_forever()
        except OSError as e:
            logger.error(f"Failed to start server on port {self.port}: {e}")
            self.running = False
            return False
        except Exception as e:
            logger.error(f"Server error on port {self.port}: {e}")
            self.running = False
            return False
    
    async def stop(self):
        """Stop the forward server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        self.running = False
        logger.info(f"Forward server stopped on port {self.port}")
    
    def get_status(self) -> Dict:
        """Get server status."""
        return {
            "port": self.port,
            "remote": f"{self.remote_ip}:{self.remote_port}",
            "running": self.running,
            "active_sessions": len(self.active_sessions),
            "stats": self.stats,
        }


class ForwardManager:
    """Manages all port forwarding servers."""
    
    def __init__(self, config):
        self.config = config
        self.servers: Dict[int, ForwardServer] = {}
        self.event_loop: Optional[asyncio.AbstractEventLoop] = None
        self.running_task: Optional[asyncio.Task] = None
        
        # Ensure log directory exists
        FORWARDS_LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    def create_forward(self, port: int) -> Tuple[bool, str]:
        """Create a port forward."""
        remote_ip = self.config.remote_forward_ip
        if not remote_ip:
            return False, "Remote forward IP not configured"
        
        if port in self.servers:
            return False, f"Port {port} already forwarding"
        
        # Create forward server
        server = ForwardServer(port, remote_ip, remote_port=port)
        self.servers[port] = server
        
        # Add to config
        self.config.add_port(port)
        
        return True, f"Port forward for {port} created (-> {remote_ip}:{port})"
    
    def remove_forward(self, port: int) -> Tuple[bool, str]:
        """Remove a port forward."""
        if port not in self.servers:
            return False, f"Port {port} not found"
        
        # Server will be stopped when ForwardManager stops or specifically removed
        del self.servers[port]
        self.config.remove_port(port)
        
        return True, f"Port forward for {port} removed"
    
    def add_multiple_forwards(self, ports_str: str) -> Tuple[bool, str]:
        """Add multiple port forwards from comma-separated string."""
        results = []
        ports = [p.strip() for p in ports_str.split(',') if p.strip()]
        
        for port_str in ports:
            try:
                port = int(port_str)
                success, msg = self.create_forward(port)
                results.append(f"Port {port}: {msg}")
            except ValueError:
                results.append(f"Port '{port_str}': Invalid port number")
        
        return True, "\n".join(results)
    
    def remove_multiple_forwards(self, ports_str: str) -> Tuple[bool, str]:
        """Remove multiple port forwards from comma-separated string."""
        results = []
        ports = [p.strip() for p in ports_str.split(',') if p.strip()]
        
        for port_str in ports:
            try:
                port = int(port_str)
                success, msg = self.remove_forward(port)
                results.append(f"Port {port}: {msg}")
            except ValueError:
                results.append(f"Port '{port_str}': Invalid port number")
        
        return True, "\n".join(results)
    
    def list_forwards(self) -> List[Dict]:
        """List all configured port forwards with their status."""
        forwards = []
        
        for port in self.config.forwarded_ports:
            if port in self.servers:
                server = self.servers[port]
                forwards.append(server.get_status())
            else:
                forwards.append({
                    "port": port,
                    "remote": f"{self.config.remote_forward_ip}:{port}",
                    "running": False,
                    "active_sessions": 0,
                })
        
        return forwards
    
    async def start_all_forwards(self) -> Tuple[bool, str]:
        """Start all configured port forwards asynchronously."""
        results = []
        tasks = []
        
        for port in self.config.forwarded_ports:
            remote_ip = self.config.remote_forward_ip
            
            if port not in self.servers:
                server = ForwardServer(port, remote_ip, remote_port=port)
                self.servers[port] = server
            else:
                server = self.servers[port]
            
            if not server.running:
                task = asyncio.create_task(server.start())
                tasks.append((port, task))
                results.append(f"Port {port}: starting...")
        
        if not results:
            return True, "No port forwards configured"
        
        return True, "\n".join(results)
    
    async def stop_all_forwards(self) -> Tuple[bool, str]:
        """Stop all configured port forwards asynchronously."""
        results = []
        tasks = []
        
        for port, server in self.servers.items():
            if server.running:
                task = asyncio.create_task(server.stop())
                tasks.append((port, task))
                results.append(f"Port {port}: stopping...")
        
        # Wait for all tasks
        if tasks:
            await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
        
        if not results:
            return True, "No port forwards running"
        
        return True, "\n".join(results)
    
    async def restart_all_forwards(self) -> Tuple[bool, str]:
        """Restart all configured port forwards."""
        await self.stop_all_forwards()
        await asyncio.sleep(1)  # Brief pause between stop and start
        return await self.start_all_forwards()
    
    def start_in_background(self) -> bool:
        """Start all forwards in a background event loop."""
        try:
            import threading
            
            def run_loop():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                self.event_loop = loop
                
                async def run_servers():
                    await self.start_all_forwards()
                    # Keep running
                    while True:
                        await asyncio.sleep(1)
                
                loop.run_until_complete(run_servers())
            
            thread = threading.Thread(target=run_loop, daemon=True)
            thread.start()
            return True
        except Exception as e:
            logger.error(f"Failed to start background forwards: {e}")
            return False
