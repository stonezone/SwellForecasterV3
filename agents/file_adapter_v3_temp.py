"""
File Adapter V3 for SwellForecaster V3.

Fixed to use the correct FileManager upload_file method.
"""

import os
import json
import asyncio
from typing import List, Dict, Any, Optional
from configparser import ConfigParser
from pathlib import Path
from assistants.file_manager import FileManager
from openai import OpenAI
from logging_config import get_logger

logger = get_logger(__name__)


class FileAdapter:
    """
    Bridges the gap between existing agents and the Assistants API file system.
    Fixed to use correct FileManager methods.
    """
    
    def __init__(self, config: ConfigParser):
        """
        Initialize the FileAdapter.
        
        Args:
            config: Configuration object
        """
        self.config = config
        # Create OpenAI client
        api_key = config.get('openai', 'api_key')
        self.client = OpenAI(api_key=api_key)
        # Create FileManager with client
        self.file_manager = FileManager(self.client)
        self.bundle_metadata: List[Dict[str, Any]] = []
    
    def is_binary_file(self, filename: str) -> bool:
        """
        Determine if a file should be treated as binary based on extension.
        
        Args:
            filename: Name of the file
            
        Returns:
            True if file should be treated as binary
        """
        binary_extensions = {'.gif', '.jpg', '.jpeg', '.png', '.bmp', '.tiff', 
                           '.webp', '.ico', '.pdf', '.zip', '.tar', '.gz'}
        
        file_ext = Path(filename).suffix.lower()
        return file_ext in binary_extensions
    
    async def upload_file(self, filepath: str, purpose: str = "assistants") -> Optional[str]:
        """
        Upload a single file to the Assistants API.
        
        Args:
            filepath: Path to the file
            purpose: Purpose of the file upload
            
        Returns:
            File ID if successful, None otherwise
        """
        try:
            # Use the synchronous upload_file method
            file_id = self.file_manager.upload_file(filepath, purpose)
            logger.info(f"Successfully uploaded {os.path.basename(filepath)} with ID: {file_id}")
            return file_id
                
        except Exception as e:
            logger.error(f"Error uploading file {filepath}: {str(e)}")
            return None
    
    async def upload_bundle(self, bundle_path: str, bundle_metadata: Dict[str, Any]) -> List[str]:
        """
        Upload all files in a bundle to the Assistants API.
        
        Args:
            bundle_path: Path to the bundle directory
            bundle_metadata: Metadata about the bundle
            
        Returns:
            List of uploaded file IDs
        """
        file_ids = []
        
        try:
            # Get all files in the bundle directory
            all_files = []
            for root, dirs, files in os.walk(bundle_path):
                for file in files:
                    filepath = os.path.join(root, file)
                    all_files.append(filepath)
            
            logger.info(f"Found {len(all_files)} files in bundle {bundle_path}")
            
            # Upload each file
            for filepath in all_files:
                # Skip certain files
                filename = os.path.basename(filepath)
                
                # Skip metadata files for images (they're included in the main data files)
                if filename.endswith('_metadata.json') and any(
                    part in filename.lower() for part in 
                    ['sst_anomaly', 'subsurface', 'pacific_', 'trade_wind', 'ocean', 
                     'surface', 'wave', 'wind', '500mb', 'satellite', 'ir']
                ):
                    logger.info(f"Skipping image metadata file: {filename}")
                    continue
                
                # Skip failure summary - it should be included in bundle metadata
                if filename == 'failure_summary.json':
                    logger.info(f"Skipping failure summary file: {filename}")
                    continue
                
                file_id = await self.upload_file(filepath)
                if file_id:
                    file_ids.append(file_id)
                    
                    # Add to bundle metadata
                    self.bundle_metadata.append({
                        'file_id': file_id,
                        'filename': filename,
                        'filepath': filepath,
                        'is_binary': self.is_binary_file(filename),
                        'bundle_id': bundle_metadata.get('bundle_id')
                    })
                    
            # Upload the bundle metadata itself last
            metadata_path = os.path.join(bundle_path, "bundle_metadata.json")
            if os.path.exists(metadata_path):
                # Ensure the bundle metadata includes all file IDs
                bundle_metadata['uploaded_file_ids'] = file_ids
                with open(metadata_path, 'w') as f:
                    json.dump(bundle_metadata, f, indent=2)
                    
                metadata_id = await self.upload_file(metadata_path)
                if metadata_id:
                    file_ids.append(metadata_id)
            
            logger.info(f"Successfully uploaded {len(file_ids)} files from bundle")
            
        except Exception as e:
            logger.error(f"Error uploading bundle: {str(e)}")
        
        return file_ids
    
    def get_bundle_metadata(self) -> List[Dict[str, Any]]:
        """
        Get the collected bundle metadata.
        
        Returns:
            List of metadata dictionaries
        """
        return self.bundle_metadata
    
    def clear_metadata(self):
        """Clear the collected metadata."""
        self.bundle_metadata = []