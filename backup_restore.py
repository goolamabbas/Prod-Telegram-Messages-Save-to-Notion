"""
Database Backup Restoration Script

This script provides functionality to restore a PostgreSQL database from a backup.
It should be run manually when recovery is needed.
"""
import os
import io
import gzip
import logging
import subprocess
import tempfile
import shlex
from datetime import datetime
from storage import STORAGE_CLIENT

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('backup_restore')

def get_db_connection_params():
    """Get database connection parameters from environment variables"""
    return {
        "host": os.environ.get("PGHOST", ""),
        "port": os.environ.get("PGPORT", ""),
        "dbname": os.environ.get("PGDATABASE", ""),
        "user": os.environ.get("PGUSER", ""),
        "password": os.environ.get("PGPASSWORD", "")
    }

def list_available_backups():
    """List all available backups in Object Storage"""
    if not STORAGE_CLIENT:
        logger.error("Replit Object Storage client not available")
        return []
    
    try:
        all_objects = STORAGE_CLIENT.list()
        backup_objects = [obj for obj in all_objects 
                         if isinstance(obj, str) and obj.startswith("backups/backup_")]
        
        # Sort by name (newest first)
        backup_objects.sort(reverse=True)
        
        # Format for display
        formatted_backups = []
        for i, backup in enumerate(backup_objects):
            filename = backup.split('/')[-1]
            parts = filename.split('_')
            if len(parts) >= 3:
                date_str = parts[1]
                backup_type = parts[2].split('.')[0]
                formatted_backups.append({
                    "index": i,
                    "path": backup,
                    "filename": filename,
                    "date": date_str,
                    "type": backup_type
                })
        
        return formatted_backups
    
    except Exception as e:
        logger.error(f"Error listing available backups: {str(e)}")
        return []

def download_backup(backup_path):
    """Download a backup file from Replit Object Storage"""
    if not STORAGE_CLIENT:
        logger.error("Replit Object Storage client not available")
        return None
    
    try:
        logger.info(f"Downloading backup: {backup_path}")
        compressed_data = STORAGE_CLIENT.download_as_bytes(backup_path)
        
        # Decompress gzip
        logger.info("Decompressing backup file")
        decompressed_data = gzip.decompress(compressed_data)
        
        return decompressed_data
    
    except Exception as e:
        logger.error(f"Error downloading backup: {str(e)}")
        return None

def restore_database(backup_data, db_params=None):
    """Restore database from backup data"""
    if db_params is None:
        db_params = get_db_connection_params()
    
    # Validate db_params
    for key in ["host", "port", "user", "dbname"]:
        if not isinstance(db_params.get(key), str):
            logger.error(f"Invalid database parameter: {key}")
            return False
    
    try:
        # Create a temporary file for the backup
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(backup_data)
            temp_path = temp_file.name
        
        # Set environment variables for password
        env = os.environ.copy()
        env["PGPASSWORD"] = db_params["password"]
        
        # Option 1: Drop connections first (if you have the necessary privileges)
        try:
            # Create SQL to terminate connections using parameterized query
            # Using psql with $1 parameter to safely handle the database name
            terminate_cmd = [
                "psql",
                "-h", shlex.quote(db_params["host"]),
                "-p", shlex.quote(db_params["port"]),
                "-U", shlex.quote(db_params["user"]),
                "-d", "postgres",  # Connect to postgres db to terminate connections
                "-c", "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = $1 AND pid <> pg_backend_pid();",
                "-v", f"1={shlex.quote(db_params['dbname'])}"
            ]
            
            logger.info("Terminating existing database connections")
            term_process = subprocess.Popen(
                terminate_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env
            )
            term_stdout, term_stderr = term_process.communicate()
            
            if term_process.returncode != 0:
                logger.warning(f"Warning terminating connections: {term_stderr.decode('utf-8')}")
        except Exception as e:
            logger.warning(f"Warning: Could not terminate connections: {str(e)}")
        
        # Option 2: Recreate the database
        try:
            # Drop the database
            drop_cmd = [
                "dropdb",
                "-h", db_params["host"],
                "-p", db_params["port"],
                "-U", db_params["user"],
                "--if-exists",
                db_params["dbname"]
            ]
            
            logger.info(f"Dropping database: {db_params['dbname']}")
            drop_process = subprocess.Popen(
                drop_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env
            )
            drop_stdout, drop_stderr = drop_process.communicate()
            
            if drop_process.returncode != 0:
                logger.error(f"Error dropping database: {drop_stderr.decode('utf-8')}")
                return False
            
            # Create the database
            create_cmd = [
                "createdb",
                "-h", shlex.quote(db_params["host"]),
                "-p", shlex.quote(db_params["port"]),
                "-U", shlex.quote(db_params["user"]),
                shlex.quote(db_params["dbname"])
            ]
            
            logger.info(f"Creating database: {db_params['dbname']}")
            create_process = subprocess.Popen(
                create_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env
            )
            create_stdout, create_stderr = create_process.communicate()
            
            if create_process.returncode != 0:
                logger.error(f"Error creating database: {create_stderr.decode('utf-8')}")
                return False
        except Exception as e:
            logger.error(f"Error recreating database: {str(e)}")
            return False
        
        # Restore the database
        restore_cmd = [
            "pg_restore",
            "-h", shlex.quote(db_params["host"]),
            "-p", shlex.quote(db_params["port"]),
            "-U", shlex.quote(db_params["user"]),
            "-d", shlex.quote(db_params["dbname"]),
            "--clean",  # Clean (drop) database objects before recreating
            "--no-owner",  # Don't output commands to set ownership
            "--no-privileges",  # Don't output commands to set privileges
            shlex.quote(temp_path)
        ]
        
        logger.info(f"Restoring database: {db_params['dbname']}")
        restore_process = subprocess.Popen(
            restore_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )
        restore_stdout, restore_stderr = restore_process.communicate()
        
        # Clean up temp file
        os.unlink(temp_path)
        
        if restore_process.returncode != 0:
            logger.error(f"Error restoring database: {restore_stderr.decode('utf-8')}")
            return False
        
        logger.info("Database restore completed successfully")
        return True
    
    except Exception as e:
        logger.error(f"Error restoring database: {str(e)}")
        return False

def interactive_restore():
    """Interactive restore process"""
    print("\n===== DATABASE RESTORATION TOOL =====\n")
    print("This tool will restore your database from a backup. This operation will REPLACE your current database.")
    print("Make sure you understand the consequences before proceeding.\n")
    
    proceed = input("Do you want to proceed? (yes/no): ")
    if proceed.lower() != "yes":
        print("Operation cancelled.")
        return
    
    # List available backups
    backups = list_available_backups()
    
    if not backups:
        print("No backups found in storage. Restoration cancelled.")
        return
    
    print("\nAvailable backups:")
    for backup in backups:
        print(f"{backup['index']:3d}. {backup['date']} - {backup['type']} ({backup['filename']})")
    
    # Select backup
    while True:
        selection = input("\nEnter the number of the backup to restore (or 'q' to quit): ")
        
        if selection.lower() == 'q':
            print("Operation cancelled.")
            return
        
        try:
            idx = int(selection)
            if 0 <= idx < len(backups):
                selected_backup = backups[idx]
                break
            else:
                print("Invalid selection. Please try again.")
        except ValueError:
            print("Please enter a valid number.")
    
    # Confirm selection
    print(f"\nYou selected: {selected_backup['date']} - {selected_backup['type']} ({selected_backup['filename']})")
    confirm = input("Are you sure you want to restore this backup? (yes/no): ")
    
    if confirm.lower() != "yes":
        print("Operation cancelled.")
        return
    
    # Download backup
    print(f"\nDownloading backup: {selected_backup['path']}")
    backup_data = download_backup(selected_backup['path'])
    
    if not backup_data:
        print("Failed to download backup. Restoration cancelled.")
        return
    
    # Restore database
    print("\nRestoring database... (this may take a while)")
    success = restore_database(backup_data)
    
    if success:
        print("\n✅ Database restored successfully!")
    else:
        print("\n❌ Database restoration failed. Please check the logs for details.")

if __name__ == "__main__":
    interactive_restore()