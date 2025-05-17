"""Utility functions for downloading and saving images in agents."""
import aiohttp
import asyncio
from typing import Optional, Dict, Any
import logging
from pathlib import Path
import mimetypes

logger = logging.getLogger(__name__)

async def download_image(url: str, session: aiohttp.ClientSession, filename: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Download an image from a URL and return its content.
    
    Args:
        url: URL of the image to download
        session: aiohttp session for making requests
        filename: Optional filename to use (will be inferred from URL if not provided)
    
    Returns:
        Dictionary with image data and metadata, or None if failed
    """
    try:
        logger.info(f"Downloading image from {url}")
        
        # Extract filename from URL if not provided
        if not filename:
            filename = url.split('/')[-1]
            if not filename or '.' not in filename:
                filename = 'image.gif'  # Default fallback
        
        # Attempt to download with SSL verification disabled for problematic sites
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as temp_session:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            
            async with temp_session.get(url, headers=headers, timeout=30) as response:
                if response.status == 200:
                    content = await response.read()
                    content_type = response.headers.get('Content-Type', 'image/gif')
                    
                    # Determine extension from content type if needed
                    if not Path(filename).suffix:
                        ext = mimetypes.guess_extension(content_type) or '.gif'
                        filename = f"{filename}{ext}"
                    
                    logger.info(f"Successfully downloaded {filename} ({len(content)} bytes)")
                    
                    return {
                        'filename': filename,
                        'content': content,
                        'content_type': content_type,
                        'url': url,
                        'size': len(content)
                    }
                else:
                    logger.warning(f"Failed to download {url}: HTTP {response.status}")
                    return None
                    
    except asyncio.TimeoutError:
        logger.error(f"Timeout downloading image from {url}")
        return None
    except Exception as e:
        logger.error(f"Error downloading image from {url}: {str(e)}")
        return None

async def save_image(ctx, image_data: Dict[str, Any]) -> bool:
    """
    Save image data using the context's save method.
    
    Args:
        ctx: Agent context with save method
        image_data: Dictionary with image content and metadata
    
    Returns:
        True if saved successfully, False otherwise
    """
    try:
        filename = image_data['filename']
        content = image_data['content']
        
        # Save the binary image data
        await ctx.save(filename, content, binary=True)
        
        # Also save metadata about the image
        metadata = {
            'url': image_data['url'],
            'content_type': image_data['content_type'],
            'size': image_data['size'],
            'filename': filename
        }
        
        metadata_filename = f"{Path(filename).stem}_metadata.json"
        import json
        await ctx.save(metadata_filename, json.dumps(metadata, indent=2))
        
        logger.info(f"Saved image {filename} and metadata")
        return True
        
    except Exception as e:
        logger.error(f"Error saving image: {str(e)}")
        return False

async def download_and_save_images(ctx, image_urls: Dict[str, str], session: aiohttp.ClientSession) -> Dict[str, bool]:
    """
    Download multiple images and save them.
    
    Args:
        ctx: Agent context with save method
        image_urls: Dictionary mapping image names to URLs
        session: aiohttp session for making requests
    
    Returns:
        Dictionary mapping image names to success status
    """
    results = {}
    
    for name, url in image_urls.items():
        image_data = await download_image(url, session, filename=f"{name}.gif")
        if image_data:
            success = await save_image(ctx, image_data)
            results[name] = success
        else:
            results[name] = False
    
    return results