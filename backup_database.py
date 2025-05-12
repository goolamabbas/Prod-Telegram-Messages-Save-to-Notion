"""
PostgreSQL Database Backup Script

This script creates a daily backup of the PostgreSQL database and stores it in Replit Object Storage.
It also manages a rotation policy to maintain the last 7 daily backups, 4 weekly backups, and 3 monthly backups.
"""
import os
import io
import gzip
import logging
import subprocess
import datetime
from datetime import datetime, timedelta
from storage import STORAGE_CLIENT

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('database_backup')

# Backup configuration
DAILY_RETENTION = 7      # Keep daily backups for 7 days
WEEKLY_RETENTION = 4     # Keep weekly backups for 4 weeks
MONTHLY_RETENTION = 3    # Keep monthly backups for 3 months

def get_db_connection_params():
    """Get database connection parameters from environment variables"""
    return {
        "host": os.environ.get("PGHOST", ""),
        "port": os.environ.get("PGPORT", ""),
        "dbname": os.environ.get("PGDATABASE", ""),
        "user": os.environ.get("PGUSER", ""),
        "password": os.environ.get("PGPASSWORD", "")
    }

def create_db_backup():
    """Create a pg_dump of the database"""
    try:
        # Get DB connection parameters
        db_params = get_db_connection_params()
        
        # Set environment variables for password (more secure than command line)
        env = os.environ.copy()
        env["PGPASSWORD"] = db_params["password"]
        
        # Create dump command
        dump_cmd = [
            "pg_dump", 
            "-h", db_params["host"],
            "-p", db_params["port"],
            "-U", db_params["user"],
            "-d", db_params["dbname"],
            "-F", "c",  # Custom format (compressed binary)
        ]
        
        # Execute pg_dump
        logger.info(f"Creating database backup for {db_params['dbname']}")
        dump_process = subprocess.Popen(
            dump_cmd, 
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )
        
        # Capture output
        stdout, stderr = dump_process.communicate()
        
        if dump_process.returncode != 0:
            logger.error(f"Error creating database dump: {stderr.decode('utf-8')}")
            return None
        
        # Compress dump with gzip for additional compression
        compressed_data = gzip.compress(stdout)
        
        return compressed_data
    
    except Exception as e:
        logger.error(f"Error during backup creation: {str(e)}")
        return None

def get_backup_filename(backup_type="daily"):
    """
    Generate backup filename with format: 
    backup_YYYY-MM-DD_type.sql.gz
    """
    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")
    return f"backup_{date_str}_{backup_type}.sql.gz"

def save_backup_to_object_storage(backup_data, filename):
    """Save the backup to Replit Object Storage"""
    if not STORAGE_CLIENT:
        logger.error("Replit Object Storage client not available")
        return False
    
    try:
        # Store in a 'backups' folder
        object_name = f"backups/{filename}"
        
        # Upload to Replit Object Storage
        STORAGE_CLIENT.upload_from_bytes(object_name, backup_data)
        logger.info(f"Backup saved to Replit Object Storage: {object_name}")
        
        return True
    except Exception as e:
        logger.error(f"Error saving backup to Replit Object Storage: {str(e)}")
        return False

def list_existing_backups():
    """List all existing backups in Object Storage"""
    if not STORAGE_CLIENT:
        logger.error("Replit Object Storage client not available")
        return []
    
    try:
        all_objects = STORAGE_CLIENT.list()
        backup_objects = [obj for obj in all_objects if isinstance(obj, str) and obj.startswith("backups/backup_")]
        return backup_objects
    except Exception as e:
        logger.error(f"Error listing existing backups: {str(e)}")
        return []

def apply_retention_policy():
    """
    Apply the retention policy to existing backups:
    - Keep daily backups for DAILY_RETENTION days
    - Keep weekly backups (Sunday) for WEEKLY_RETENTION weeks
    - Keep monthly backups (1st of month) for MONTHLY_RETENTION months
    """
    if not STORAGE_CLIENT:
        logger.error("Replit Object Storage client not available")
        return
    
    try:
        # List all existing backups
        all_backups = list_existing_backups()
        logger.info(f"Found {len(all_backups)} existing backups")
        
        # Group backups by type
        daily_backups = [b for b in all_backups if "_daily." in b]
        weekly_backups = [b for b in all_backups if "_weekly." in b]
        monthly_backups = [b for b in all_backups if "_monthly." in b]
        
        # Sort backups by date (newest first)
        daily_backups.sort(reverse=True)
        weekly_backups.sort(reverse=True)
        monthly_backups.sort(reverse=True)
        
        # Apply retention policies
        to_delete = []
        
        # Daily backups beyond retention period
        if len(daily_backups) > DAILY_RETENTION:
            to_delete.extend(daily_backups[DAILY_RETENTION:])
        
        # Weekly backups beyond retention period
        if len(weekly_backups) > WEEKLY_RETENTION:
            to_delete.extend(weekly_backups[WEEKLY_RETENTION:])
        
        # Monthly backups beyond retention period
        if len(monthly_backups) > MONTHLY_RETENTION:
            to_delete.extend(monthly_backups[MONTHLY_RETENTION:])
        
        # Delete old backups
        for backup in to_delete:
            try:
                STORAGE_CLIENT.delete(backup)
                logger.info(f"Deleted old backup: {backup}")
            except Exception as e:
                logger.error(f"Error deleting backup {backup}: {str(e)}")
        
        logger.info(f"Retention policy applied, deleted {len(to_delete)} old backups")
    
    except Exception as e:
        logger.error(f"Error applying retention policy: {str(e)}")

def verify_backup(backup_name):
    """
    Verify the backup is valid by downloading and checking its size
    (A more thorough verification would restore it to a test database)
    """
    if not STORAGE_CLIENT:
        logger.error("Replit Object Storage client not available")
        return False
    
    try:
        # Get file size
        backup_data = STORAGE_CLIENT.download_as_bytes(backup_name)
        size = len(backup_data)
        
        if size < 1000:  # If less than 1KB, probably an error
            logger.error(f"Backup verification failed: {backup_name} is too small ({size} bytes)")
            return False
        
        logger.info(f"Backup verification successful: {backup_name} ({size} bytes)")
        return True
    
    except Exception as e:
        logger.error(f"Error verifying backup {backup_name}: {str(e)}")
        return False

def determine_backup_type():
    """
    Determine the type of backup to create:
    - Monthly backup on the 1st of the month
    - Weekly backup on Sundays
    - Daily backup otherwise
    """
    today = datetime.now()
    
    if today.day == 1:
        return "monthly"
    elif today.weekday() == 6:  # Sunday
        return "weekly"
    else:
        return "daily"

def perform_backup():
    """Main backup function"""
    logger.info("Starting database backup process")
    
    # Determine backup type
    backup_type = determine_backup_type()
    logger.info(f"Backup type: {backup_type}")
    
    # Create database backup
    backup_data = create_db_backup()
    if not backup_data:
        logger.error("Failed to create database backup")
        return False
    
    # Generate filename
    filename = get_backup_filename(backup_type)
    
    # Save to Object Storage
    success = save_backup_to_object_storage(backup_data, filename)
    if not success:
        logger.error("Failed to save backup to storage")
        return False
    
    # Verify backup
    backup_name = f"backups/{filename}"
    verified = verify_backup(backup_name)
    if not verified:
        logger.error("Backup verification failed")
        return False
    
    # Apply retention policy
    apply_retention_policy()
    
    logger.info("Database backup process completed successfully")
    return True

if __name__ == "__main__":
    perform_backup()