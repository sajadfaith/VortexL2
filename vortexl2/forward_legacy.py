"""
VortexL2 Port Forward Management

Uses HAProxy for high-performance production-grade port forwarding.
This module provides compatibility with the existing interface.
"""

from __future__ import annotations
import asyncio
from locale import str

# Import HAProxy manager as the primary implementation
from vortexl2.haproxy_manager import HAProxyManager, ForwardSession
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
from typing import Dict, List, Optional

# For backward compatibility
ForwardManager = HAProxyManager

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
    """Relay data between two connections with optimized buffering."""
    try:
        # Use larger buffer size for better throughput (64KB instead of 4KB)
        BUFFER_SIZE = 65536
        drain_threshold = 262144  # 256KB - drain only when buffer gets large
        pending_bytes = 0
        
        while True:
            data = await asyncio.wait_for(reader.read(BUFFER_SIZE), timeout=60)
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
            pending_bytes += len(data)
            
            # Only drain periodically instead of after every write
            if pending_bytes >= drain_threshold:
                await writer.drain()
                pending_bytes = 0
        
        # Final drain to ensure all data is sent
        if pending_bytes > 0:
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
        "stats": self.stats
    }