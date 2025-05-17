"""
ENSO (El Niño/Southern Oscillation) Agent for SwellForecasterV3 V2.

This version downloads actual images instead of just storing URLs.
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


class ENSOAgent:
    """Agent for collecting ENSO diagnostic data with image downloads"""
    
    def __init__(self, config):
        """Initialize the ENSO agent"""
        self.config = config
        self.base_url = "https://www.cpc.ncep.noaa.gov"
        self.sources = {
            'enso_discussion': f"{self.base_url}/products/analysis_monitoring/enso_advisory/ensodisc.shtml",
            'enso_alert': f"{self.base_url}/products/analysis_monitoring/enso_advisory/enso-alert-readme.shtml",
            'sst_anomalies': f"{self.base_url}/products/analysis_monitoring/ensostuff/ONI_v5.php",
            'mjo_status': f"{self.base_url}/products/precip/CWlink/MJO/mjo.shtml",
            'images': {
                'sst_anomaly_map': f"{self.base_url}/products/analysis_monitoring/ocean/index/heat_content_index/heat_content_pentad.gif",
                'subsurface_temps': f"{self.base_url}/products/analysis_monitoring/ocean/index/heat_content_index/heat_content_subsurface.gif",
                'sst_weekly': f"{self.base_url}/data/indices/wksst8110.for",
                'oni_graph': f"{self.base_url}/products/analysis_monitoring/ensostuff/ONI_v5.php",
                'pacific_sst': f"{self.base_url}/products/analysis_monitoring/ensostuff/sst.gif"
            }
        }
        # Additional trade wind images from different pages
        self.trade_wind_images = {
            'trade_wind_current': f"{self.base_url}/products/analysis_monitoring/ensostuff/curr.anom.gif",
            'trade_wind_monthly': f"{self.base_url}/products/analysis_monitoring/ensostuff/wind.mon.mean.gif"
        }
        
    async def fetch_data(self, ctx, session: aiohttp.ClientSession) -> Dict[str, Any]:
        """Fetch ENSO diagnostic data from CPC including images"""
        try:
            data = {
                'timestamp': datetime.utcnow().isoformat(),
                'source': 'NOAA_CPC',
                'enso_status': {},
                'forecasts': {},
                'images': {},
                'indices': {}
            }
            
            # Fetch ENSO discussion
            try:
                async with session.get(self.sources['enso_discussion']) as response:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Extract discussion text
                    pre_tags = soup.find_all('pre')
                    if pre_tags:
                        data['forecasts']['enso_discussion'] = {
                            'text': pre_tags[0].text.strip(),
                            'url': self.sources['enso_discussion']
                        }
                        
                        # Extract ENSO status from discussion
                        discussion_text = pre_tags[0].text
                        data['enso_status'] = self._extract_enso_status(discussion_text)
                        
            except Exception as e:
                logger.error(f"Error fetching ENSO discussion: {str(e)}")
                
            # Fetch ENSO alert status
            try:
                async with session.get(self.sources['enso_alert']) as response:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Extract alert level
                    if soup:
                        data['enso_status']['alert_level'] = self._extract_alert_level(soup)
                        
            except Exception as e:
                logger.error(f"Error fetching ENSO alert: {str(e)}")
                
            # Fetch SST anomaly data (ONI index)
            try:
                async with session.get(self.sources['sst_anomalies']) as response:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Extract ONI values
                    tables = soup.find_all('table')
                    if tables:
                        data['indices']['oni'] = self._extract_oni_values(tables[0])
                        
            except Exception as e:
                logger.error(f"Error fetching SST anomalies: {str(e)}")
                
            # Download images
            logger.info("Downloading ENSO images...")
            
            # Download main ENSO images
            image_results = await download_and_save_images(ctx, self.sources['images'], session)
            for name, success in image_results.items():
                if success:
                    data['images'][name] = {
                        'filename': f"{name}.gif",
                        'downloaded': True,
                        'type': 'image'
                    }
                    logger.info(f"Successfully downloaded ENSO image: {name}")
                else:
                    data['images'][name] = {
                        'url': self.sources['images'][name],
                        'downloaded': False,
                        'error': 'Failed to download'
                    }
                    
            # Download trade wind images
            trade_wind_results = await download_and_save_images(ctx, self.trade_wind_images, session)
            for name, success in trade_wind_results.items():
                if success:
                    data['images'][name] = {
                        'filename': f"{name}.gif",
                        'downloaded': True,
                        'type': 'image'
                    }
                    logger.info(f"Successfully downloaded trade wind image: {name}")
                else:
                    data['images'][name] = {
                        'url': self.trade_wind_images[name],
                        'downloaded': False,
                        'error': 'Failed to download'
                    }
                
            return data
            
        except Exception as e:
            logger.error(f"Error in ENSO data collection: {str(e)}")
            return {}
            
    def _extract_enso_status(self, text: str) -> Dict[str, str]:
        """Extract current ENSO status from discussion text"""
        status = {
            'current_phase': 'Neutral',
            'outlook': '',
            'probability': ''
        }
        
        try:
            text_lower = text.lower()
            
            # Determine current phase
            if 'el niño' in text_lower or 'el nino' in text_lower:
                if 'conditions' in text_lower and 'present' in text_lower:
                    status['current_phase'] = 'El Niño'
            elif 'la niña' in text_lower or 'la nina' in text_lower:
                if 'conditions' in text_lower and 'present' in text_lower:
                    status['current_phase'] = 'La Niña'
                    
            # Extract outlook
            if 'outlook' in text_lower:
                outlook_start = text_lower.find('outlook')
                outlook_text = text[outlook_start:outlook_start+200]
                status['outlook'] = outlook_text.strip()
                
            # Look for probability statements
            if 'probability' in text_lower or 'chance' in text_lower:
                prob_start = text_lower.find('probability')
                if prob_start == -1:
                    prob_start = text_lower.find('chance')
                prob_text = text[prob_start:prob_start+100]
                status['probability'] = prob_text.strip()
                
        except Exception as e:
            logger.error(f"Error extracting ENSO status: {str(e)}")
            
        return status
        
    def _extract_alert_level(self, soup: BeautifulSoup) -> str:
        """Extract ENSO alert level from page"""
        try:
            # Look for alert status in various formats
            alert_tags = soup.find_all(['h2', 'h3', 'strong'])
            for tag in alert_tags:
                text = tag.text.lower()
                if 'watch' in text:
                    return 'Watch'
                elif 'advisory' in text:
                    return 'Advisory'
                elif 'warning' in text:
                    return 'Warning'
                    
            return 'Not Active'
            
        except Exception as e:
            logger.error(f"Error extracting alert level: {str(e)}")
            return 'Unknown'
            
    def _extract_oni_values(self, table) -> List[Dict[str, Any]]:
        """Extract recent ONI (Oceanic Niño Index) values"""
        oni_values = []
        
        try:
            rows = table.find_all('tr')
            
            # Get headers
            headers = [th.text.strip() for th in rows[0].find_all(['th', 'td'])]
            
            # Get last few rows of data
            for row in rows[-5:]:  # Last 5 months
                cells = row.find_all('td')
                if len(cells) >= 2:
                    oni_values.append({
                        'period': cells[0].text.strip(),
                        'value': cells[1].text.strip(),
                        'anomaly': cells[2].text.strip() if len(cells) > 2 else ''
                    })
                    
        except Exception as e:
            logger.error(f"Error extracting ONI values: {str(e)}")
            
        return oni_values
    
    async def collect(self, ctx, session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
        """
        Collect ENSO diagnostic data with images.
        
        Args:
            ctx: Context object with save() method
            session: aiohttp client session
            
        Returns:
            List of metadata dictionaries
        """
        metadata_list = []
        
        try:
            # Fetch ENSO data including images
            data = await self.fetch_data(ctx, session)
            
            if data:
                # Save collected data
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"enso_data_{timestamp}.json"
                
                # Save using the context's save method
                await ctx.save(filename, json.dumps(data, indent=2))
                
                # Create metadata
                metadata = {
                    'source': 'CPC_ENSO',
                    'type': 'climate_diagnostic',
                    'filename': filename,
                    'url': self.base_url,
                    'priority': 4,
                    'description': 'NOAA CPC ENSO diagnostic information, forecasts, and images',
                    'north_facing': True,
                    'south_facing': True,
                    'long_term_relevant': True,
                    'includes_images': True,
                    'image_count': sum(1 for img in data.get('images', {}).values() if img.get('downloaded', False))
                }
                
                metadata_list.append(metadata)
                logger.info(f"Successfully collected ENSO data with {metadata['image_count']} images")
            
        except Exception as e:
            logger.error(f"Error in ENSO agent collection: {str(e)}")
        
        return metadata_list