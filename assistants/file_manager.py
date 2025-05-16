"""
File Manager for SwellForecaster V3.

This module handles file uploads, management, and tracking for the OpenAI Assistants API.
"""

import os
import mimetypes
from typing import List, Dict, Optional, Tuple
from openai import OpenAI
from logging_config import get_logger

logger = get_logger(__name__)


class FileManager:
    """
    Manages file uploads and tracking for OpenAI Assistants.
    """
    
    def __init__(self, client: OpenAI):
        """
        Initialize the FileManager.
        
        Args:
            client: OpenAI client instance
        """
        self.client = client
        self.uploaded_files: Dict[str, str] = {}  # local_path -> file_id
        self.file_metadata: Dict[str, Dict] = {}  # file_id -> metadata
    
    def upload_file(self, file_path: str, purpose: str = "assistants") -> str:
        """
        Upload a file to OpenAI.
        
        Args:
            file_path: Path to the file to upload
            purpose: Upload purpose (default: "assistants")
            
        Returns:
            File ID
            
        Raises:
            FileNotFoundError: If file doesn't exist
            Exception: If upload fails
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Check if file was already uploaded
        if file_path in self.uploaded_files:
            file_id = self.uploaded_files[file_path]
            logger.info(f"File already uploaded: {file_path} -> {file_id}")
            return file_id
        
        try:
            # Determine file type
            mime_type, _ = mimetypes.guess_type(file_path)
            file_size = os.path.getsize(file_path)
            
            logger.info(f"Uploading file: {file_path} ({file_size} bytes, {mime_type})")
            
            with open(file_path, 'rb') as f:
                file_obj = self.client.files.create(
                    file=f,
                    purpose=purpose
                )
            
            file_id = file_obj.id
            self.uploaded_files[file_path] = file_id
            self.file_metadata[file_id] = {
                'local_path': file_path,
                'size': file_size,
                'mime_type': mime_type,
                'filename': os.path.basename(file_path)
            }
            
            logger.info(f"Successfully uploaded: {file_path} -> {file_id}")
            return file_id
            
        except Exception as e:
            logger.error(f"Error uploading file {file_path}: {e}")
            raise
    
    def upload_files(self, file_paths: List[str]) -> List[str]:
        """
        Upload multiple files.
        
        Args:
            file_paths: List of file paths to upload
            
        Returns:
            List of file IDs
        """
        file_ids = []
        
        for file_path in file_paths:
            try:
                file_id = self.upload_file(file_path)
                file_ids.append(file_id)
            except Exception as e:
                logger.error(f"Failed to upload {file_path}: {e}")
                # Continue with other files
        
        return file_ids
    
    def upload_directory(self, directory_path: str, 
                        extensions: Optional[List[str]] = None) -> List[str]:
        """
        Upload all files from a directory.
        
        Args:
            directory_path: Path to directory
            extensions: Optional list of file extensions to include
            
        Returns:
            List of file IDs
        """
        if not os.path.isdir(directory_path):
            raise ValueError(f"Not a directory: {directory_path}")
        
        file_paths = []
        
        for filename in os.listdir(directory_path):
            file_path = os.path.join(directory_path, filename)
            
            if not os.path.isfile(file_path):
                continue
            
            if extensions:
                _, ext = os.path.splitext(filename)
                if ext.lower() not in extensions:
                    continue
            
            file_paths.append(file_path)
        
        logger.info(f"Found {len(file_paths)} files to upload from {directory_path}")
        return self.upload_files(file_paths)
    
    def delete_file(self, file_id: str):
        """
        Delete a file from OpenAI.
        
        Args:
            file_id: File ID to delete
        """
        try:
            self.client.files.delete(file_id)
            
            # Remove from tracking
            if file_id in self.file_metadata:
                local_path = self.file_metadata[file_id]['local_path']
                if local_path in self.uploaded_files:
                    del self.uploaded_files[local_path]
                del self.file_metadata[file_id]
            
            logger.info(f"Deleted file: {file_id}")
        except Exception as e:
            logger.warning(f"Error deleting file {file_id}: {e}")
    
    def cleanup_files(self):
        """Delete all tracked files."""
        file_ids = list(self.file_metadata.keys())
        
        for file_id in file_ids:
            self.delete_file(file_id)
        
        self.uploaded_files.clear()
        self.file_metadata.clear()
        logger.info("Cleaned up all files")
    
    def get_file_info(self, file_id: str) -> Optional[Dict]:
        """
        Get metadata for a file.
        
        Args:
            file_id: File ID
            
        Returns:
            File metadata dict or None if not found
        """
        return self.file_metadata.get(file_id)
    
    def list_files(self) -> List[Tuple[str, str]]:
        """
        List all uploaded files.
        
        Returns:
            List of (local_path, file_id) tuples
        """
        return list(self.uploaded_files.items())
    
    def create_data_bundle_metadata(self, file_ids: List[str], 
                                  bundle_info: Dict) -> str:
        """
        Create a metadata file for a data bundle.
        
        Args:
            file_ids: List of file IDs in the bundle
            bundle_info: Additional bundle information
            
        Returns:
            File ID of the metadata file
        """
        import json
        import tempfile
        
        metadata = {
            'bundle_info': bundle_info,
            'files': []
        }
        
        for file_id in file_ids:
            file_info = self.get_file_info(file_id)
            if file_info:
                metadata['files'].append({
                    'file_id': file_id,
                    'filename': file_info['filename'],
                    'size': file_info['size'],
                    'mime_type': file_info['mime_type']
                })
        
        # Create temporary metadata file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(metadata, f, indent=2)
            temp_path = f.name
        
        try:
            # Upload metadata file
            metadata_file_id = self.upload_file(temp_path)
            return metadata_file_id
        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)