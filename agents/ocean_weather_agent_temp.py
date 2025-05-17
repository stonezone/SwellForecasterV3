"""
Ocean Weather Agent for SwellForecasterV3.

This agent collects images and data from Ocean Weather (ocean.weather.gov),
specifically focusing on the Pacific tab which contains critical wave and weather charts.
"""

import asyncio
import aiohttp
import json
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Dict, List, Any
from logging_config import get_logger
import sys
import os
# Add parent directory to path to import image_utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.image_utils_temp import download_and_save_images, download_image, save_image

logger = get_logger(__name__)


class OceanWeatherAgent:
    """Agent for collecting Ocean Weather Pacific tab data and images"""
    
    def __init__(self, config):
        """Initialize the Ocean Weather agent"""
        self.config = config
        self.base_url = "https://ocean.weather.gov"
        self.pac_tab_url = f"{self.base_url}/Pac_tab.php"
        
        # Critical Pacific basin images
        self.pacific_images = {
            # Surface Analysis
            'pacific_surface_analysis_00hr': f"{self.base_url}/shtml/P_00hr500.gif",
            'pacific_surface_analysis_24hr': f"{self.base_url}/shtml/P_24hr500.gif",
            'pacific_surface_analysis_48hr': f"{self.base_url}/shtml/P_48hr500.gif",
            'pacific_surface_analysis_72hr': f"{self.base_url}/shtml/P_72hr500.gif",
            'pacific_surface_analysis_96hr': f"{self.base_url}/shtml/P_96hr500.gif",
            
            # Wave Analysis
            'pacific_wave_analysis_00hr': f"{self.base_url}/shtml/P_00hrww.gif",
            'pacific_wave_analysis_24hr': f"{self.base_url}/shtml/P_24hrww.gif",
            'pacific_wave_analysis_48hr': f"{self.base_url}/shtml/P_48hrww.gif",
            'pacific_wave_analysis_72hr': f"{self.base_url}/shtml/P_72hrww.gif",
            'pacific_wave_analysis_96hr': f"{self.base_url}/shtml/P_96hrww.gif",
            
            # Combined Surface/Wave
            'pacific_combined_00hr': f"{self.base_url}/shtml/P_00hr.gif",
            'pacific_combined_24hr': f"{self.base_url}/shtml/P_24hr.gif",
            'pacific_combined_48hr': f"{self.base_url}/shtml/P_48hr.gif",
            'pacific_combined_72hr': f"{self.base_url}/shtml/P_72hr.gif",
            'pacific_combined_96hr': f"{self.base_url}/shtml/P_96hr.gif",
            
            # Wind/Wave
            'pacific_wind_wave_00hr': f"{self.base_url}/shtml/P_00hrwnd.gif",
            'pacific_wind_wave_24hr': f"{self.base_url}/shtml/P_24hrwnd.gif",
            'pacific_wind_wave_48hr': f"{self.base_url}/shtml/P_48hrwnd.gif",
            'pacific_wind_wave_72hr': f"{self.base_url}/shtml/P_72hrwnd.gif",
            'pacific_wind_wave_96hr': f"{self.base_url}/shtml/P_96hrwnd.gif",
            
            # Satellite
            'pacific_satellite_ir': f"{self.base_url}/shtml/GOES_PAC_IR.jpg",
            'pacific_satellite_vis': f"{self.base_url}/shtml/GOES_PAC_VIS.jpg",
            
            # Sea State Analysis
            'pacific_sea_state': f"{self.base_url}/PT_SEA_SFC.gif"
        }
        
    async def fetch_page_content(self, session: aiohttp.ClientSession) -> str:
        """Fetch the Pacific tab page content"""
        try:
            async with session.get(self.pac_tab_url) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    logger.error(f"Failed to fetch Pacific tab page: HTTP {response.status}")
                    return ""
        except Exception as e:
            logger.error(f"Error fetching Pacific tab page: {str(e)}")
            return ""
    
    async def parse_additional_images(self, html: str) -> Dict[str, str]:
        """Parse the page to find additional image links"""
        additional_images = {}
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Find all image links on the page
            for img_tag in soup.find_all('img'):
                src = img_tag.get('src', '')
                alt = img_tag.get('alt', '')
                
                if src and ('.gif' in src or '.jpg' in src or '.png' in src):
                    # Convert relative URLs to absolute
                    if not src.startswith('http'):
                        if src.startswith('/'):
                            src = f"{self.base_url}{src}"
                        else:
                            src = f"{self.base_url}/{src}"
                    
                    # Create a descriptive name from alt text or filename
                    name = alt.replace(' ', '_').lower() if alt else src.split('/')[-1].split('.')[0]
                    
                    # Only add if not already in our list
                    if name not in self.pacific_images and name not in additional_images:
                        additional_images[name] = src
                        
        except Exception as e:
            logger.error(f"Error parsing additional images: {str(e)}")
            
        return additional_images
    
    async def collect(self, ctx, session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
        """
        Collect Ocean Weather Pacific data and images.
        
        Args:
            ctx: Context object with save() method
            session: aiohttp client session
            
        Returns:
            List of metadata dictionaries
        """
        metadata_list = []
        
        try:
            logger.info("Collecting Ocean Weather Pacific data and images...")
            
            # Fetch the main page content
            page_content = await self.fetch_page_content(session)
            
            # Parse for additional images
            additional_images = await self.parse_additional_images(page_content)
            
            # Combine all images
            all_images = {**self.pacific_images, **additional_images}
            
            logger.info(f"Found {len(all_images)} total Ocean Weather images to download")
            
            # Download all images
            image_results = await download_and_save_images(ctx, all_images, session)
            
            # Create data summary
            data = {
                'timestamp': datetime.utcnow().isoformat(),
                'source': 'Ocean_Weather_Pacific',
                'url': self.pac_tab_url,
                'images': {},
                'image_categories': {
                    'surface_analysis': [],
                    'wave_analysis': [],
                    'wind_wave': [],
                    'satellite': [],
                    'other': []
                }
            }
            
            # Organize images by category and record results
            for name, success in image_results.items():
                if success:
                    data['images'][name] = {
                        'filename': f"{name}.gif",
                        'downloaded': True,
                        'type': 'image'
                    }
                    
                    # Categorize the image
                    if 'surface_analysis' in name:
                        data['image_categories']['surface_analysis'].append(name)
                    elif 'wave_analysis' in name:
                        data['image_categories']['wave_analysis'].append(name)
                    elif 'wind_wave' in name:
                        data['image_categories']['wind_wave'].append(name)
                    elif 'satellite' in name:
                        data['image_categories']['satellite'].append(name)
                    else:
                        data['image_categories']['other'].append(name)
                        
                    logger.info(f"Successfully downloaded Ocean Weather image: {name}")
                else:
                    data['images'][name] = {
                        'url': all_images[name],
                        'downloaded': False,
                        'error': 'Failed to download'
                    }
            
            # Add page text content if available
            if page_content:
                soup = BeautifulSoup(page_content, 'html.parser')
                # Extract any textual forecasts or warnings
                text_content = []
                for p in soup.find_all(['p', 'pre']):
                    text = p.text.strip()
                    if text and len(text) > 50:  # Only include substantial text
                        text_content.append(text)
                
                if text_content:
                    data['text_content'] = text_content
            
            # Save collected data
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"ocean_weather_data_{timestamp}.json"
            
            # Save using the context's save method
            await ctx.save(filename, json.dumps(data, indent=2))
            
            # Create metadata
            successful_downloads = sum(1 for img in data['images'].values() if img.get('downloaded', False))
            metadata = {
                'source': 'Ocean_Weather_Pacific',
                'type': 'ocean_weather_charts',
                'filename': filename,
                'url': self.pac_tab_url,
                'priority': 3,
                'description': 'NOAA Ocean Weather Pacific charts and analysis',
                'north_facing': True,
                'south_facing': True,
                'includes_images': True,
                'image_count': successful_downloads,
                'total_images_attempted': len(all_images),
                'categories': {
                    'surface_analysis': len(data['image_categories']['surface_analysis']),
                    'wave_analysis': len(data['image_categories']['wave_analysis']),
                    'wind_wave': len(data['image_categories']['wind_wave']),
                    'satellite': len(data['image_categories']['satellite']),
                    'other': len(data['image_categories']['other'])
                }
            }
            
            metadata_list.append(metadata)
            logger.info(f"Successfully collected Ocean Weather data with {successful_downloads}/{len(all_images)} images")
            
        except Exception as e:
            logger.error(f"Error in Ocean Weather agent collection: {str(e)}")
        
        return metadata_list