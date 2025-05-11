from app import app, db
from models import TelegramMessage, SyncStatus, Setting, User
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_database():
    """Migrate database to add new columns for media handling"""
    with app.app_context():
        logger.info("Starting database migration for media fields...")
        
        # Check if tables exist and create them if not
        logger.info("Creating tables if they don't exist...")
        db.create_all()
        
        # Check if we need to add media columns
        try:
            # Check if the 'media_type' column exists
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('telegram_message')]
            
            logger.info(f"Existing columns in telegram_message: {columns}")
            
            if 'media_type' not in columns:
                logger.info("Adding media columns to TelegramMessage table...")
                
                # Add the columns one by one
                with db.engine.connect() as conn:
                    for column_name, column_type in [
                        ('media_type', 'VARCHAR(20)'),
                        ('media_file_id', 'VARCHAR(255)'),
                        ('media_original_url', 'VARCHAR(255)'),
                        ('media_stored_path', 'VARCHAR(255)'),
                        ('media_size', 'INTEGER'),
                        ('media_filename', 'VARCHAR(255)'),
                        ('media_content_type', 'VARCHAR(100)')
                    ]:
                        try:
                            # In PostgreSQL we can use the IF NOT EXISTS syntax
                            conn.execute(text(f"ALTER TABLE telegram_message ADD COLUMN IF NOT EXISTS {column_name} {column_type}"))
                            # Some connection objects don't have commit method
                            try:
                                conn.commit()
                            except:
                                pass
                            logger.info(f"Added column {column_name}")
                        except Exception as e:
                            logger.error(f"Error adding column {column_name}: {e}")
                
                logger.info("Media columns added successfully")
            else:
                logger.info("Media columns already exist")
                
            logger.info("Database migration completed successfully")
            
        except Exception as e:
            logger.error(f"Error during database migration: {e}")
            raise e

if __name__ == "__main__":
    migrate_database()