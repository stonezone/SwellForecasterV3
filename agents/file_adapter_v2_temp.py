"""
File Adapter V2 for SwellForecaster V3.

Enhanced to handle binary files (images) and improved file type detection.
"""

import os
import json
import asyncio
from typing import List, Dict, Any, Optional
from configparser import ConfigParser
from pathlib import Path
from assistants.file_manager import FileManager
from logging_config import get_logger

logger = get_logger(__name__)


class FileAdapter:
    """
    Bridges the gap between existing agents and the Assistants API file system.
    Enhanced to handle binary files like images.
    """
    
    def __init__(self, config: ConfigParser):
        """
        Initialize the FileAdapter.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.file_manager = FileManager(config)
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
            # Determine if file is binary
            is_binary = self.is_binary_file(filepath)
            
            # Read file content appropriately
            if is_binary:
                with open(filepath, 'rb') as f:
                    content = f.read()
                logger.info(f"Uploading binary file: {os.path.basename(filepath)}")
            else:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                logger.info(f"Uploading text file: {os.path.basename(filepath)}")
            
            # Upload to API
            file_obj = await self.file_manager.create_file(content, purpose)
            
            if file_obj and hasattr(file_obj, 'id'):
                logger.info(f"Successfully uploaded {os.path.basename(filepath)} with ID: {file_obj.id}")
                return file_obj.id
            else:
                logger.error(f"Failed to get file ID for {filepath}")
                return None
                
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
                if filename in ['bundle_metadata.json', 'failure_summary.json']:
                    continue
                    
                # Skip metadata files for images (they're included in the main data files)
                if filename.endswith('_metadata.json') and any(
                    filename.startswith(img_name) for img_name in 
                    ['sst_anomaly', 'subsurface', 'pacific_', 'trade_wind']
                ):
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
            
            # Upload the bundle metadata itself
            metadata_path = os.path.join(bundle_path, "bundle_metadata.json")
            if os.path.exists(metadata_path):
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