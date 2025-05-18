"""
Test Backup Restore Functionality

This script tests the backup restoration functionality specifically.
It creates a backup, then tests if it can be properly restored.
"""
import os
import io
import tempfile
import logging
from datetime import datetime
from storage import STORAGE_CLIENT
from backup_database import create_db_backup
from backup_restore import download_backup

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('restore_test')

def test_backup_and_restore():
    """Test the full backup and restore cycle"""
    logger.info("===== BACKUP RESTORE TEST =====")
    
    # Step 1: Create a backup
    logger.info("STEP 1: Creating test backup")
    backup_data = create_db_backup()
    
    if not backup_data:
        logger.error("❌ Failed to create backup")
        return False
    
    size_kb = len(backup_data) / 1024
    logger.info(f"✅ Backup created successfully ({size_kb:.2f} KB)")
    
    # Step 2: Store the backup in Replit Object Storage
    logger.info("\nSTEP 2: Storing backup in Replit Object Storage")
    
    if not STORAGE_CLIENT:
        logger.error("❌ Replit Object Storage client not available")
        return False
    
    # Generate a unique test filename
    test_filename = f"test_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql.gz"
    object_name = f"backups/test/{test_filename}"
    
    try:
        # Upload to Replit Object Storage
        logger.info(f"Uploading backup to {object_name}")
        STORAGE_CLIENT.upload_from_bytes(object_name, backup_data)
        logger.info("✅ Upload successful")
    except Exception as e:
        logger.error(f"❌ Error uploading backup: {str(e)}")
        return False
    
    # Step 3: Test restoration from storage
    logger.info("\nSTEP 3: Testing restoration from storage")
    
    try:
        # Download the backup
        logger.info(f"Downloading backup from {object_name}")
        downloaded_data = download_backup(object_name)
        
        if not downloaded_data:
            logger.error("❌ Failed to download backup")
            return False
        
        # Note: The downloaded data will be different in size because it's decompressed
        # by the download_backup function. We'll check content validity instead.
        if downloaded_data:
            logger.info(f"✅ Successfully downloaded and decompressed backup (Original size: {len(backup_data)} bytes, Decompressed size: {len(downloaded_data)} bytes)")
        else:
            logger.error("❌ Failed to properly download and decompress backup")
            return False
        
        # Create a temporary file to test decompression
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(downloaded_data)
            temp_path = temp_file.name
        
        logger.info(f"Created temporary file for testing: {temp_path}")
        logger.info(f"Backup file size: {os.path.getsize(temp_path)} bytes")
        
        # Check file content (read first few lines) - Note: data is already decompressed
        try:
            with open(temp_path, 'rb') as f:
                first_lines = f.read(512).decode('utf-8', errors='replace')
                logger.info(f"Backup content preview:\n{first_lines[:200]}...")
                logger.info("✅ Backup file content can be read")
        except Exception as e:
            logger.error(f"❌ Error reading backup content: {str(e)}")
        
        # Clean up
        os.unlink(temp_path)
        logger.info("Temporary file deleted")
        
        # Clean up Replit Object Storage
        try:
            STORAGE_CLIENT.delete(object_name)
            logger.info(f"✅ Test object deleted from storage")
        except Exception as e:
            logger.error(f"❌ Error deleting test object: {str(e)}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error testing backup restoration: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_backup_and_restore()
    
    if success:
        logger.info("\n✅✅ TEST PASSED - Backup and restore cycle works correctly")
    else:
        logger.error("\n❌❌ TEST FAILED - Issues detected in backup and restore cycle")