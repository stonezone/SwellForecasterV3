"""
Data Collector for SwellForecaster V3.

This module orchestrates data collection from various agents and uploads
the data to the Assistants API.
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

from agents.file_adapter import FileAdapter
from agents.buoy_agent import buoy_agent
from logging_config import get_logger
from failure_tracker import FailureTracker

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
    
    async def save(self, filename: str, content: Any) -> str:
        """
        Save content to a file in the bundle directory.
        
        Args:
            filename: Name of the file
            content: Content to save (string or bytes)
            
        Returns:
            Full path to the saved file
        """
        file_path = os.path.join(self.bundle_path, filename)
        
        try:
            # Create directory if needed
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Determine write mode
            mode = 'wb' if isinstance(content, bytes) else 'w'
            encoding = None if isinstance(content, bytes) else 'utf-8'
            
            # Save the file
            with open(file_path, mode, encoding=encoding) as f:
                f.write(content)
            
            self.saved_files.append(file_path)
            logger.debug(f"Saved {filename} to {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error saving {filename}: {e}")
            raise
    
    async def fetch(self, url: str, session: aiohttp.ClientSession) -> str:
        """
        Fetch content from a URL.
        
        Args:
            url: URL to fetch
            session: aiohttp client session
            
        Returns:
            Response content as string
        """
        try:
            async with session.get(url) as response:
                return await response.text()
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            raise


class DataCollector:
    """
    Orchestrates data collection from multiple agents.
    """
    
    def __init__(self, config: ConfigParser, file_adapter: FileAdapter):
        """
        Initialize the DataCollector.
        
        Args:
            config: Configuration object
            file_adapter: FileAdapter for uploading to Assistants API
        """
        self.config = config
        self.file_adapter = file_adapter
        self.data_dir = config.get('general', 'data_directory')
        self.failure_tracker = FailureTracker()
        
        # Available agents
        self.agents = {
            'buoy': buoy_agent,
            # Add more agents here as they're created
            # 'weather': weather_agent,
            # 'model': model_agent,
            # 'satellite': satellite_agent,
        }
    
    async def collect_all(self, region: Optional[str] = None) -> Dict[str, Any]:
        """
        Collect data from all configured agents.
        
        Args:
            region: Optional region to collect data for
            
        Returns:
            Bundle information including file IDs and metadata
        """
        # Create bundle directory
        bundle_id = uuid.uuid4().hex[:12]
        timestamp = datetime.now(timezone.utc)
        bundle_name = f"{bundle_id}_{int(timestamp.timestamp())}"
        bundle_path = os.path.join(self.data_dir, bundle_name)
        os.makedirs(bundle_path, exist_ok=True)
        
        logger.info(f"Starting data collection for bundle: {bundle_name}")
        
        # Create context for agents
        ctx = CollectorContext(bundle_path, self.config)
        
        # Reset file adapter for new bundle
        self.file_adapter.reset()
        
        # Collect data from all agents
        async with aiohttp.ClientSession() as session:
            tasks = []
            
            for agent_name, agent_func in self.agents.items():
                if self._is_agent_enabled(agent_name):
                    logger.info(f"Dispatching {agent_name} agent")
                    task = self._run_agent(agent_name, agent_func, ctx, session, bundle_path)
                    tasks.append(task)
            
            # Wait for all agents to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Log results
            for agent_name, result in zip(self.agents.keys(), results):
                if isinstance(result, Exception):
                    logger.error(f"Agent {agent_name} failed: {result}")
                else:
                    logger.info(f"Agent {agent_name} uploaded {len(result)} files")
        
        # Create bundle summary
        bundle_info = {
            'bundle_id': bundle_id,
            'timestamp': timestamp.isoformat(),
            'region': region or 'all',
            'duration': time.time() - timestamp.timestamp()
        }
        
        summary_file_id = self.file_adapter.create_bundle_summary(bundle_info)
        
        # Create final bundle metadata
        bundle_metadata = {
            'bundle_info': bundle_info,
            'summary_file_id': summary_file_id,
            'file_ids': [m['file_id'] for m in self.file_adapter.bundle_metadata],
            'bundle_path': bundle_path
        }
        
        # Save local metadata file
        metadata_path = os.path.join(bundle_path, 'metadata.json')
        with open(metadata_path, 'w') as f:
            json.dump(bundle_metadata, f, indent=2)
        
        logger.info(f"Completed data collection: {len(bundle_metadata['file_ids'])} files")
        return bundle_metadata
    
    async def _run_agent(self, agent_name: str, agent_func, ctx, session, bundle_path) -> List[str]:
        """
        Run a single agent and upload its data.
        
        Args:
            agent_name: Name of the agent
            agent_func: Agent function to execute
            ctx: Collector context
            session: aiohttp session
            bundle_path: Path to bundle directory
            
        Returns:
            List of uploaded file IDs
        """
        try:
            # Run the agent
            metadata_list = await agent_func(ctx, session)
            
            # Upload files through the adapter
            return self.file_adapter.add_agent_data(agent_name, metadata_list, bundle_path)
            
        except Exception as e:
            logger.error(f"Error running agent {agent_name}: {e}")
            # Track the failure
            self.failure_tracker.log_failure(
                source=agent_name,
                url="agent_execution",
                error=str(e),
                agent=agent_name
            )
            return []
    
    def _is_agent_enabled(self, agent_name: str) -> bool:
        """
        Check if an agent is enabled in configuration.
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            True if agent is enabled
        """
        # Check for specific enable flags in config
        enable_key = f"enable_{agent_name}"
        if self.config.has_option('sources', enable_key):
            return self.config.getboolean('sources', enable_key)
        
        # Default to enabled
        return True
    
    def get_latest_bundle(self) -> Optional[Dict[str, Any]]:
        """
        Get the most recent data bundle.
        
        Returns:
            Bundle metadata or None if no bundles exist
        """
        try:
            # List all bundle directories
            bundle_dirs = [
                d for d in os.listdir(self.data_dir)
                if os.path.isdir(os.path.join(self.data_dir, d))
            ]
            
            if not bundle_dirs:
                return None
            
            # Sort by timestamp (in directory name)
            bundle_dirs.sort(reverse=True)
            latest_dir = bundle_dirs[0]
            
            # Load metadata
            metadata_path = os.path.join(self.data_dir, latest_dir, 'metadata.json')
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r') as f:
                    return json.load(f)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting latest bundle: {e}")
            return None