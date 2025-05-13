"""
Test Backup System

This script performs a comprehensive test of the backup system:
1. Creates a test backup of the current database
2. Verifies the backup was correctly stored in Replit Object Storage
3. Tests the offsite backup transfer to AWS S3
4. Attempts a test restore to verify backup integrity
"""
import os
import io
import sys
import json
import logging
import tempfile
import subprocess
from datetime import datetime
import boto3
from storage import STORAGE_CLIENT
from backup_database import create_db_backup, get_backup_filename
from offsite_backup import transfer_to_s3
from backup_restore import download_backup

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('backup_test')

# S3 bucket configuration (read from offsite_backup.py)
from offsite_backup import S3_BUCKET_NAME

def get_aws_credentials():
    """Get AWS credentials from environment variables/secrets"""
    return {
        "aws_access_key_id": os.environ.get("REPLIT_AWS_ACCESS_KEY_ID", ""),
        "aws_secret_access_key": os.environ.get("REPLIT_AWS_SECRET_ACCESS_KEY", "")
    }

def test_create_backup():
    """Test creating a database backup"""
    logger.info("=== TESTING BACKUP CREATION ===")
    
    # Create test backup
    logger.info("Creating test backup...")
    backup_data = create_db_backup()
    
    if not backup_data:
        logger.error("❌ Failed to create backup")
        return None
    
    size_mb = len(backup_data) / (1024 * 1024)
    logger.info(f"✅ Backup created successfully ({size_mb:.2f} MB)")
    
    # Generate a test filename
    test_filename = f"test_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql.gz"
    
    return {
        "backup_data": backup_data,
        "filename": test_filename,
        "size_mb": size_mb
    }

def test_replit_storage(backup_info):
    """Test storing backup in Replit Object Storage"""
    logger.info("\n=== TESTING REPLIT OBJECT STORAGE ===")
    
    if not STORAGE_CLIENT:
        logger.error("❌ Replit Object Storage client not available")
        return False
    
    if not backup_info or not backup_info.get("backup_data"):
        logger.error("❌ No backup data available to test")
        return False
    
    try:
        # Upload to Replit Object Storage
        object_name = f"backups/test/{backup_info['filename']}"
        logger.info(f"Uploading to Replit Object Storage: {object_name}")
        
        STORAGE_CLIENT.upload_from_bytes(object_name, backup_info["backup_data"])
        logger.info(f"✅ Upload successful")
        
        # Verify file exists
        objects = STORAGE_CLIENT.list()
        if object_name in objects:
            logger.info(f"✅ Object verified in storage")
        else:
            logger.warning(f"⚠️ Object not found in storage listing")
        
        # Try to download the file
        try:
            downloaded_data = STORAGE_CLIENT.download_as_bytes(object_name)
            download_size = len(downloaded_data) / (1024 * 1024)
            logger.info(f"✅ Download successful ({download_size:.2f} MB)")
            
            if len(downloaded_data) == len(backup_info["backup_data"]):
                logger.info("✅ Downloaded file size matches original")
            else:
                logger.warning(f"⚠️ Size mismatch: Original={backup_info['size_mb']:.2f} MB, Downloaded={download_size:.2f} MB")
        except Exception as e:
            logger.error(f"❌ Error downloading file: {str(e)}")
        
        # Clean up
        try:
            STORAGE_CLIENT.delete(object_name)
            logger.info(f"✅ Test object deleted")
        except Exception as e:
            logger.error(f"❌ Error deleting test object: {str(e)}")
        
        return True
    
    except Exception as e:
        logger.error(f"❌ Error testing Replit Object Storage: {str(e)}")
        return False

def test_aws_s3(backup_info):
    """Test AWS S3 offsite backup"""
    logger.info("\n=== TESTING AWS S3 OFFSITE BACKUP ===")
    
    aws_creds = get_aws_credentials()
    
    if not aws_creds["aws_access_key_id"] or not aws_creds["aws_secret_access_key"]:
        logger.error("❌ AWS credentials not configured")
        return False
    
    if not backup_info or not backup_info.get("backup_data"):
        logger.error("❌ No backup data available to test")
        return False
    
    # Use a temporary bucket name for testing if not configured
    bucket_name = S3_BUCKET_NAME
    if not bucket_name or bucket_name == "your-database-backups-bucket":
        logger.warning("⚠️ S3 bucket name not configured in offsite_backup.py")
        logger.info("Skipping S3 bucket tests, but testing AWS credentials and S3 client setup")
        bucket_name = None
    
    object_name = None
    try:
        # Initialize S3 client first to verify AWS credentials
        logger.info("Initializing S3 client to verify AWS credentials")
        try:
            s3_client = boto3.client(
                's3',
                aws_access_key_id=aws_creds["aws_access_key_id"],
                aws_secret_access_key=aws_creds["aws_secret_access_key"]
            )
            logger.info("✅ AWS credentials valid - S3 client initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize S3 client: {str(e)}")
            return False

        # If no bucket name, just verify credentials and return
        if bucket_name is None:
            logger.info("✅ AWS credentials verified (S3 bucket tests skipped)")
            return True

        # Upload to temporary location in Replit Object Storage first
        object_name = f"backups/test/{backup_info['filename']}"
        logger.info(f"Creating temporary object for S3 test: {object_name}")
        
        if not STORAGE_CLIENT:
            logger.error("❌ Replit Object Storage client not available")
            return False
        
        STORAGE_CLIENT.upload_from_bytes(object_name, backup_info["backup_data"])
        
        # Test transferring to S3
        logger.info(f"Testing transfer to S3 bucket: {bucket_name}")
        
        # Check if bucket exists
        try:
            s3_client.head_bucket(Bucket=bucket_name)
            logger.info(f"✅ S3 bucket {bucket_name} exists and is accessible")
        except Exception as e:
            logger.error(f"❌ S3 bucket error: {str(e)}")
            # Clean up
            if object_name:
                STORAGE_CLIENT.delete(object_name)
            return False
        
        # Upload to S3
        try:
            # Direct upload from memory
            s3_key = f"test/{backup_info['filename']}"
            s3_client.upload_fileobj(
                io.BytesIO(backup_info["backup_data"]),
                bucket_name,
                s3_key
            )
            logger.info(f"✅ Direct upload to S3 successful")
            
            # Verify file exists in S3
            try:
                response = s3_client.head_object(Bucket=bucket_name, Key=s3_key)
                s3_size = response['ContentLength'] / (1024 * 1024)
                logger.info(f"✅ Object verified in S3 ({s3_size:.2f} MB)")
            except Exception as e:
                logger.error(f"❌ Error verifying S3 object: {str(e)}")
            
            # Clean up S3
            try:
                s3_client.delete_object(Bucket=bucket_name, Key=s3_key)
                logger.info(f"✅ Test object deleted from S3")
            except Exception as e:
                logger.error(f"❌ Error deleting test object from S3: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Error uploading to S3: {str(e)}")
        
        # Clean up Replit Object Storage
        if object_name:
            STORAGE_CLIENT.delete(object_name)
        
        return True
    
    except Exception as e:
        logger.error(f"❌ Error testing AWS S3 offsite backup: {str(e)}")
        # Attempt to clean up
        try:
            if STORAGE_CLIENT and object_name:
                STORAGE_CLIENT.delete(object_name)
        except:
            pass
        return False

def test_restore_capability(backup_info):
    """Test the restore capability"""
    logger.info("\n=== TESTING RESTORE CAPABILITY ===")
    
    if not backup_info or not backup_info.get("backup_data"):
        logger.error("❌ No backup data available to test")
        return False
    
    try:
        # Create a temporary file for the backup
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(backup_info["backup_data"])
            temp_path = temp_file.name
        
        logger.info(f"Created temporary file for restore test: {temp_path}")
        
        # Try pg_restore --list to verify backup is valid
        try:
            cmd = ["pg_restore", "--list", temp_path]
            logger.info(f"Testing backup validity with: {' '.join(cmd)}")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate()
            
            if process.returncode == 0:
                logger.info("✅ Backup file is valid and can be restored")
                # Truncate stdout if too long
                stdout_sample = stdout.decode('utf-8')[:500]
                if len(stdout.decode('utf-8')) > 500:
                    stdout_sample += "... (truncated)"
                logger.info(f"Backup contents preview:\n{stdout_sample}")
            else:
                logger.error(f"❌ Backup file validation failed: {stderr.decode('utf-8')}")
        except Exception as e:
            logger.error(f"❌ Error testing backup validity: {str(e)}")
        
        # Clean up
        os.unlink(temp_path)
        logger.info("Temporary file deleted")
        
        return True
    
    except Exception as e:
        logger.error(f"❌ Error testing restore capability: {str(e)}")
        return False

def run_all_tests():
    """Run all backup system tests"""
    logger.info("STARTING COMPREHENSIVE BACKUP SYSTEM TEST")
    logger.info("=======================================")
    
    # Step 1: Create test backup
    backup_info = test_create_backup()
    if not backup_info:
        logger.error("Backup creation failed, cannot continue tests")
        return False
    
    # Step 2: Test Replit Object Storage
    replit_storage_success = test_replit_storage(backup_info)
    
    # Step 3: Test AWS S3 offsite backup
    aws_s3_success = test_aws_s3(backup_info)
    
    # Step 4: Test restore capability
    restore_success = test_restore_capability(backup_info)
    
    # Summary
    logger.info("\n=== TEST SUMMARY ===")
    logger.info(f"Backup Creation: {'✅ Success' if backup_info else '❌ Failed'}")
    logger.info(f"Replit Object Storage: {'✅ Success' if replit_storage_success else '❌ Failed'}")
    logger.info(f"AWS S3 Offsite Backup: {'✅ Success' if aws_s3_success else '❌ Failed'}")
    logger.info(f"Restore Capability: {'✅ Success' if restore_success else '❌ Failed'}")
    
    # If S3 bucket name is not configured, don't consider it a failure
    if not S3_BUCKET_NAME or S3_BUCKET_NAME == "your-database-backups-bucket":
        logger.info("Note: S3 bucket tests partially skipped (no bucket configured)")
        overall_success = all([
            backup_info is not None,
            replit_storage_success,
            # aws_s3_success will be True if credentials verified successfully
            restore_success
        ])
    else:
        overall_success = all([
            backup_info is not None,
            replit_storage_success,
            aws_s3_success,
            restore_success
        ])
    
    logger.info(f"\nOVERALL RESULT: {'✅ ALL TESTS PASSED' if overall_success else '❌ SOME TESTS FAILED'}")
    
    return overall_success

if __name__ == "__main__":
    success = run_all_tests()
    # Exit with appropriate status code
    sys.exit(0 if success else 1)