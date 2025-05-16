"""
Buoy Agent for SwellForecaster V3.

Example agent that collects buoy data from NOAA NDBC.
This demonstrates the pattern for data collection agents.
"""

import aiohttp
import os
from typing import List, Dict, Any
from logging_config import get_logger

logger = get_logger(__name__)


class BuoyAgent:
    """
    Collects buoy data from NOAA NDBC.
    """
    
    def __init__(self, config):
        """
        Initialize the BuoyAgent.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.base_url = "https://www.ndbc.noaa.gov"
        
    async def collect(self, ctx, session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
        """
        Collect buoy data.
        
        Args:
            ctx: Context object with save() method
            session: aiohttp client session
            
        Returns:
            List of metadata dictionaries
        """
        metadata_list = []
        buoy_urls = self.config.get('data_sources', 'buoy_urls').split(',')
        
        for url in buoy_urls:
            url = url.strip()
            try:
                # Extract station ID from URL
                station_id = url.split('station=')[-1] if 'station=' in url else 'unknown'
                
                # Fetch the data
                async with session.get(url) as response:
                    content = await response.text()
                
                # Save the data
                filename = f"buoy_{station_id}.txt"
                await ctx.save(filename, content)
                
                # Create metadata
                metadata = {
                    'source': 'NDBC',
                    'type': 'buoy',
                    'filename': filename,
                    'station_id': station_id,
                    'url': url,
                    'priority': 1
                }
                
                # Add regional tags based on station location
                if station_id.startswith('51'):  # Hawaii buoys
                    metadata['north_facing'] = True
                    metadata['south_facing'] = True
                
                metadata_list.append(metadata)
                logger.info(f"Collected buoy data from {station_id}")
                
            except Exception as e:
                logger.error(f"Error fetching buoy data from {url}: {e}")
                # Track failure if context has failure tracker
                if hasattr(ctx, 'failure_tracker'):
                    ctx.failure_tracker.log_failure(
                        source='NDBC',
                        url=url,
                        error=str(e),
                        agent='buoy'
                    )
        
        return metadata_list


# Agent function following the standard pattern
async def buoy_agent(ctx, session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
    """
    Standard agent function for buoy data collection.
    
    Args:
        ctx: Context object
        session: aiohttp client session
        
    Returns:
        List of metadata dictionaries
    """
    agent = BuoyAgent(ctx.cfg)
    return await agent.collect(ctx, session)