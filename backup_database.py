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
    """Create a simple SQL dump of the database using plain SQL"""
    import psycopg2
    import io
    
    try:
        # Get DB connection parameters
        db_params = get_db_connection_params()
        
        # Create connection string
        conn_string = f"host={db_params['host']} port={db_params['port']} dbname={db_params['dbname']} user={db_params['user']} password={db_params['password']}"
        
        # Connect to the database
        logger.info(f"Creating database backup for {db_params['dbname']} using plain SQL")
        conn = psycopg2.connect(conn_string)
        cursor = conn.cursor()
        
        # Get a list of all tables in the current schema
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        tables = [row[0] for row in cursor.fetchall()]
        
        # Create a buffer for the SQL backup
        sql_buffer = io.StringIO()
        
        # Write header information
        sql_buffer.write(f"-- Database: {db_params['dbname']}\n")
        sql_buffer.write(f"-- Backup Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        sql_buffer.write("-- Backup Method: plain SQL export\n\n")
        
        # For each table, get the data only (simpler approach for testing)
        for table_name in tables:
            sql_buffer.write(f"\n-- Table: {table_name}\n")
            
            # Get table data
            try:
                cursor.execute("SELECT * FROM %s", (table_name,))
                rows = cursor.fetchall()
                
                if rows:
                    # Get column names
                    columns = [desc[0] for desc in cursor.description]
                    columns_str = ', '.join([f'"{col}"' for col in columns])
                    
                    # Add table data header
                    sql_buffer.write(f"-- Data for {table_name}\n")
                    
                    # Generate INSERT statements
                    for row in rows:
                        values = []
                        for val in row:
                            if val is None:
                                values.append("NULL")
                            elif isinstance(val, (int, float)):
                                values.append(str(val))
                            elif isinstance(val, (datetime, timedelta)):
                                values.append(f"'{val}'")
                            elif isinstance(val, (bytes, bytearray)):
                                # Handle binary data
                                import binascii
                                hex_data = binascii.hexlify(val).decode('utf-8')
                                values.append(f"'\\\\x{hex_data}'")
                            else:
                                # Escape string values
                                val_str = str(val).replace("'", "''")
                                values.append(f"'{val_str}'")
                        
                        values_str = ', '.join(values)
                        sql_buffer.write(f"INSERT INTO {table_name} ({columns_str}) VALUES ({values_str});\n")
                    
                    sql_buffer.write("\n")
            except Exception as e:
                logger.warning(f"Error fetching data from table {table_name}: {str(e)}")
                sql_buffer.write(f"-- Error fetching data: {str(e)}\n\n")
        
        # Close database connection
        cursor.close()
        conn.close()
        
        # Get SQL content and compress with gzip
        sql_content = sql_buffer.getvalue().encode('utf-8')
        compressed_data = gzip.compress(sql_content)
        
        logger.info(f"Database backup completed successfully ({len(compressed_data) / 1024:.2f} KB)")
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