"""
Offsite Backup Transfer Script

This script transfers recent backups from Replit Object Storage to AWS S3 for offsite storage.
It runs weekly to ensure your data is safely stored in multiple locations.
"""
import os
import io
import logging
import boto3
from datetime import datetime, timedelta
from storage import STORAGE_CLIENT

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('offsite_backup')

# AWS S3 configuration
S3_BUCKET_NAME = os.environ.get("REPLIT_AWS_S3_BUCKET", "")  # Get bucket name from Replit Secrets

def get_aws_credentials():
    """Get AWS credentials from Replit Secrets"""
    return {
        "aws_access_key_id": os.environ.get("REPLIT_AWS_ACCESS_KEY_ID", ""),
        "aws_secret_access_key": os.environ.get("REPLIT_AWS_SECRET_ACCESS_KEY", "")
    }

def list_recent_backups(days=7):
    """List backups created in the last X days"""
    if not STORAGE_CLIENT:
        logger.error("Replit Object Storage client not available")
        return []
    
    try:
        # List all backups
        all_objects = STORAGE_CLIENT.list()
        backup_objects = [obj for obj in all_objects 
                         if isinstance(obj, str) and obj.startswith("backups/backup_")]
        
        # Filter by date in filename (backup_YYYY-MM-DD_type.sql.gz)
        recent_backups = []
        cutoff_date = datetime.now() - timedelta(days=days)
        
        for backup in backup_objects:
            try:
                # Extract date from filename
                filename = backup.split('/')[-1]  # Get just the filename
                date_str = filename.split('_')[1]  # Get the YYYY-MM-DD part
                backup_date = datetime.strptime(date_str, "%Y-%m-%d")
                
                # Check if it's recent
                if backup_date >= cutoff_date:
                    recent_backups.append(backup)
            except Exception:
                # If we can't parse the date, skip this file
                continue
        
        return recent_backups
    
    except Exception as e:
        logger.error(f"Error listing recent backups: {str(e)}")
        return []

def transfer_to_s3(backup_name):
    """Transfer a single backup to AWS S3"""
    if not STORAGE_CLIENT:
        logger.error("Replit Object Storage client not available")
        return False
    
    try:
        # Get AWS credentials
        aws_creds = get_aws_credentials()
        
        if not aws_creds["aws_access_key_id"] or not aws_creds["aws_secret_access_key"]:
            logger.error("AWS credentials not configured")
            return False
        
        # Download the backup from Replit Object Storage
        backup_data = STORAGE_CLIENT.download_as_bytes(backup_name)
        
        # Initialize S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_creds["aws_access_key_id"],
            aws_secret_access_key=aws_creds["aws_secret_access_key"]
        )
        
        # Just use the filename part for S3
        s3_key = backup_name.split('/')[-1]
        
        # Upload to S3
        s3_client.upload_fileobj(
            io.BytesIO(backup_data),
            S3_BUCKET_NAME,
            s3_key
        )
        
        logger.info(f"Successfully transferred {backup_name} to S3 bucket {S3_BUCKET_NAME}")
        return True
    
    except Exception as e:
        logger.error(f"Error transferring backup to S3: {str(e)}")
        return False

def perform_offsite_backup():
    """Main function to transfer recent backups to offsite storage"""
    logger.info("Starting offsite backup transfer")
    
    # Get recent backups
    recent_backups = list_recent_backups(days=7)
    logger.info(f"Found {len(recent_backups)} recent backups to transfer")
    
    if not recent_backups:
        logger.warning("No recent backups found to transfer")
        return False
    
    # Transfer each backup
    success_count = 0
    for backup in recent_backups:
        if transfer_to_s3(backup):
            success_count += 1
    
    logger.info(f"Transferred {success_count} out of {len(recent_backups)} backups to S3")
    return success_count > 0

if __name__ == "__main__":
    perform_offsite_backup()