"""
Model Agent for SwellForecaster V3.

Collects wave model data for Hawaii surf forecasting.
"""

import aiohttp
import os
import json
from typing import List, Dict, Any
from logging_config import get_logger

logger = get_logger(__name__)


class ModelAgent:
    """
    Collects wave model data from various sources.
    """
    
    def __init__(self, config):
        """
        Initialize the ModelAgent.
        
        Args:
            config: Configuration object
        """
        self.config = config
        
    async def collect(self, ctx, session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
        """
        Collect wave model data for Hawaii.
        
        Args:
            ctx: Context object with save() method
            session: aiohttp client session
            
        Returns:
            List of metadata dictionaries
        """
        metadata_list = []
        
        # Wave model data sources
        sources = [
            # NOAA WaveWatch III model
            {
                'url': 'https://nomads.ncep.noaa.gov/cgi-bin/filter_gfswave.pl?file=gfswave.t00z.global.0p16.f000.grib2&lev_surface=on&var_DIRPW=on&var_PERPW=on&var_HTSGW=on&subregion=&leftlon=190&rightlon=210&toplat=30&bottomlat=15&dir=%2Fgfs',
                'name': 'wavewatch3_hawaii',
                'type': 'wavewatch3',
                'description': 'WaveWatch III model - Hawaii region'
            },
            # PacIOOS Wave Model
            {
                'url': 'https://www.pacioos.hawaii.edu/waves/model-hawaii/',
                'name': 'pacioos_hawaii',
                'type': 'pacioos_model',
                'description': 'PacIOOS Hawaii regional wave model',
                'parse_type': 'html'
            },
            # NOAA GFS Wave for North Pacific
            {
                'url': 'https://www.ncei.noaa.gov/data/global-forecast-system/access/grid-004-0.5-degree/analysis/ocean/latest/',
                'name': 'gfs_wave_pacific',
                'type': 'gfs_wave',
                'description': 'GFS Wave model - North Pacific'
            }
        ]
        
        # Attempt to add additional model sources if API keys are available
        if self.config.has_option('api_keys', 'stormglass_key'):
            sources.append({
                'url': 'https://api.stormglass.io/v2/weather/point',
                'name': 'stormglass_hawaii',
                'type': 'stormglass',
                'description': 'Stormglass wave model data',
                'params': {
                    'lat': 21.3099,
                    'lng': -157.8581,
                    'params': 'waveHeight,waveDirection,wavePeriod,swellHeight,swellDirection,swellPeriod,windWaveHeight,windWaveDirection,windWavePeriod'
                }
            })
        
        for source in sources:
            try:
                logger.info(f"Fetching model data from {source['name']}")
                headers = {'User-Agent': 'SwellForecasterV3'}
                
                # Add auth headers if needed
                if source['type'] == 'stormglass' and self.config.has_option('api_keys', 'stormglass_key'):
                    headers['Authorization'] = self.config.get('api_keys', 'stormglass_key')
                
                # Prepare request parameters
                kwargs = {'headers': headers}
                if 'params' in source:
                    kwargs['params'] = source['params']
                
                async with session.get(source['url'], **kwargs) as response:
                    content_type = response.headers.get('content-type', '')
                    
                    if 'json' in content_type or source['type'] == 'stormglass':
                        # JSON response
                        data = await response.json()
                        content = self._format_model_json(data, source['type'])
                    else:
                        # Text/HTML response
                        content = await response.text()
                        
                        # For HTML pages, extract relevant information
                        if source.get('parse_type') == 'html':
                            content = self._extract_pacioos_data(content)
                    
                    # Save the data
                    filename = f"model_{source['name']}.txt"
                    await ctx.save(filename, content)
                    
                    # Create metadata
                    metadata = {
                        'source': source['type'].upper(),
                        'type': 'model',
                        'subtype': source['type'],
                        'filename': filename,
                        'name': source['name'],
                        'description': source['description'],
                        'url': source['url'],
                        'priority': 1
                    }
                    
                    # All model data is relevant to both shores
                    metadata['north_facing'] = True
                    metadata['south_facing'] = True
                    
                    metadata_list.append(metadata)
                    logger.info(f"Collected model data from {source['name']}")
                    
            except Exception as e:
                logger.error(f"Error fetching model data from {source['name']}: {e}")
                if hasattr(ctx, 'failure_tracker'):
                    ctx.failure_tracker.log_failure(
                        source=source['type'].upper(),
                        url=source['url'],
                        error=str(e),
                        agent='model'
                    )
        
        return metadata_list
    
    def _format_model_json(self, data: dict, model_type: str) -> str:
        """
        Format model JSON data into readable text.
        
        Args:
            data: JSON data dictionary
            model_type: Type of model for specific formatting
            
        Returns:
            Formatted text
        """
        output = []
        output.append(f"{model_type.upper()} MODEL DATA")
        output.append("=" * 50)
        
        if model_type == 'stormglass':
            if 'hours' in data:
                for hour in data['hours'][:24]:  # Next 24 hours
                    output.append(f"\nTime: {hour.get('time', 'N/A')}")
                    
                    # Wave data
                    if 'waveHeight' in hour:
                        output.append(f"Wave Height: {hour['waveHeight'].get('sg', 'N/A')} m")
                    if 'waveDirection' in hour:
                        output.append(f"Wave Direction: {hour['waveDirection'].get('sg', 'N/A')}°")
                    if 'wavePeriod' in hour:
                        output.append(f"Wave Period: {hour['wavePeriod'].get('sg', 'N/A')} s")
                    
                    # Swell data
                    if 'swellHeight' in hour:
                        output.append(f"Swell Height: {hour['swellHeight'].get('sg', 'N/A')} m")
                    if 'swellDirection' in hour:
                        output.append(f"Swell Direction: {hour['swellDirection'].get('sg', 'N/A')}°")
                    if 'swellPeriod' in hour:
                        output.append(f"Swell Period: {hour['swellPeriod'].get('sg', 'N/A')} s")
                    
                    output.append("-" * 30)
        else:
            # Generic JSON formatting
            output.append(json.dumps(data, indent=2))
        
        return '\n'.join(output)
    
    def _extract_pacioos_data(self, html_content: str) -> str:
        """
        Extract relevant data from PacIOOS HTML page.
        
        Args:
            html_content: HTML content
            
        Returns:
            Extracted text data
        """
        output = []
        output.append("PACIOOS WAVE MODEL DATA")
        output.append("=" * 50)
        
        # Basic extraction - in production you'd use BeautifulSoup or similar
        import re
        
        # Look for wave height data
        height_pattern = r'Wave Height[:\s]+([0-9.]+)\s*(?:ft|m)'
        heights = re.findall(height_pattern, html_content, re.IGNORECASE)
        if heights:
            output.append(f"Wave Heights: {', '.join(heights)}")
        
        # Look for period data
        period_pattern = r'Wave Period[:\s]+([0-9.]+)\s*(?:s|seconds)'
        periods = re.findall(period_pattern, html_content, re.IGNORECASE)
        if periods:
            output.append(f"Wave Periods: {', '.join(periods)}")
        
        # Look for direction data
        dir_pattern = r'Direction[:\s]+([0-9]+)°?\s*(?:deg)?'
        directions = re.findall(dir_pattern, html_content, re.IGNORECASE)
        if directions:
            output.append(f"Wave Directions: {', '.join(directions)}")
        
        # Include raw HTML in case parsing fails
        output.append("\nRAW HTML DATA:")
        output.append("-" * 30)
        # Limit to first 5000 chars to avoid huge outputs
        output.append(html_content[:5000])
        
        return '\n'.join(output)


# Agent function following the standard pattern
async def model_agent(ctx, session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
    """
    Standard agent function for model data collection.
    
    Args:
        ctx: Context object
        session: aiohttp client session
        
    Returns:
        List of metadata dictionaries
    """
    agent = ModelAgent(ctx.cfg)
    return await agent.collect(ctx, session)