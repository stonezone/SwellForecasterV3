"""
Stormsurf Agent for SwellForecasterV3.

This agent collects wave model data and forecasts from Stormsurf/Stormsurfing,
a popular surf forecasting website with detailed Pacific wave models.
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


class StormsurfAgent:
    """Agent for collecting Stormsurf wave model data"""
    
    def __init__(self, config):
        """Initialize the Stormsurf agent"""
        self.config = config
        self.sources = {
            'pacific_wave_models': 'https://www.stormsurf.com/page/data/nep.shtml',
            'north_pacific_height': 'https://www.stormsurfing.com/swf/nph.html',
            'pacific_surface_pressure': 'https://www.stormsurf.com/page/data/slp.shtml',
            'pacific_period': 'https://www.stormsurfing.com/swf/npp.html',
            'south_pacific_precip': 'https://www.stormsurfing.com/swf/spp.html'
        }
        
    async def fetch_data(self, session: aiohttp.ClientSession) -> Dict[str, Any]:
        """Fetch wave model data from Stormsurf"""
        data = {
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'Stormsurf',
            'models': {},
            'errors': []
        }
        
        for source_name, url in self.sources.items():
            try:
                logger.info(f"Fetching Stormsurf {source_name}")
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Extract model data based on source type
                        model_data = {
                            'url': url,
                            'fetched_at': datetime.utcnow().isoformat()
                        }
                        
                        if 'wave' in source_name or 'height' in source_name:
                            model_data['type'] = 'wave_height'
                            model_data['models'] = self._extract_wave_models(soup)
                        elif 'pressure' in source_name:
                            model_data['type'] = 'surface_pressure'
                            model_data['models'] = self._extract_pressure_models(soup)
                        elif 'period' in source_name:
                            model_data['type'] = 'wave_period'
                            model_data['models'] = self._extract_wave_models(soup)
                        elif 'precip' in source_name:
                            model_data['type'] = 'precipitation'
                            model_data['models'] = self._extract_pressure_models(soup)
                            
                        # Extract any image links for wave model graphics
                        model_data['images'] = self._extract_model_images(soup)
                        
                        # Extract any text content or analysis
                        model_data['analysis'] = self._extract_text_content(soup)
                        
                        data['models'][source_name] = model_data
                        
            except aiohttp.ClientError as e:
                error_msg = f"Error fetching {source_name}: {str(e)}"
                logger.error(error_msg)
                data['errors'].append(error_msg)
            except Exception as e:
                error_msg = f"Unexpected error with {source_name}: {str(e)}"
                logger.error(error_msg) 
                data['errors'].append(error_msg)
                
        return data
        
    def _extract_wave_models(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Extract wave model links and info from page"""
        models = []
        try:
            # Look for model links in common patterns
            for link in soup.find_all('a'):
                href = link.get('href')
                text = link.text.strip()
                
                if href and ('model' in href.lower() or 'wave' in text.lower()):
                    model_info = {
                        "name": text,
                        "url": href if href.startswith('http') else f"https://www.stormsurf.com{href}",
                        "type": "wave_model"
                    }
                    models.append(model_info)
                    
        except Exception as e:
            logger.error(f"Error extracting wave models: {str(e)}")
            
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
                text_content += pre.text.strip() + "\n\n"
                
            # Look for analysis divs
            for div in soup.find_all('div', class_='analysis'):
                text_content += div.text.strip() + "\n\n"
                
        except Exception as e:
            logger.error(f"Error extracting text content: {str(e)}")
            
        return text_content.strip()
        
    async def collect(self, ctx, session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
        """
        Collect Stormsurf wave model data.
        
        Args:
            ctx: Context object with save() method
            session: aiohttp client session
            
        Returns:
            List of metadata dictionaries
        """
        metadata_list = []
        
        try:
            # Fetch Stormsurf data
            data = await self.fetch_data(session)
            
            # Save collected data using the context save method
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"stormsurf_data_{timestamp}.json"
            
            # Save using the context's save method (this saves to the bundle directory)
            await ctx.save(filename, json.dumps(data, indent=2))
            
            # Create metadata
            metadata = {
                'source': 'Stormsurf',
                'type': 'wave_models',
                'filename': filename,
                'url': 'https://www.stormsurf.com',
                'priority': 3,
                'description': 'Stormsurf Pacific wave models and analysis',
                'north_facing': True,
                'south_facing': True
            }
            
            metadata_list.append(metadata)
            logger.info(f"Stormsurf data saved successfully")
            
        except Exception as e:
            logger.error(f"Error in Stormsurf agent collection: {str(e)}")
            
        return metadata_list