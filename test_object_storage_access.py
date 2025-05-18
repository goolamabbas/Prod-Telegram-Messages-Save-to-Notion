"""
Test Replit Object Storage Access

This script tests if the application can access Replit Object Storage
and reports any permission or configuration issues.
"""
import os
import logging
from storage import STORAGE_CLIENT, get_replit_client

# Configure logging
logging.basicConfig(level=logging.INFO,
                  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('storage_test')

def test_object_storage_access():
    """Test if Replit Object Storage is accessible"""
    logger.info("Testing Replit Object Storage access...")
    
    # Check if the client is initialized
    client = STORAGE_CLIENT
    if not client:
        logger.error("❌ Replit Object Storage client is not initialized")
        # Try to initialize it again and check for specific errors
        logger.info("Attempting to initialize client again for detailed error...")
        client = get_replit_client()
        return False
    
    # Try to list objects
    try:
        logger.info("Listing objects in storage...")
        objects = client.list()
        if isinstance(objects, list):
            logger.info(f"✅ Successfully listed objects: {len(objects)} objects found")
            
            # Print the first few objects for debugging
            if objects:
                logger.info(f"Sample objects: {objects[:5] if len(objects) > 5 else objects}")
            else:
                logger.info("Storage appears to be empty (no objects found)")
            
            return True
        else:
            logger.error(f"❌ Unexpected response when listing objects: {objects}")
            return False
    except Exception as e:
        logger.error(f"❌ Error accessing Replit Object Storage: {str(e)}")
        # Try to get more specific error info
        logger.info("Checking environment variables for diagnosis...")
        logger.info(f"REPLIT_DB_URL set: {'Yes' if os.environ.get('REPLIT_DB_URL') else 'No'}")
        logger.info(f"Is running in Replit: {'Yes' if os.environ.get('REPL_ID') and os.environ.get('REPL_OWNER') else 'No'}")
        return False

def test_object_storage_write():
    """Test if we can write to Replit Object Storage"""
    if not STORAGE_CLIENT:
        logger.error("❌ Client not available, skipping write test")
        return False
    
    try:
        logger.info("Testing writing to Replit Object Storage...")
        test_data = b"Hello, this is a test of Replit Object Storage!"
        test_key = "test/hello_test.txt"
        
        # Upload the test data
        logger.info(f"Uploading test data to {test_key}...")
        STORAGE_CLIENT.upload_from_bytes(test_key, test_data)
        logger.info("✅ Upload successful")
        
        # Verify by downloading
        try:
            logger.info("Downloading test data to verify...")
            downloaded = STORAGE_CLIENT.download_as_bytes(test_key)
            if downloaded == test_data:
                logger.info("✅ Download verification successful - content matches")
            else:
                logger.error(f"❌ Downloaded data does not match: {downloaded[:20]}...")
            
            # Clean up test file
            logger.info("Cleaning up test file...")
            STORAGE_CLIENT.delete(test_key)
            logger.info("✅ Cleanup successful")
            
            return True
        except Exception as e:
            logger.error(f"❌ Error verifying test data: {str(e)}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error writing to Replit Object Storage: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("===== Replit Object Storage Test =====")
    access_ok = test_object_storage_access()
    
    if access_ok:
        write_ok = test_object_storage_write()
        
        if access_ok and write_ok:
            logger.info("✅✅ ALL TESTS PASSED - Replit Object Storage is working correctly")
        else:
            logger.warning("⚠️ PARTIAL SUCCESS - Can list objects but not write to storage")
    else:
        logger.error("❌❌ TEST FAILED - Cannot access Replit Object Storage")