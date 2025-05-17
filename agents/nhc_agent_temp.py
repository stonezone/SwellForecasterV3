"""
NHC (National Hurricane Center) Marine Agent for SwellForecasterV3.

This agent collects marine forecast data from NOAA's National Hurricane Center,
including Eastern Pacific marine forecasts and tropical cyclone information.
"""

import asyncio
import aiohttp
import json
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Dict, List, Any
from logging_config import get_logger

logger = get_logger(__name__)


class NHCAgent:
    """Agent for collecting NHC marine forecast data"""
    
    def __init__(self, config):
        """Initialize the NHC agent"""
        self.config = config
        self.base_url = "https://www.nhc.noaa.gov"
        self.sources = {
            'high_seas_forecast': f"{self.base_url}/text/MIAHSFEP.shtml",
            'offshore_waters': f"{self.base_url}/text/MIAOFFPZ5.shtml",
            'tropical_outlook': f"{self.base_url}/gtwo.php?basin=epac",
            'marine_discussion': f"{self.base_url}/marine",
            'charts': {
                '24h_wind_wave': f"{self.base_url}/tafb_latest/atlpac_wave24",
                '48h_wind_wave': f"{self.base_url}/tafb_latest/atlpac_wave48",
                'surface_analysis': f"{self.base_url}/tafb_latest/PYBA00_latest"
            }
        }
        
    async def fetch_data(self, session: aiohttp.ClientSession) -> Dict[str, Any]:
        """Fetch marine forecast data from NHC"""
        try:
            data = {
                'timestamp': datetime.utcnow().isoformat(),
                'source': 'NOAA_NHC',
                'forecasts': {},
                'charts': {},
                'tropical_systems': []
            }
            
            # Fetch high seas forecast
            try:
                async with session.get(self.sources['high_seas_forecast']) as response:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Extract forecast text
                    pre_tags = soup.find_all('pre')
                    if pre_tags:
                        data['forecasts']['high_seas'] = {
                            'text': pre_tags[0].text.strip(),
                            'url': self.sources['high_seas_forecast']
                        }
                        
            except Exception as e:
                logger.error(f"Error fetching high seas forecast: {str(e)}")
                
            # Fetch offshore waters forecast
            try:
                async with session.get(self.sources['offshore_waters']) as response:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    pre_tags = soup.find_all('pre')
                    if pre_tags:
                        data['forecasts']['offshore_waters'] = {
                            'text': pre_tags[0].text.strip(),
                            'url': self.sources['offshore_waters']
                        }
                        
            except Exception as e:
                logger.error(f"Error fetching offshore waters: {str(e)}")
                
            # Fetch tropical outlook
            try:
                async with session.get(self.sources['tropical_outlook']) as response:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Extract tropical systems if any
                    outlook_div = soup.find('div', {'id': 'gtwoForm'})
                    if outlook_div:
                        data['tropical_systems'] = self._extract_tropical_systems(outlook_div)
                        
            except Exception as e:
                logger.error(f"Error fetching tropical outlook: {str(e)}")
                
            # Get chart URLs
            for chart_name, chart_url in self.sources['charts'].items():
                data['charts'][chart_name] = {
                    'url': chart_url,
                    'type': 'image'
                }
                
            return data
            
        except Exception as e:
            logger.error(f"Error in NHC data collection: {str(e)}")
            return {}
            
    def _extract_tropical_systems(self, soup_div) -> List[Dict[str, Any]]:
        """Extract information about active tropical systems"""
        systems = []
        try:
            # Look for system information in the outlook
            system_divs = soup_div.find_all('div', class_='system')
            for system in system_divs:
                system_info = {
                    'name': '',
                    'status': '',
                    'location': '',
                    'development_chance': ''
                }
                
                # Extract system details (structure varies, so be flexible)
                text = system.text.strip()
                lines = text.split('\n')
                
                for line in lines:
                    if 'Formation chance' in line:
                        system_info['development_chance'] = line
                    elif 'Location' in line:
                        system_info['location'] = line
                        
                if any(system_info.values()):
                    systems.append(system_info)
                    
        except Exception as e:
            logger.error(f"Error extracting tropical systems: {str(e)}")
            
        return systems
    
    async def collect(self, ctx, session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
        """
        Collect NHC marine forecast data.
        
        Args:
            ctx: Context object with save() method
            session: aiohttp client session
            
        Returns:
            List of metadata dictionaries
        """
        metadata_list = []
        
        try:
            # Fetch NHC data
            data = await self.fetch_data(session)
            
            if data:
                # Save collected data
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"nhc_marine_data_{timestamp}.json"
                
                # Save using the context's save method
                await ctx.save(filename, json.dumps(data, indent=2))
                
                # Create metadata
                metadata = {
                    'source': 'NHC',
                    'type': 'marine_forecast',
                    'filename': filename,
                    'url': self.base_url,
                    'priority': 3,
                    'description': 'NHC Eastern Pacific marine forecasts and tropical systems',
                    'north_facing': True,
                    'south_facing': False,
                    'tropical_relevant': True
                }
                
                metadata_list.append(metadata)
                logger.info("Successfully collected NHC marine data")
            
        except Exception as e:
            logger.error(f"Error in NHC agent collection: {str(e)}")
        
        return metadata_list