"""
Setup Backup Schedule

This script sets up scheduled jobs for database backups:
1. Daily backups to Replit Object Storage
2. Weekly offsite backups to AWS S3

It integrates with the application's scheduler to ensure backups run regularly.
"""
import os
import logging
from app import app, scheduler
from apscheduler.triggers.cron import CronTrigger
from backup_database import perform_backup
from offsite_backup import perform_offsite_backup

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('backup_scheduler')

def setup_backup_schedule():
    """Configure and start the backup schedule"""
    with app.app_context():
        # Set up daily backup job (runs at 3:00 AM UTC)
        scheduler.add_job(
            perform_backup,
            trigger=CronTrigger(hour=3, minute=0),
            id='daily_backup',
            name='Daily Database Backup',
            replace_existing=True
        )
        logger.info("Daily backup job scheduled (runs at 03:00 UTC)")
        
        # Set up weekly offsite backup job (runs at 4:00 AM UTC on Sundays)
        scheduler.add_job(
            perform_offsite_backup,
            trigger=CronTrigger(day_of_week='sun', hour=4, minute=0),
            id='weekly_offsite_backup',
            name='Weekly Offsite Backup Transfer',
            replace_existing=True
        )
        logger.info("Weekly offsite backup job scheduled (runs on Sundays at 04:00 UTC)")
        
        logger.info("All backup jobs have been scheduled successfully")

def manual_backup():
    """Run a backup manually"""
    with app.app_context():
        logger.info("Starting manual backup")
        success = perform_backup()
        if success:
            logger.info("Manual backup completed successfully")
        else:
            logger.error("Manual backup failed")
        return success

if __name__ == "__main__":
    # Check if we should run a manual backup
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--manual':
        manual_backup()
    else:
        # Set up the scheduled backups
        setup_backup_schedule()