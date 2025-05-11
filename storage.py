import os
import io
import uuid
import logging
import mimetypes
import requests
import json
from urllib.parse import urlparse, quote
from pathlib import Path
from google.cloud import storage
from google.oauth2 import service_account

# Initialize logger
logger = logging.getLogger(__name__)

# Google Cloud Storage Configuration
def get_gcs_client():
    """Get initialized Google Cloud Storage client with credentials from Replit Secrets"""
    try:
        # Get GCP credentials from environment
        gcp_credentials_json = os.environ.get('REPLIT_GCP_SERVICE_ACCOUNT_KEY')
        
        if not gcp_credentials_json:
            logger.warning("GCP credentials not found in environment variables, using local storage fallback")
            return None
        
        # Parse JSON credentials
        try:
            credentials_info = json.loads(gcp_credentials_json)
            credentials = service_account.Credentials.from_service_account_info(credentials_info)
        except json.JSONDecodeError:
            logger.error("Failed to parse GCP credentials JSON")
            return None
        
        # Initialize GCS client
        storage_client = storage.Client(credentials=credentials)
        
        # Get or create bucket
        bucket_name = os.environ.get('REPLIT_GCS_BUCKET_NAME', 'telegram-files')
        
        # Check if bucket exists, create if not
        bucket = None
        try:
            bucket = storage_client.get_bucket(bucket_name)
            logger.info(f"Connected to GCS bucket: {bucket_name}")
        except Exception:
            logger.info(f"Creating GCS bucket: {bucket_name}")
            try:
                bucket = storage_client.create_bucket(bucket_name)
            except Exception as e:
                logger.error(f"Error creating GCS bucket: {str(e)}")
                return None
                
        return {
            'client': storage_client,
            'bucket': bucket
        }
    except Exception as e:
        logger.error(f"Error initializing GCS client: {str(e)}")
        return None

# Global GCS client
GCS_CLIENT = get_gcs_client()

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
    Download a file from URL and save to storage
    
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
        
        # Determine if we should use GCS or local storage
        if GCS_CLIENT:
            # Store in GCS
            blob_name = f"media/{unique_filename}"
            blob = GCS_CLIENT['bucket'].blob(blob_name)
            
            # Set content type and upload
            blob.content_type = content_type
            file_data.seek(0)
            blob.upload_from_file(file_data)
            
            # Make the blob publicly accessible
            blob.make_public()
            
            logger.info(f"File uploaded to GCS: {blob_name}, size: {file_size} bytes, type: {media_type}")
            
            # Store GCS path
            stored_path = f"gcs://{GCS_CLIENT['bucket'].name}/{blob_name}"
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
    
    # Check if this is a GCS path
    if stored_path.startswith('gcs://'):
        # Parse GCS URL
        parts = stored_path.replace('gcs://', '').split('/', 1)
        if len(parts) != 2:
            logger.error(f"Invalid GCS path format: {stored_path}")
            return None
            
        bucket_name = parts[0]
        blob_name = parts[1]
        
        if GCS_CLIENT:
            # Get public URL for the blob
            try:
                blob = GCS_CLIENT['bucket'].blob(blob_name)
                url = blob.public_url
                return url
            except Exception as e:
                logger.error(f"Error generating public URL: {str(e)}")
                return None
        else:
            logger.warning(f"GCS client not available, can't generate URL for {stored_path}")
            return None
    else:
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
        # Check if this is a GCS path
        if stored_path.startswith('gcs://'):
            # Parse GCS URL
            parts = stored_path.replace('gcs://', '').split('/', 1)
            if len(parts) != 2:
                logger.error(f"Invalid GCS path format: {stored_path}")
                return False
                
            bucket_name = parts[0]
            blob_name = parts[1]
            
            if GCS_CLIENT:
                blob = GCS_CLIENT['bucket'].blob(blob_name)
                blob.delete()
                logger.info(f"Deleted file from GCS: {stored_path}")
                return True
            else:
                logger.warning(f"GCS client not available, can't delete {stored_path}")
                return False
        else:
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