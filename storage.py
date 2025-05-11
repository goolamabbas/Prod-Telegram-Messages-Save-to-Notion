import os
import uuid
import logging
import requests
from datetime import datetime
from flask import url_for, current_app

# Set up logger
logger = logging.getLogger('storage')
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(console_handler)
    logger.setLevel(logging.INFO)

# Constants
MEDIA_DIR = 'media'
ALLOWED_MEDIA_TYPES = {
    'image': ['.jpg', '.jpeg', '.png', '.gif', '.webp'],
    'video': ['.mp4', '.avi', '.mov', '.webm'],
    'audio': ['.mp3', '.ogg', '.wav', '.m4a'],
    'document': ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt']
}

def get_media_type(filename):
    """Determine media type from filename extension"""
    ext = os.path.splitext(filename.lower())[1]
    
    for media_type, extensions in ALLOWED_MEDIA_TYPES.items():
        if ext in extensions:
            return media_type
    
    return 'document'  # Default to document for unknown types

def ensure_media_dir():
    """Ensure the media directory exists"""
    media_path = os.path.join(os.getcwd(), MEDIA_DIR)
    if not os.path.exists(media_path):
        os.makedirs(media_path)
        logger.info(f"Created media directory: {media_path}")
    return media_path

def generate_unique_filename(original_filename):
    """Generate a unique filename with UUID to avoid collisions"""
    # Keep the original extension
    ext = os.path.splitext(original_filename)[1]
    # Generate a UUID and use it as filename
    return f"{uuid.uuid4()}{ext}"

def save_file_from_url(url, original_filename=None):
    """
    Download a file from URL and save to Replit storage
    
    Args:
        url (str): URL of the file to download
        original_filename (str, optional): Original filename
        
    Returns:
        dict: File metadata including stored path, size, etc.
    """
    try:
        # If no original filename is provided, extract from URL
        if not original_filename:
            original_filename = os.path.basename(url)
        
        # Generate unique filename
        unique_filename = generate_unique_filename(original_filename)
        
        # Ensure media directory exists
        media_path = ensure_media_dir()
        
        # Full path where file will be saved
        file_path = os.path.join(media_path, unique_filename)
        
        # Download file
        logger.info(f"Downloading file from {url}")
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Raise exception for HTTP errors
        
        # Get content type from response headers
        content_type = response.headers.get('Content-Type', 'application/octet-stream')
        
        # Save file to disk
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Get file size
        file_size = os.path.getsize(file_path)
        
        # Determine media type
        media_type = get_media_type(original_filename)
        
        logger.info(f"Saved file to {file_path} ({file_size} bytes)")
        
        # Return metadata
        return {
            'stored_path': os.path.join(MEDIA_DIR, unique_filename),
            'media_type': media_type,
            'content_type': content_type,
            'size': file_size,
            'original_filename': original_filename,
            'unique_filename': unique_filename,
            'stored_at': datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error saving file from URL: {str(e)}")
        return None

def get_file_url(stored_path):
    """
    Get the full URL for accessing a stored file
    
    Args:
        stored_path (str): The path where the file is stored
        
    Returns:
        str: The full URL to access the file
    """
    try:
        # Get the Replit domain from environment
        replit_domain = os.environ.get('REPLIT_DOMAIN')
        
        if not replit_domain:
            # If running in development, use the Flask app's URL
            if current_app:
                # If we're in a Flask context, use url_for
                base_url = url_for('index', _external=True)
                base_url = base_url.rstrip('/')
            else:
                # Fallback to localhost
                base_url = 'http://localhost:5000'
        else:
            # Using Replit domain
            base_url = f"https://{replit_domain}"
        
        # Return the complete URL
        return f"{base_url}/{stored_path}"
    
    except Exception as e:
        logger.error(f"Error generating file URL: {str(e)}")
        return None

def delete_file(stored_path):
    """
    Delete a stored file
    
    Args:
        stored_path (str): The path where the file is stored
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get absolute path
        abs_path = os.path.join(os.getcwd(), stored_path)
        
        # Check if file exists
        if os.path.exists(abs_path):
            # Delete the file
            os.remove(abs_path)
            logger.info(f"Deleted file: {abs_path}")
            return True
        else:
            logger.warning(f"File not found for deletion: {abs_path}")
            return False
    
    except Exception as e:
        logger.error(f"Error deleting file: {str(e)}")
        return False