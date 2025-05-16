"""Stormsurf data collection agent"""
import asyncio
import aiohttp
import logging
from typing import Dict, List, Any
from datetime import datetime
from bs4 import BeautifulSoup

import json
from pathlib import Path

logger = logging.getLogger(__name__)

class StormsurfAgent:
    """Agent for collecting Stormsurf wave models and forecasts"""
    
    def __init__(self):
        self.sources = {
            "pacific_wave_models": "https://www.stormsurf.com/page2/links/pacwam.shtml",
            "north_pacific_height": "https://www.stormsurfing.com/cgi/display.cgi?a=npac_height",
            "pacific_surface_pressure": "https://www.stormsurf.com/page2/links/pacslp.shtml",
            "pacific_period": "https://www.stormsurfing.com/cgi/display.cgi?a=pac_per",
            "south_pacific_precip": "https://www.stormsurfing.com/cgi/display_alt.cgi?a=spac_precip"
        }
        
    async def fetch_data(self, session: aiohttp.ClientSession) -> Dict[str, Any]:
        """Fetch all Stormsurf data including models and charts"""
        data = {
            "source": "Stormsurf",
            "collected_at": datetime.now().isoformat(),
            "models": {},
            "charts": {},
            "analyses": {}
        }
        
        # Collect data from each source
        for source_name, url in self.sources.items():
            try:
                logger.info(f"Fetching Stormsurf {source_name}")
                async with session.get(url) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Extract model images and links
                        if source_name == "pacific_wave_models":
                            data["models"]["ww3_heights"] = self._extract_ww3_models(soup)
                        elif source_name == "north_pacific_height":
                            data["models"]["npac_height"] = self._extract_model_images(soup)
                        elif source_name == "pacific_surface_pressure":
                            data["models"]["pressure"] = self._extract_pressure_models(soup)
                        elif source_name == "pacific_period":
                            data["models"]["swell_period"] = self._extract_model_images(soup)
                        elif source_name == "south_pacific_precip":
                            data["models"]["spac_precip"] = self._extract_model_images(soup)
                            
                        # Extract any text analysis
                        text_content = self._extract_text_content(soup)
                        if text_content:
                            data["analyses"][source_name] = text_content
                            
                    else:
                        logger.error(f"Failed to fetch {source_name}: {response.status}")
                        
            except Exception as e:
                logger.error(f"Error fetching {source_name}: {str(e)}")
                
        return data
        
    def _extract_ww3_models(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Extract WaveWatch III model links"""
        models = []
        try:
            # Look for WW3 model links
            for link in soup.find_all('a'):
                href = link.get('href')
                text = link.text.strip()
                
                if href and 'ww3' in href.lower():
                    model_info = {
                        "name": text,
                        "url": href if href.startswith('http') else f"https://www.stormsurf.com{href}",
                        "type": "wave_height"
                    }
                    
                    # Determine forecast hour from text
                    if "00hr" in text.lower():
                        model_info["forecast_hour"] = 0
                    elif "24hr" in text.lower():
                        model_info["forecast_hour"] = 24
                    elif "48hr" in text.lower():
                        model_info["forecast_hour"] = 48
                    elif "72hr" in text.lower():
                        model_info["forecast_hour"] = 72
                        
                    models.append(model_info)
                    
        except Exception as e:
            logger.error(f"Error extracting WW3 models: {str(e)}")
            
        return models
    
    def _extract_pressure_models(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Extract surface pressure model links"""
        models = []
        try:
            # Look for pressure/precipitation model links
            for link in soup.find_all('a'):
                href = link.get('href')
                text = link.text.strip()
                
                if href and ('slp' in href.lower() or 'pressure' in text.lower()):
                    model_info = {
                        "name": text,
                        "url": href if href.startswith('http') else f"https://www.stormsurf.com{href}",
                        "type": "surface_pressure"
                    }
                    models.append(model_info)
                    
        except Exception as e:
            logger.error(f"Error extracting pressure models: {str(e)}")
            
        return models
        
    def _extract_model_images(self, soup: BeautifulSoup) -> List[str]:
        """Extract model image URLs"""
        images = []
        try:
            # Look for image links
            for img in soup.find_all('img'):
                src = img.get('src')
                if src and ('.gif' in src or '.png' in src or '.jpg' in src):
                    # Make absolute URL if relative
                    if not src.startswith('http'):
                        base_url = "https://www.stormsurfing.com"
                        src = f"{base_url}{src}" if src.startswith('/') else f"{base_url}/{src}"
                    images.append(src)
                    
        except Exception as e:
            logger.error(f"Error extracting model images: {str(e)}")
            
        return images
        
    def _extract_text_content(self, soup: BeautifulSoup) -> str:
        """Extract any text analysis or commentary"""
        text_content = ""
        try:
            # Look for text in pre tags or specific divs
            for pre in soup.find_all('pre'):
                text_content += pre.text + "\n\n"
                
            # Look for analysis text
            for div in soup.find_all('div', class_=['analysis', 'forecast', 'commentary']):
                text_content += div.text + "\n\n"
                
        except Exception as e:
            logger.error(f"Error extracting text content: {str(e)}")
            
        return text_content.strip()
    
    async def collect(self) -> str:
        """Main collection entry point"""
        async with aiohttp.ClientSession() as session:
            data = await self.fetch_data(session)
            
            # Save collected data
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"stormsurf_data_{timestamp}.json"
            filepath = Path("data") / filename
            filepath.parent.mkdir(exist_ok=True)
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Stormsurf data saved to {filepath}")
            return str(filepath)