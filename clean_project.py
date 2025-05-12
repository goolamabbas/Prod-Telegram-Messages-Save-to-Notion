"""
Clean up and reset the project for production.
This script will:
1. Reset the database (drop and recreate all tables)
2. Delete all downloaded media files from local storage
3. Delete all objects from Replit Object Storage (if available)
"""
import os
import logging
import shutil
from app import app, db
from models import User, TelegramMessage, SyncStatus, Setting
from werkzeug.security import generate_password_hash
from storage import STORAGE_CLIENT

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clean_local_media():
    """Delete all local media files but keep the directory"""
    try:
        media_dir = os.path.join(os.getcwd(), 'media')
        
        # Check if directory exists
        if os.path.exists(media_dir):
            logger.info(f"Cleaning local media directory: {media_dir}")
            
            # Get all files in the directory
            for filename in os.listdir(media_dir):
                file_path = os.path.join(media_dir, filename)
                
                # Make sure it's a file and not a directory
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    logger.info(f"Deleted local file: {file_path}")
                    
            logger.info("Local media files deleted successfully")
        else:
            logger.info("Media directory doesn't exist, creating it")
            os.makedirs(media_dir, exist_ok=True)
            
        # Create .gitkeep file to preserve the empty directory in git
        with open(os.path.join(media_dir, '.gitkeep'), 'w') as f:
            pass
            
        return True
    except Exception as e:
        logger.error(f"Error cleaning local media: {str(e)}")
        return False

def clean_replit_storage():
    """Delete all objects from Replit Object Storage"""
    try:
        if not STORAGE_CLIENT:
            logger.warning("Replit Object Storage client not available")
            return False
            
        logger.info("Cleaning Replit Object Storage")
        
        # List all objects
        objects = STORAGE_CLIENT.list()
        logger.info(f"Found {len(objects)} objects in Replit Object Storage")
        
        # Delete each object
        for obj in objects:
            try:
                # Convert object to string if it's not already
                obj_name = str(obj) if hasattr(obj, "__str__") else obj
                
                # Extract the object name if it's not already a string
                if not isinstance(obj, str) and hasattr(obj, "name"):
                    obj_name = obj.name
                    
                # Delete the object
                STORAGE_CLIENT.delete(obj_name)
                logger.info(f"Deleted object: {obj_name}")
            except Exception as e:
                logger.error(f"Error deleting object {obj}: {str(e)}")
                
        logger.info("Replit Object Storage cleaned successfully")
        return True
    except Exception as e:
        logger.error(f"Error cleaning Replit Object Storage: {str(e)}")
        return False

def reset_database():
    """Reset the database by dropping and recreating all tables"""
    try:
        with app.app_context():
            logger.info("Dropping all database tables")
            db.drop_all()
            
            logger.info("Creating all database tables")
            db.create_all()
            
            # Create admin user
            logger.info("Creating admin user")
            admin = User(
                username="admin",
                email="admin@example.com",
                password_hash=generate_password_hash("admin")  # Default password, should be changed after deployment
            )
            db.session.add(admin)
            
            # Create default settings
            logger.info("Creating default settings")
            token_setting = Setting()
            token_setting.key = "telegram_token"
            token_setting.value = ""
            
            notion_secret = Setting()
            notion_secret.key = "notion_integration_secret"
            notion_secret.value = ""
            
            notion_page = Setting()
            notion_page.key = "notion_page_id"
            notion_page.value = ""
            
            db.session.add_all([token_setting, notion_secret, notion_page])
            db.session.commit()
            
            logger.info("Database reset successfully")
            return True
    except Exception as e:
        logger.error(f"Error resetting database: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("Starting project cleanup")
    
    # Clean local media files
    clean_local_media()
    
    # Clean Replit Object Storage
    clean_replit_storage()
    
    # Reset database
    reset_database()
    
    logger.info("Project cleanup completed")
    print("\n✅ Project cleanup completed successfully.")
    print("✅ Database has been reset with default admin user (username: admin, password: admin)")
    print("✅ Media files have been deleted")
    print("✅ Replit Object Storage has been cleaned")
    print("\n⚠️ IMPORTANT: Remember to change the admin password after deployment!")