"""
Update Application to Include Backup Schedule

This script updates the application to integrate the backup system
into the existing scheduler.
"""
import logging
from app import app, scheduler
from setup_backup_schedule import setup_backup_schedule
from backup_monitor import check_backup_health
from apscheduler.triggers.cron import CronTrigger

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('update_app')

def update_application():
    """Update the application with backup functionality"""
    with app.app_context():
        # Set up backup schedule
        setup_backup_schedule()
        
        # Add backup monitoring (runs at 9:00 AM UTC)
        scheduler.add_job(
            check_backup_health,
            trigger=CronTrigger(hour=9, minute=0),
            id='backup_monitor',
            name='Daily Backup Monitoring',
            replace_existing=True
        )
        
        logger.info("Application updated with backup system")
        print("✅ Application successfully updated with backup functionality")

if __name__ == "__main__":
    update_application()