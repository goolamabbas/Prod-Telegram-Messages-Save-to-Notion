import os
import io
import uuid
import logging
import mimetypes
import requests
from urllib.parse import urlparse, quote
from pathlib import Path
from replit.object_storage import Client

# Initialize logger
logger = logging.getLogger(__name__)

# Initialize Replit Object Storage client
def get_replit_client():
    """Get initialized Replit Object Storage client"""
    try:
        # Create a Client instance for Replit Object Storage
        client = Client()
        logger.info("Connected to Replit Object Storage")
        return client
    except Exception as e:
        logger.error(f"Error initializing Replit Object Storage: {str(e)}")
        return None

# Global Replit Object Storage client
STORAGE_CLIENT = get_replit_client()

# Ensure local media directory exists (as fallback)
def ensure_media_dir():
    """Ensure the media directory exists"""
    media_dir = os.path.join(os.getcwd(), 'media')
    os.makedirs(media_dir, exist_ok=True)
    return media_dir

def get_media_type(filename):
    """Determine media type from filename extension"""
    extension = os.path.splitext(filename)[1].lower()
    
    if extension in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']:
        return 'image'
    elif extension in ['.mp4', '.mov', '.avi', '.webm', '.mkv']:
        return 'video'
    elif extension in ['.mp3', '.wav', '.ogg', '.m4a', '.flac']:
        return 'audio'
    else:
        return 'document'

def ensure_media_dir():
    """Ensure the media directory exists (fallback for local storage)"""
    media_dir = os.path.join(os.getcwd(), 'media')
    os.makedirs(media_dir, exist_ok=True)
    return media_dir

def generate_unique_filename(original_filename):
    """Generate a unique filename with UUID to avoid collisions"""
    if not original_filename:
        # Default extension if none provided
        original_filename = "file.bin"
        
    # Extract the file extension
    _, extension = os.path.splitext(original_filename)
    if not extension:
        extension = ".bin"  # Default extension if none found
    
    # Create a unique filename with UUID and the original extension
    unique_filename = f"{uuid.uuid4().hex}{extension.lower()}"
    return unique_filename

def save_file_from_url(url, original_filename=None):
    """
    Download a file from URL and save to Replit Object Storage
    
    Args:
        url (str): URL of the file to download
        original_filename (str, optional): Original filename
        
    Returns:
        dict: File metadata including stored path, size, etc.
    """
    try:
        # Try to extract original filename from URL if not provided
        if not original_filename:
            parsed_url = urlparse(url)
            original_filename = os.path.basename(parsed_url.path)
        
        # Generate unique filename
        unique_filename = generate_unique_filename(original_filename)
        
        # Download file from URL
        logger.info(f"Downloading file from {url}")
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        # Get MIME type
        content_type = response.headers.get('Content-Type')
        if not content_type:
            # Try to guess MIME type from extension
            content_type, _ = mimetypes.guess_type(original_filename)
            if not content_type:
                content_type = 'application/octet-stream'
        
        # Determine media type from content type
        media_type = None
        if content_type.startswith('image/'):
            media_type = 'image'
        elif content_type.startswith('video/'):
            media_type = 'video'
        elif content_type.startswith('audio/'):
            media_type = 'audio'
        else:
            # Try to determine from filename
            media_type = get_media_type(original_filename)
        
        # Read file data into memory
        file_data = io.BytesIO()
        for chunk in response.iter_content(chunk_size=8192):
            file_data.write(chunk)
        
        file_data.seek(0)
        file_size = file_data.getbuffer().nbytes
        
        # Define object key for storage
        object_name = f"media/{unique_filename}"
        
        # Check if we can use Replit Object Storage
        if STORAGE_CLIENT:
            # Upload to Replit Object Storage
            file_data.seek(0)
            STORAGE_CLIENT.upload_from_bytes(object_name, file_data.getvalue())
            
            logger.info(f"File uploaded to Replit Object Storage: {object_name}, size: {file_size} bytes, type: {media_type}")
            
            # Store Replit Object Storage path
            stored_path = f"replit://{object_name}"
        else:
            # Fallback to local storage
            media_dir = ensure_media_dir()
            file_path = os.path.join(media_dir, unique_filename)
            relative_path = os.path.join('media', unique_filename)
            
            with open(file_path, 'wb') as f:
                file_data.seek(0)
                f.write(file_data.read())
            
            logger.info(f"File saved to local storage: {file_path}, size: {file_size} bytes, type: {media_type}")
            
            # Store local path
            stored_path = relative_path
        
        # Return file metadata
        return {
            'stored_path': stored_path,
            'size': file_size,
            'media_type': media_type,
            'content_type': content_type,
            'original_filename': original_filename,
            'filename': unique_filename
        }
        
    except Exception as e:
        logger.error(f"Error saving file from URL {url}: {str(e)}")
        return None

def get_file_url(stored_path):
    """
    Get the full URL for accessing a stored file
    
    Args:
        stored_path (str): The path where the file is stored
        
    Returns:
        str: The full URL to access the file
    """
    if not stored_path:
        return None
    
    # Local path, generate URL
    try:
        from flask import request
        base_url = request.host_url.rstrip('/')
        return f"{base_url}/{stored_path}"
    except:
        # Fallback to just the path
        return f"/{stored_path}"

def delete_file(stored_path):
    """
    Delete a stored file
    
    Args:
        stored_path (str): The path where the file is stored
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Local storage path
        full_path = os.path.join(os.getcwd(), stored_path)
        
        # Check if file exists
        if os.path.exists(full_path):
            os.remove(full_path)
            logger.info(f"Deleted file {full_path}")
            return True
        else:
            logger.warning(f"File not found: {full_path}")
            return False
    except Exception as e:
        logger.error(f"Error deleting file {stored_path}: {str(e)}")
        return False