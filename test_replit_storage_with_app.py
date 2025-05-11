import logging
import requests
from app import app
from storage import STORAGE_CLIENT, save_file_from_url, get_file_url, delete_file

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_replit_storage():
    """Test Replit Object Storage integration with application context"""
    
    # Check if client is available
    if not STORAGE_CLIENT:
        logger.error("Replit Object Storage client not available")
        return False
    
    with app.app_context():
        try:
            # Test file URL (public domain image)
            test_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2f/Google_2015_logo.svg/500px-Google_2015_logo.svg.png"
            
            # Save file from URL
            logger.info(f"Saving file from URL: {test_url}")
            file_info = save_file_from_url(test_url, "test_logo.png")
            
            if not file_info:
                logger.error("Failed to save file from URL")
                return False
            
            logger.info(f"File saved successfully: {file_info}")
            
            # Get file URL
            stored_path = file_info['stored_path']
            file_url = get_file_url(stored_path)
            
            logger.info(f"File URL: {file_url}")
            
            # Clean up
            if stored_path:
                logger.info(f"Deleting file: {stored_path}")
                deleted = delete_file(stored_path)
                logger.info(f"File deleted: {deleted}")
            
            return True
        
        except Exception as e:
            logger.error(f"Error testing Replit Object Storage: {str(e)}")
            return False

if __name__ == "__main__":
    test_replit_storage()