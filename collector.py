"""
Data Collector V4 for SwellForecaster V3.

Final version with all corrected components.
"""

import asyncio
import aiohttp
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
from configparser import ConfigParser

from agents.file_adapter_v3_temp import FileAdapter  # V3 with correct methods
from agents.buoy_agent import buoy_agent
from agents.weather_agent import weather_agent
from agents.model_agent import model_agent
from agents.satellite_agent import satellite_agent
from agents.opc_agent_temp import OPCAgent
from agents.stormsurf_agent_temp import StormsurfAgent
from agents.nhc_agent_temp import NHCAgent
from agents.enso_agent_v3_temp import ENSOAgent  # V3 with correct URLs
from agents.ocean_weather_agent_v2_temp import OceanWeatherAgent  # V2 with correct URLs
from logging_config import get_logger
from failure_tracker_v2_temp import FailureTracker  # V2 with correct methods

logger = get_logger(__name__)


class CollectorContext:
    """
    Context object provided to agents for data collection.
    """
    
    def __init__(self, bundle_path: str, config: ConfigParser):
        """
        Initialize the collector context.
        
        Args:
            bundle_path: Path to save collected data
            config: Configuration object
        """
        self.bundle_path = bundle_path
        self.cfg = config
        self.saved_files: List[str] = []
    
    async def save(self, filename: str, content: Any, binary: bool = False):
        """
        Save content to a file in the bundle directory.
        
        Args:
            filename: Name of the file to save
            content: Content to save (string, bytes, or JSON-serializable object)
            binary: Whether to save as binary file
        """
        filepath = os.path.join(self.bundle_path, filename)
        
        try:
            if binary:
                mode = 'wb'
                data = content if isinstance(content, bytes) else content.encode('utf-8')
            else:
                mode = 'w'
                data = content
            
            with open(filepath, mode) as f:
                f.write(data)
                
            self.saved_files.append(filename)
            logger.info(f"Saved {'binary' if binary else 'text'} file: {filename}")
            
        except Exception as e:
            logger.error(f"Error saving file {filename}: {str(e)}")
            raise


class DataCollector:
    """
    Orchestrates data collection from multiple agents.
    """
    
    def __init__(self, config: ConfigParser):
        """
        Initialize the data collector.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.file_adapter = FileAdapter(config)
        self.failure_tracker = FailureTracker()
        
        # Configuration for data collection
        self.data_dir = self.config.get('paths', 'data_dir', fallback='./data')
        self.bundle_retention_days = self.config.getint('data_collection', 
                                                       'bundle_retention_days', 
                                                       fallback=7)
        
        # Configure agents
        self.agents = {
            'buoy': buoy_agent,
            'weather': weather_agent,
            'model': model_agent,
            'satellite': satellite_agent,
        }
        
        # Class-based agents - Final versions with image support
        self.class_agents = {
            'opc': OPCAgent,
            'stormsurf': StormsurfAgent,
            'nhc': NHCAgent,
            'enso': ENSOAgent,  # V3 with correct URLs
            'ocean_weather': OceanWeatherAgent,  # V2 with correct URLs
        }
        
        # Create data directory if it doesn't exist
        os.makedirs(self.data_dir, exist_ok=True)
        
    async def collect_from_agent(self, agent_name: str, agent, ctx: CollectorContext,
                               session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
        """
        Collect data from a single agent.
        
        Args:
            agent_name: Name of the agent
            agent: Agent instance or function
            ctx: Collector context
            session: aiohttp session
            
        Returns:
            List of metadata dictionaries
        """
        try:
            logger.info(f"Collecting data from {agent_name} agent")
            
            # Handle both function-based and class-based agents
            if hasattr(agent, 'collect'):
                # Class-based agent
                return await agent.collect(ctx, session)
            else:
                # Function-based agent
                return await agent(ctx, session)
                
        except Exception as e:
            error_msg = f"Error collecting from {agent_name}: {str(e)}"
            logger.error(error_msg)
            
            # Track failure
            self.failure_tracker.add_failure(
                source=agent_name,
                error_type=type(e).__name__,
                message=str(e)
            )
            
            return []
    
    async def collect_all(self, region: str = "North Pacific") -> Dict[str, Any]:
        """
        Collect data from all configured agents.
        
        Args:
            region: Region for data collection
            
        Returns:
            Bundle information dictionary
        """
        bundle_id = str(uuid.uuid4())
        bundle_path = os.path.join(self.data_dir, bundle_id)
        os.makedirs(bundle_path, exist_ok=True)
        
        ctx = CollectorContext(bundle_path, self.config)
        
        logger.info(f"Starting data collection for bundle {bundle_id}")
        
        async with aiohttp.ClientSession() as session:
            # Create tasks for all agents
            tasks = []
            
            # Function-based agents
            for agent_name, agent_func in self.agents.items():
                if self.config.getboolean('agents', agent_name, fallback=True):
                    tasks.append(self.collect_from_agent(agent_name, agent_func, ctx, session))
                    
            # Class-based agents with configuration
            for agent_name, agent_class in self.class_agents.items():
                if self.config.getboolean('agents', agent_name, fallback=True):
                    agent = agent_class(self.config)
                    tasks.append(self.collect_from_agent(agent_name, agent, ctx, session))
            
            # Run all agents concurrently
            results = await asyncio.gather(*tasks)
            
        # Flatten results and filter out empty lists
        all_metadata = []
        for result in results:
            if result:
                all_metadata.extend(result)
        
        # Calculate image statistics
        total_images = 0
        for metadata in all_metadata:
            if metadata.get('includes_images'):
                total_images += metadata.get('image_count', 0)
        
        # Create bundle metadata
        bundle_metadata = {
            'bundle_id': bundle_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'region': region,
            'files': all_metadata,
            'total_files': len(all_metadata),
            'saved_files': ctx.saved_files,
            'collection_stats': {
                'total_agents': len(tasks),
                'successful_agents': sum(1 for r in results if r),
                'total_files': len(all_metadata),
                'total_images': total_images,
                'total_saved_files': len(ctx.saved_files)
            }
        }
        
        # Save bundle metadata
        metadata_path = os.path.join(bundle_path, "bundle_metadata.json")
        with open(metadata_path, 'w') as f:
            json.dump(bundle_metadata, f, indent=2)
        
        # Upload to Assistants API
        logger.info(f"Uploading {len(ctx.saved_files)} files to Assistants API")
        file_ids = await self.file_adapter.upload_bundle(bundle_path, bundle_metadata)
        
        # Update bundle metadata with file IDs
        bundle_metadata['uploaded_file_ids'] = file_ids
        bundle_metadata['collection_stats']['uploaded_files'] = len(file_ids)
        
        # Save updated metadata
        with open(metadata_path, 'w') as f:
            json.dump(bundle_metadata, f, indent=2)
        
        # Save failure summary if there were any failures
        failure_summary = self.failure_tracker.get_summary()
        if failure_summary['total_failures'] > 0:
            failure_path = os.path.join(bundle_path, "failure_summary.json")
            self.failure_tracker.save_summary(failure_path)
            
        logger.info(f"Data collection complete. Bundle ID: {bundle_id}")
        logger.info(f"Total files saved: {len(ctx.saved_files)}, Images: {total_images}")
        logger.info(f"Uploaded to API: {len(file_ids)} files")
        
        return bundle_metadata
    
    def cleanup_old_bundles(self):
        """
        Remove bundles older than retention period.
        """
        try:
            cutoff_time = time.time() - (self.bundle_retention_days * 24 * 60 * 60)
            
            for item in os.listdir(self.data_dir):
                item_path = os.path.join(self.data_dir, item)
                
                # Skip if not a directory
                if not os.path.isdir(item_path):
                    continue
                
                # Check if it's an old bundle
                if os.path.getmtime(item_path) < cutoff_time:
                    logger.info(f"Removing old bundle: {item}")
                    import shutil
                    shutil.rmtree(item_path)
                    
        except Exception as e:
            logger.error(f"Error cleaning up old bundles: {str(e)}")