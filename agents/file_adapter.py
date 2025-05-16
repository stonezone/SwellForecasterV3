"""
File Adapter for SwellForecaster V3.

This module adapts the existing agent data collection pattern to work with
the new Assistants API file upload system.
"""

import os
import json
import asyncio
from typing import List, Dict, Any, Optional
from assistants.file_manager import FileManager
from logging_config import get_logger

logger = get_logger(__name__)


class FileAdapter:
    """
    Bridges the gap between existing agents and the Assistants API file system.
    """
    
    def __init__(self, file_manager: FileManager):
        """
        Initialize the FileAdapter.
        
        Args:
            file_manager: FileManager instance for handling uploads
        """
        self.file_manager = file_manager
        self.bundle_metadata: List[Dict[str, Any]] = []
    
    def add_agent_data(self, agent_name: str, metadata_list: List[Dict[str, Any]],
                      bundle_path: str) -> List[str]:
        """
        Process agent data and upload files to Assistants API.
        
        Args:
            agent_name: Name of the agent that collected the data
            metadata_list: List of metadata dictionaries from the agent
            bundle_path: Path to the bundle directory containing the files
            
        Returns:
            List of uploaded file IDs
        """
        file_ids = []
        
        for metadata in metadata_list:
            # Skip if no filename in metadata
            if 'filename' not in metadata:
                logger.warning(f"No filename in metadata from {agent_name}: {metadata}")
                continue
            
            # Construct full file path
            file_path = os.path.join(bundle_path, metadata['filename'])
            
            if not os.path.exists(file_path):
                logger.warning(f"File not found: {file_path}")
                continue
            
            try:
                # Upload file to Assistants API
                file_id = self.file_manager.upload_file(file_path)
                file_ids.append(file_id)
                
                # Add to bundle metadata
                enhanced_metadata = metadata.copy()
                enhanced_metadata['file_id'] = file_id
                enhanced_metadata['agent'] = agent_name
                self.bundle_metadata.append(enhanced_metadata)
                
                logger.info(f"Uploaded {metadata['filename']} from {agent_name}: {file_id}")
                
            except Exception as e:
                logger.error(f"Error uploading {file_path}: {e}")
        
        return file_ids
    
    def create_bundle_summary(self, bundle_info: Dict[str, Any]) -> str:
        """
        Create a summary file for the entire data bundle.
        
        Args:
            bundle_info: Information about the bundle (timestamp, region, etc.)
            
        Returns:
            File ID of the summary file
        """
        summary = {
            'bundle_info': bundle_info,
            'agents': {},
            'files': self.bundle_metadata,
            'statistics': {
                'total_files': len(self.bundle_metadata),
                'agents': list(set(m['agent'] for m in self.bundle_metadata)),
                'data_types': list(set(m.get('type', 'unknown') for m in self.bundle_metadata))
            }
        }
        
        # Group files by agent
        for metadata in self.bundle_metadata:
            agent = metadata['agent']
            if agent not in summary['agents']:
                summary['agents'][agent] = []
            summary['agents'][agent].append(metadata)
        
        # Create metadata file
        return self.file_manager.create_data_bundle_metadata(
            [m['file_id'] for m in self.bundle_metadata],
            summary
        )
    
    def reset(self):
        """Reset the adapter for a new bundle."""
        self.bundle_metadata = []
    
    async def process_agent_async(self, agent_name: str, agent_coroutine,
                                 bundle_path: str) -> List[str]:
        """
        Process an async agent and upload its data.
        
        Args:
            agent_name: Name of the agent
            agent_coroutine: The agent coroutine to execute
            bundle_path: Path to the bundle directory
            
        Returns:
            List of uploaded file IDs
        """
        try:
            # Run the agent
            metadata_list = await agent_coroutine
            
            # Upload the files
            return self.add_agent_data(agent_name, metadata_list, bundle_path)
            
        except Exception as e:
            logger.error(f"Error processing agent {agent_name}: {e}")
            return []
    
    def get_file_ids_by_type(self, data_type: str) -> List[str]:
        """
        Get file IDs filtered by data type.
        
        Args:
            data_type: The data type to filter by
            
        Returns:
            List of file IDs matching the data type
        """
        return [
            m['file_id'] 
            for m in self.bundle_metadata 
            if m.get('type') == data_type
        ]
    
    def get_file_ids_by_agent(self, agent_name: str) -> List[str]:
        """
        Get file IDs filtered by agent.
        
        Args:
            agent_name: The agent name to filter by
            
        Returns:
            List of file IDs from the specified agent
        """
        return [
            m['file_id'] 
            for m in self.bundle_metadata 
            if m.get('agent') == agent_name
        ]
    
    def get_regional_file_ids(self, shore: str) -> List[str]:
        """
        Get file IDs relevant to a specific shore.
        
        Args:
            shore: "North Shore" or "South Shore"
            
        Returns:
            List of file IDs relevant to the shore
        """
        shore_tag = 'north_facing' if 'North' in shore else 'south_facing'
        
        relevant_files = []
        for metadata in self.bundle_metadata:
            # Include if specifically tagged for this shore
            if metadata.get(shore_tag, False):
                relevant_files.append(metadata['file_id'])
            # Include if not specifically tagged for either shore (general data)
            elif not metadata.get('north_facing', False) and not metadata.get('south_facing', False):
                relevant_files.append(metadata['file_id'])
        
        return relevant_files