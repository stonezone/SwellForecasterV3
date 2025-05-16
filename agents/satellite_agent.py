"""
Satellite Agent for SwellForecaster V3.

Collects satellite imagery and data for Hawaii surf forecasting.
"""

import aiohttp
import os
import json
from typing import List, Dict, Any
from logging_config import get_logger

logger = get_logger(__name__)


class SatelliteAgent:
    """
    Collects satellite imagery and data from various sources.
    """
    
    def __init__(self, config):
        """
        Initialize the SatelliteAgent.
        
        Args:
            config: Configuration object
        """
        self.config = config
        
    async def collect(self, ctx, session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
        """
        Collect satellite data for Hawaii and Pacific.
        
        Args:
            ctx: Context object with save() method
            session: aiohttp client session
            
        Returns:
            List of metadata dictionaries
        """
        metadata_list = []
        
        # Satellite data sources
        sources = [
            # GOES-West Pacific View
            {
                'url': 'https://www.star.nesdis.noaa.gov/goes/sector.php?sat=G18&sector=cep',
                'name': 'goes_west_pacific',
                'type': 'goes_imagery',
                'description': 'GOES-18 Central Pacific satellite imagery'
            },
            # GOES-West Hawaii Regional
            {
                'url': 'https://www.star.nesdis.noaa.gov/goes/sector.php?sat=G18&sector=hi',
                'name': 'goes_west_hawaii',
                'type': 'goes_imagery',
                'description': 'GOES-18 Hawaii regional satellite imagery'
            },
            # NHC Satellite Imagery
            {
                'url': 'https://www.nhc.noaa.gov/satellite.php',
                'name': 'nhc_satellite',
                'type': 'nhc_imagery',
                'description': 'National Hurricane Center satellite products'
            },
            # CIMSS Tropical Cyclone Data
            {
                'url': 'https://tropic.ssec.wisc.edu/real-time/mtpw2/product.php?color_type=tpw_nrl_colors&prod=global2&area=pacific',
                'name': 'cimss_tpw_pacific',
                'type': 'cimss_moisture',
                'description': 'Total Precipitable Water - Pacific'
            },
            # Navy NRL Monterey Satellite
            {
                'url': 'https://www.nrlmry.navy.mil/TC-bin/tc_home2.cgi?YEAR=&amp;MO=&amp;BASIN=WPAC&amp;STORM_NAME=&amp;ARCHIVE=active&amp;ACTIVES=active',
                'name': 'nrl_monterey',
                'type': 'nrl_tropical',
                'description': 'Naval Research Lab tropical monitoring'
            }
        ]
        
        # Additional sources if Windy API key is available
        if self.config.has_option('api_keys', 'windy_key'):
            sources.append({
                'url': 'https://api.windy.com/api/webcams/v2/list/limit=10/bbox=18.91619,-160.5481,22.2356,-154.8067',
                'name': 'windy_webcams_hawaii',
                'type': 'windy_webcams',
                'description': 'Hawaii area webcams from Windy',
                'auth_header': 'x-windy-key'
            })
        
        for source in sources:
            try:
                logger.info(f"Fetching satellite data from {source['name']}")
                headers = {'User-Agent': 'SwellForecasterV3'}
                
                # Add authentication if needed
                if source.get('auth_header') == 'x-windy-key':
                    headers['x-windy-key'] = self.config.get('api_keys', 'windy_key')
                
                async with session.get(source['url'], headers=headers) as response:
                    content_type = response.headers.get('content-type', '')
                    
                    if 'json' in content_type:
                        # JSON response
                        data = await response.json()
                        content = self._format_satellite_json(data, source['type'])
                    else:
                        # Text/HTML response
                        content = await response.text()
                        
                        # Extract relevant information from HTML
                        if source['type'] in ['goes_imagery', 'nhc_imagery', 'cimss_moisture']:
                            content = self._extract_imagery_links(content, source['type'])
                    
                    # Save the data
                    filename = f"satellite_{source['name']}.txt"
                    await ctx.save(filename, content)
                    
                    # Create metadata
                    metadata = {
                        'source': source['type'].upper(),
                        'type': 'satellite',
                        'subtype': source['type'],
                        'filename': filename,
                        'name': source['name'],
                        'description': source['description'],
                        'url': source['url'],
                        'priority': 3
                    }
                    
                    # All satellite data is relevant to both shores
                    metadata['north_facing'] = True
                    metadata['south_facing'] = True
                    
                    metadata_list.append(metadata)
                    logger.info(f"Collected satellite data from {source['name']}")
                    
            except Exception as e:
                logger.error(f"Error fetching satellite data from {source['name']}: {e}")
                if hasattr(ctx, 'failure_tracker'):
                    ctx.failure_tracker.log_failure(
                        source=source['type'].upper(),
                        url=source['url'],
                        error=str(e),
                        agent='satellite'
                    )
        
        return metadata_list
    
    def _format_satellite_json(self, data: dict, sat_type: str) -> str:
        """
        Format satellite JSON data into readable text.
        
        Args:
            data: JSON data dictionary
            sat_type: Type of satellite data
            
        Returns:
            Formatted text
        """
        output = []
        output.append(f"{sat_type.upper()} SATELLITE DATA")
        output.append("=" * 50)
        
        if sat_type == 'windy_webcams':
            if 'result' in data and 'webcams' in data['result']:
                for webcam in data['result']['webcams']:
                    output.append(f"\nWebcam: {webcam.get('title', 'Unknown')}")
                    output.append(f"Location: {webcam.get('location', {}).get('city', 'N/A')}")
                    output.append(f"Status: {webcam.get('status', 'N/A')}")
                    if 'lastImageUrl' in webcam:
                        output.append(f"Last Image: {webcam['lastImageUrl']}")
                    output.append("-" * 30)
        else:
            # Generic JSON formatting
            output.append(json.dumps(data, indent=2))
        
        return '\n'.join(output)
    
    def _extract_imagery_links(self, html_content: str, img_type: str) -> str:
        """
        Extract satellite imagery links and information from HTML.
        
        Args:
            html_content: HTML content
            img_type: Type of imagery
            
        Returns:
            Extracted information
        """
        output = []
        output.append(f"{img_type.upper()} SATELLITE IMAGERY")
        output.append("=" * 50)
        
        import re
        
        # Extract image links
        img_pattern = r'<img[^>]+src="([^"]+(?:\.jpg|\.png|\.gif)[^"]*)"[^>]*>'
        images = re.findall(img_pattern, html_content, re.IGNORECASE)
        
        if images:
            output.append("\nIMAGE LINKS:")
            for i, img in enumerate(images[:10], 1):  # Limit to first 10 images
                # Clean up relative URLs
                if img.startswith('/'):
                    if 'goes' in img_type:
                        img = f"https://www.star.nesdis.noaa.gov{img}"
                    elif 'nhc' in img_type:
                        img = f"https://www.nhc.noaa.gov{img}"
                output.append(f"{i}. {img}")
        
        # Look for text descriptions
        text_pattern = r'<(?:p|div|span)[^>]*>([^<]+Pacific[^<]+)</(?:p|div|span)>'
        texts = re.findall(text_pattern, html_content, re.IGNORECASE)
        
        if texts:
            output.append("\nDESCRIPTIONS:")
            for text in texts[:5]:  # Limit to first 5 descriptions
                output.append(f"- {text.strip()}")
        
        # Look for time stamps
        time_pattern = r'(?:Updated|Valid|Time)[:\s]+([0-9]{2,4}[^\n<]+)'
        times = re.findall(time_pattern, html_content, re.IGNORECASE)
        
        if times:
            output.append("\nTIMESTAMPS:")
            for time in times[:3]:
                output.append(f"- {time.strip()}")
        
        return '\n'.join(output)


# Agent function following the standard pattern
async def satellite_agent(ctx, session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
    """
    Standard agent function for satellite data collection.
    
    Args:
        ctx: Context object
        session: aiohttp client session
        
    Returns:
        List of metadata dictionaries
    """
    agent = SatelliteAgent(ctx.cfg)
    return await agent.collect(ctx, session)