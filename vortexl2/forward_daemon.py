#!/usr/bin/env python3
"""
VortexL2 Forward Daemon

Runs the asyncio-based port forwarding servers as a daemon service.
This replaces the individual socat systemd services.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from vortexl2.config import ConfigManager
from vortexl2.forward import ForwardManager


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/vortexl2/forward-daemon.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ForwardDaemon:
    """Manages the forward daemon."""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.forward_managers = {}
        self.running = False
    
    async def start(self):
        """Start the forward daemon."""
        logger.info("Starting VortexL2 Forward Daemon")
        self.running = True
        
        # Get all tunnel configurations
        tunnels = self.config_manager.get_all_tunnels()
        
        if not tunnels:
            logger.warning("No tunnels configured")
            return
        
        # Create forward manager for each tunnel
        tasks = []
        for tunnel_config in tunnels:
            if not tunnel_config.is_configured():
                logger.warning(f"Tunnel '{tunnel_config.name}' not fully configured, skipping")
                continue
            
            if not tunnel_config.forwarded_ports:
                logger.debug(f"Tunnel '{tunnel_config.name}' has no forwarded ports")
                continue
            
            forward_manager = ForwardManager(tunnel_config)
            self.forward_managers[tunnel_config.name] = forward_manager
            
            logger.info(f"Starting forwards for tunnel '{tunnel_config.name}': {tunnel_config.forwarded_ports}")
            await forward_manager.start_all_forwards()
        
        logger.info("Forward Daemon started successfully")
        
        # Keep running
        try:
            while self.running:
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Error in forward daemon: {e}")
    
    async def stop(self):
        """Stop the forward daemon."""
        logger.info("Stopping VortexL2 Forward Daemon")
        self.running = False
        
        # Stop all forward managers
        tasks = []
        for tunnel_name, forward_manager in self.forward_managers.items():
            logger.info(f"Stopping forwards for tunnel '{tunnel_name}'")
            tasks.append(forward_manager.stop_all_forwards())
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info("Forward Daemon stopped")


async def main():
    """Main entry point."""
    daemon = ForwardDaemon()
    
    # Setup signal handlers
    def handle_signal(sig, frame):
        logger.info(f"Received signal {sig}")
        asyncio.create_task(daemon.stop())
    
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    
    try:
        await daemon.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        await daemon.stop()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
