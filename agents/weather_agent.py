"""
Weather Agent for SwellForecaster V3.

Collects weather data from NOAA/NWS for Hawaii surf forecasting.
"""

import aiohttp
import os
import re
from typing import List, Dict, Any
from logging_config import get_logger

logger = get_logger(__name__)


class WeatherAgent:
    """
    Collects weather data from NOAA/NWS.
    """
    
    def __init__(self, config):
        """
        Initialize the WeatherAgent.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.base_url = "https://api.weather.gov"
        
    async def collect(self, ctx, session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
        """
        Collect weather data for Hawaii.
        
        Args:
            ctx: Context object with save() method
            session: aiohttp client session
            
        Returns:
            List of metadata dictionaries
        """
        metadata_list = []
        
        # Hawaii weather data sources
        sources = [
            {
                'url': 'https://api.weather.gov/gridpoints/HFO/170,112/forecast',
                'name': 'honolulu_forecast',
                'type': 'gridpoint_forecast',
                'description': 'Honolulu area forecast'
            },
            {
                'url': 'https://api.weather.gov/gridpoints/HFO/157,120/forecast',
                'name': 'north_shore_forecast',
                'type': 'gridpoint_forecast',
                'description': 'North Shore forecast'
            },
            {
                'url': 'https://api.weather.gov/offices/HFO',
                'name': 'hfo_office_info',
                'type': 'office_info',
                'description': 'Hawaii Forecast Office information'
            },
            {
                'url': 'https://api.weather.gov/stations/PHLI/observations/latest',
                'name': 'lihue_observations',
                'type': 'observation',
                'description': 'Lihue airport observations'
            },
            {
                'url': 'https://api.weather.gov/stations/PHNL/observations/latest',
                'name': 'honolulu_observations',
                'type': 'observation',
                'description': 'Honolulu airport observations'
            }
        ]
        
        # Also get the forecast discussion for meteorological context
        sources.append({
            'url': 'https://forecast.weather.gov/product.php?site=HFO&issuedby=HFO&product=AFD&format=txt&version=1&glossary=0',
            'name': 'hawaii_forecast_discussion',
            'type': 'forecast_discussion',
            'description': 'Hawaii area forecast discussion'
        })
        
        for source in sources:
            try:
                logger.info(f"Fetching weather data from {source['name']}")
                headers = {'User-Agent': 'SwellForecasterV3 (gcug420@gmail.com)'}
                
                async with session.get(source['url'], headers=headers) as response:
                    if source['type'] in ['gridpoint_forecast', 'office_info', 'observation']:
                        # JSON responses
                        data = await response.json()
                        content = self._format_json_data(data, source['type'])
                    else:
                        # Text responses
                        content = await response.text()
                    
                    # Save the data
                    filename = f"weather_{source['name']}.txt"
                    await ctx.save(filename, content)
                    
                    # Create metadata
                    metadata = {
                        'source': 'NOAA/NWS',
                        'type': 'weather',
                        'subtype': source['type'],
                        'filename': filename,
                        'name': source['name'],
                        'description': source['description'],
                        'url': source['url'],
                        'priority': 2
                    }
                    
                    # Add regional tags
                    if 'north_shore' in source['name'].lower():
                        metadata['north_facing'] = True
                    elif 'south' in source['name'].lower():
                        metadata['south_facing'] = True
                    else:
                        # General Hawaii data is relevant to both shores
                        metadata['north_facing'] = True
                        metadata['south_facing'] = True
                    
                    metadata_list.append(metadata)
                    logger.info(f"Collected weather data from {source['name']}")
                    
            except Exception as e:
                logger.error(f"Error fetching weather data from {source['name']}: {e}")
                if hasattr(ctx, 'failure_tracker'):
                    ctx.failure_tracker.log_failure(
                        source='NOAA/NWS',
                        url=source['url'],
                        error=str(e),
                        agent='weather'
                    )
        
        return metadata_list
    
    def _format_json_data(self, data: dict, data_type: str) -> str:
        """
        Format JSON data into readable text format.
        
        Args:
            data: JSON data dictionary
            data_type: Type of data for formatting
            
        Returns:
            Formatted text
        """
        output = []
        
        if data_type == 'gridpoint_forecast':
            output.append("WEATHER FORECAST")
            output.append("=" * 50)
            
            if 'properties' in data and 'periods' in data['properties']:
                for period in data['properties']['periods']:
                    output.append(f"\n{period['name']} ({period['startTime']})")
                    output.append(f"Temperature: {period['temperature']}°{period['temperatureUnit']}")
                    output.append(f"Wind: {period['windSpeed']} {period['windDirection']}")
                    output.append(f"Forecast: {period['detailedForecast']}")
                    output.append("-" * 30)
        
        elif data_type == 'observation':
            output.append("CURRENT OBSERVATIONS")
            output.append("=" * 50)
            
            if 'properties' in data:
                props = data['properties']
                output.append(f"Time: {props.get('timestamp', 'N/A')}")
                output.append(f"Temperature: {props.get('temperature', {}).get('value', 'N/A')}°C")
                output.append(f"Wind Speed: {props.get('windSpeed', {}).get('value', 'N/A')} m/s")
                output.append(f"Wind Direction: {props.get('windDirection', {}).get('value', 'N/A')}°")
                output.append(f"Pressure: {props.get('seaLevelPressure', {}).get('value', 'N/A')} Pa")
                output.append(f"Humidity: {props.get('relativeHumidity', {}).get('value', 'N/A')}%")
                output.append(f"Conditions: {props.get('textDescription', 'N/A')}")
        
        elif data_type == 'office_info':
            output.append("FORECAST OFFICE INFORMATION")
            output.append("=" * 50)
            output.append(str(data))
        
        return '\n'.join(output)


# Agent function following the standard pattern
async def weather_agent(ctx, session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
    """
    Standard agent function for weather data collection.
    
    Args:
        ctx: Context object
        session: aiohttp client session
        
    Returns:
        List of metadata dictionaries
    """
    agent = WeatherAgent(ctx.cfg)
    return await agent.collect(ctx, session)