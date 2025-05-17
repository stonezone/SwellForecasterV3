"""
OPC (Ocean Prediction Center) Agent for SwellForecasterV3.

This agent collects marine forecast data from NOAA's Ocean Prediction Center,
including Pacific marine forecasts and weather charts.
"""

import asyncio
import aiohttp
import json
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
from logging_config import get_logger

logger = get_logger(__name__)


class OPCAgent:
    """Agent for collecting OPC marine forecast data"""
    
    def __init__(self, config):
        """Initialize the OPC agent"""
        self.config = config
        self.base_url = "https://ocean.weather.gov"
        self.sources = {
            'pacific_forecast': f"{self.base_url}/text/NFDHSFEP3.html",
            'marine_weather_discussion': f"{self.base_url}/discussion.php",
            'charts': {
                '24h_wind_wave': f"{self.base_url}/WW3/24h_PACIFIC.gif",
                '48h_wind_wave': f"{self.base_url}/WW3/48h_PACIFIC.gif", 
                '72h_wind_wave': f"{self.base_url}/WW3/72h_PACIFIC.gif",
                'surface_analysis': f"{self.base_url}/shtml/PYBA10.gif"
            }
        }
        
    async def fetch_data(self, session: aiohttp.ClientSession) -> Dict[str, Any]:
        """Fetch marine forecast data from OPC"""
        try:
            data = {
                'timestamp': datetime.utcnow().isoformat(),
                'source': 'NOAA_OPC',
                'forecasts': {},
                'charts': {}
            }
            
            # Fetch Pacific marine forecast
            try:
                async with session.get(self.sources['pacific_forecast']) as response:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Extract forecast text
                    pre_tags = soup.find_all('pre')
                    if pre_tags:
                        data['forecasts']['pacific'] = {
                            'text': pre_tags[0].text.strip(),
                            'url': self.sources['pacific_forecast']
                        }
                        
            except Exception as e:
                logger.error(f"Error fetching Pacific forecast: {str(e)}")
                
            # Get chart URLs (these are image files)
            for chart_name, chart_url in self.sources['charts'].items():
                data['charts'][chart_name] = {
                    'url': chart_url,
                    'type': 'image/gif'
                }
                
            return data
            
        except Exception as e:
            logger.error(f"Error in OPC data collection: {str(e)}")
            return {}
    
    async def collect(self, ctx, session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
        """
        Collect OPC marine forecast data.
        
        Args:
            ctx: Context object with save() method
            session: aiohttp client session
            
        Returns:
            List of metadata dictionaries
        """
        metadata_list = []
        
        try:
            # Fetch OPC data
            data = await self.fetch_data(session)
            
            if data:
                # Save collected data using the context save method
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"opc_data_{timestamp}.json"
                
                # Save using the context's save method (this saves to the bundle directory)
                await ctx.save(filename, json.dumps(data, indent=2))
                
                # Create metadata
                metadata = {
                    'source': 'OPC',
                    'type': 'marine_forecast',
                    'filename': filename,
                    'url': self.base_url,
                    'priority': 2,
                    'description': 'NOAA Ocean Prediction Center marine forecasts and charts',
                    'north_facing': True,
                    'south_facing': False
                }
                
                metadata_list.append(metadata)
                logger.info("Successfully collected OPC Pacific data")
            
        except Exception as e:
            logger.error(f"Error in OPC agent collection: {str(e)}")
        
        return metadata_list