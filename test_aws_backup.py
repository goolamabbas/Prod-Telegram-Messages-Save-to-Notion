"""
Test AWS S3 Offsite Backup Functionality

This script tests the AWS S3 backup functionality specifically.
"""
import os
import io
import sys
import logging
import boto3
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('aws_backup_test')

def get_aws_credentials():
    """Get AWS credentials from environment variables/secrets"""
    aws_access_key = os.environ.get("REPLIT_AWS_ACCESS_KEY_ID", "")
    aws_secret_key = os.environ.get("REPLIT_AWS_SECRET_ACCESS_KEY", "")
    aws_bucket_name = os.environ.get("REPLIT_AWS_S3_BUCKET", "")
    
    if not aws_access_key or not aws_secret_key:
        logger.error("AWS credentials not properly configured")
        return None
    
    if not aws_bucket_name:
        logger.error("AWS S3 bucket name not configured")
        return None
    
    return {
        "aws_access_key_id": aws_access_key,
        "aws_secret_access_key": aws_secret_key,
        "bucket_name": aws_bucket_name
    }

def test_aws_s3_connection():
    """Test AWS S3 connection and bucket access"""
    logger.info("Testing AWS S3 connection and bucket access")
    
    # Get credentials
    aws_creds = get_aws_credentials()
    if not aws_creds:
        return False
    
    try:
        # Initialize S3 client
        logger.info("Initializing S3 client")
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_creds["aws_access_key_id"],
            aws_secret_access_key=aws_creds["aws_secret_access_key"]
        )
        logger.info("✅ S3 client initialized successfully")
        
        # Check if bucket exists
        try:
            bucket_name = aws_creds["bucket_name"]
            logger.info(f"Checking if bucket '{bucket_name}' exists")
            s3_client.head_bucket(Bucket=bucket_name)
            logger.info(f"✅ Bucket '{bucket_name}' exists and is accessible")
            
            # List objects in bucket
            logger.info(f"Listing objects in bucket '{bucket_name}'")
            response = s3_client.list_objects_v2(Bucket=bucket_name)
            objects = response.get('Contents', [])
            logger.info(f"✅ Found {len(objects)} objects in bucket")
            
            # Print a few object keys for verification
            if objects:
                logger.info("Sample objects:")
                for obj in objects[:5]:  # Show first 5 objects
                    logger.info(f" - {obj['Key']} ({obj['Size']} bytes)")
            
            return True
        except Exception as e:
            logger.error(f"❌ Error accessing bucket: {str(e)}")
            return False
    except Exception as e:
        logger.error(f"❌ Error initializing S3 client: {str(e)}")
        return False

def test_aws_s3_offsite_backup():
    """Test AWS S3 offsite backup functionality"""
    logger.info("Testing AWS S3 offsite backup functionality")
    
    # Get credentials
    aws_creds = get_aws_credentials()
    if not aws_creds:
        return False
    
    try:
        # Initialize S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_creds["aws_access_key_id"],
            aws_secret_access_key=aws_creds["aws_secret_access_key"]
        )
        
        # Create test data
        test_data = f"Test backup data created at {datetime.now().isoformat()}".encode('utf-8')
        test_key = f"test/test_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        bucket_name = aws_creds["bucket_name"]
        
        # Upload test data to S3
        logger.info(f"Uploading test data to S3 bucket '{bucket_name}', key: '{test_key}'")
        s3_client.upload_fileobj(
            io.BytesIO(test_data),
            bucket_name,
            test_key
        )
        logger.info("✅ Upload successful")
        
        # Verify file exists
        logger.info(f"Verifying file exists in S3")
        response = s3_client.head_object(Bucket=bucket_name, Key=test_key)
        logger.info(f"✅ File verified in S3, size: {response['ContentLength']} bytes")
        
        # Download the file to verify content
        logger.info(f"Downloading file to verify content")
        download_buffer = io.BytesIO()
        s3_client.download_fileobj(
            bucket_name,
            test_key,
            download_buffer
        )
        download_buffer.seek(0)
        downloaded_data = download_buffer.read()
        
        if downloaded_data == test_data:
            logger.info("✅ Downloaded data matches original data")
        else:
            logger.error("❌ Downloaded data does not match original data")
            return False
        
        # Clean up test file
        logger.info(f"Cleaning up test file from S3")
        s3_client.delete_object(Bucket=bucket_name, Key=test_key)
        logger.info("✅ Test file deleted from S3")
        
        return True
    except Exception as e:
        logger.error(f"❌ Error during AWS S3 offsite backup test: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("===== AWS S3 OFFSITE BACKUP TEST =====")
    
    # Test AWS S3 connection
    connection_success = test_aws_s3_connection()
    if not connection_success:
        logger.error("❌ AWS S3 connection test failed, stopping further tests")
        sys.exit(1)
    
    # Test AWS S3 offsite backup
    backup_success = test_aws_s3_offsite_backup()
    
    if connection_success and backup_success:
        logger.info("✅✅ ALL TESTS PASSED - AWS S3 offsite backup is working correctly")
        sys.exit(0)
    else:
        logger.error("❌❌ TESTS FAILED - AWS S3 offsite backup functionality has issues")
        sys.exit(1)