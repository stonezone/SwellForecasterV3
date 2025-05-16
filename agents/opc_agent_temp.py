"""Ocean Prediction Center (OPC) data collection agent"""
import asyncio
import aiohttp
import logging
from typing import Dict, List, Any
from datetime import datetime
from bs4 import BeautifulSoup

import json
from pathlib import Path

logger = logging.getLogger(__name__)

class OPCAgent:
    """Agent for collecting Ocean Prediction Center Pacific marine forecasts and charts"""
    
    def __init__(self):
        self.base_url = "https://ocean.weather.gov/Pac_tab.php"
        
    async def fetch_data(self, session: aiohttp.ClientSession) -> Dict[str, Any]:
        """Fetch all OPC Pacific data including charts and forecasts"""
        data = {
            "source": "NOAA Ocean Prediction Center",
            "collected_at": datetime.now().isoformat(),
            "forecasts": {},
            "charts": {},
            "analyses": {}
        }
        
        try:
            # Fetch main page
            async with session.get(self.base_url) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Extract surface analyses
                    data["charts"]["surface_analysis"] = self._extract_chart_links(soup, "Surface Analysis")
                    
                    # Extract wind/wave forecasts
                    data["charts"]["wind_wave_24hr"] = self._extract_chart_links(soup, "24 Hour")
                    data["charts"]["wind_wave_48hr"] = self._extract_chart_links(soup, "48 Hour")
                    data["charts"]["wind_wave_72hr"] = self._extract_chart_links(soup, "72 Hour")
                    data["charts"]["wind_wave_96hr"] = self._extract_chart_links(soup, "96 Hour")
                    
                    # Extract wave period forecasts
                    data["charts"]["wave_period"] = self._extract_chart_links(soup, "Wave Period")
                    
                    # Extract text forecasts
                    data["forecasts"]["high_seas"] = await self._fetch_text_forecast(session, "high seas")
                    data["forecasts"]["offshore_waters"] = await self._fetch_text_forecast(session, "offshore")
                    
                    logger.info("Successfully collected OPC Pacific data")
                else:
                    logger.error(f"Failed to fetch OPC data: {response.status}")
                    
        except Exception as e:
            logger.error(f"Error fetching OPC data: {str(e)}")
            
        return data
        
    def _extract_chart_links(self, soup: BeautifulSoup, chart_type: str) -> List[str]:
        """Extract chart image links for specific chart type"""
        links = []
        try:
            # Find links containing the chart type text
            for link in soup.find_all('a'):
                if chart_type.lower() in link.text.lower():
                    href = link.get('href')
                    if href and (href.endswith('.gif') or href.endswith('.png')):
                        # Make absolute URL if relative
                        if href.startswith('/'):
                            href = f"https://ocean.weather.gov{href}"
                        links.append(href)
        except Exception as e:
            logger.error(f"Error extracting {chart_type} links: {str(e)}")
        return links
    
    async def _fetch_text_forecast(self, session: aiohttp.ClientSession, forecast_type: str) -> str:
        """Fetch text-based forecasts"""
        text_urls = {
            "high seas": "https://ocean.weather.gov/shtml/NFDHSFEPI.php",
            "offshore": "https://ocean.weather.gov/shtml/NFDOFFN01.php"
        }
        
        url = text_urls.get(forecast_type)
        if not url:
            return ""
            
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    # Extract the pre-formatted text content
                    pre_text = soup.find('pre')
                    if pre_text:
                        return pre_text.text
        except Exception as e:
            logger.error(f"Error fetching {forecast_type} forecast: {str(e)}")
            
        return ""
    
    async def collect(self) -> str:
        """Main collection entry point"""
        async with aiohttp.ClientSession() as session:
            data = await self.fetch_data(session)
            
            # Save collected data
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"opc_data_{timestamp}.json"
            filepath = Path("data") / filename
            filepath.parent.mkdir(exist_ok=True)
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"OPC data saved to {filepath}")
            return str(filepath)