from app import app, db
import logging

# Initialize logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reset_database():
    """Reset the database by dropping all tables and recreating them"""
    with app.app_context():
        logger.info("Dropping all tables...")
        db.drop_all()
        
        logger.info("Creating all tables...")
        db.create_all()
        
        # Create admin user
        from models import User
        from werkzeug.security import generate_password_hash
        
        admin = User(
            username="admin",
            email="admin@example.com",
            password_hash=generate_password_hash("admin")
        )
        
        db.session.add(admin)
        db.session.commit()
        
        logger.info("Admin user created")
        logger.info("Database reset completed successfully")

if __name__ == "__main__":
    reset_database()