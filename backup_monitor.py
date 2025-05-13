"""
Backup Monitoring and Notification System

This script checks the status of recent backups and sends notifications if any issues are detected.
It can be scheduled to run daily to ensure your backup system is functioning correctly.
"""
import os
import logging
import smtplib
import json
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from storage import STORAGE_CLIENT

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('backup_monitor')

# Configuration
NOTIFICATION_EMAIL = "your-email@example.com"  # Update with your email address
BACKUP_LOG_FILE = "backup_log.json"

def get_smtp_config():
    """Get SMTP configuration from Replit Secrets"""
    return {
        "server": os.environ.get("SMTP_SERVER", "smtp.gmail.com"),
        "port": int(os.environ.get("SMTP_PORT", "587")),
        "username": os.environ.get("SMTP_USERNAME", ""),
        "password": os.environ.get("SMTP_PASSWORD", ""),
    }

def list_recent_backups(days=3):
    """List backups from the last X days"""
    if not STORAGE_CLIENT:
        logger.error("Replit Object Storage client not available")
        return []
    
    try:
        # List all backups
        all_objects = STORAGE_CLIENT.list()
        backup_objects = [obj for obj in all_objects 
                         if isinstance(obj, str) and obj.startswith("backups/backup_")]
        
        # Sort by date in filename
        backup_objects.sort(reverse=True)
        
        # Calculate date threshold
        threshold_date = datetime.now() - timedelta(days=days)
        threshold_date_str = threshold_date.strftime("%Y-%m-%d")
        
        # Filter to recent backups
        recent_backups = []
        for backup in backup_objects:
            try:
                # Extract date from filename
                filename = backup.split('/')[-1]  # Get just the filename
                date_part = filename.split('_')[1]  # Get the YYYY-MM-DD part
                
                if date_part >= threshold_date_str:
                    recent_backups.append(backup)
            except:
                # If we can't parse, skip this file
                continue
                
        return recent_backups
    
    except Exception as e:
        logger.error(f"Error listing recent backups: {str(e)}")
        return []

def get_backup_size(backup_name):
    """Get the size of a backup file in MB"""
    if not STORAGE_CLIENT:
        logger.error("Replit Object Storage client not available")
        return 0
    
    try:
        # Download the backup to check its size
        backup_data = STORAGE_CLIENT.download_as_bytes(backup_name)
        size_bytes = len(backup_data)
        size_mb = size_bytes / (1024 * 1024)
        return size_mb
    
    except Exception as e:
        logger.error(f"Error getting backup size: {str(e)}")
        return 0

def load_backup_log():
    """Load backup log from file"""
    try:
        if os.path.exists(BACKUP_LOG_FILE):
            with open(BACKUP_LOG_FILE, 'r') as f:
                return json.load(f)
        else:
            return {"backups": []}
    except Exception as e:
        logger.error(f"Error loading backup log: {str(e)}")
        return {"backups": []}

def save_backup_log(log_data):
    """Save backup log to file"""
    try:
        with open(BACKUP_LOG_FILE, 'w') as f:
            json.dump(log_data, f, indent=2)
        logger.info("Backup log saved successfully")
    except Exception as e:
        logger.error(f"Error saving backup log: {str(e)}")

def update_backup_log(backup_data):
    """Update the backup log with new information"""
    log = load_backup_log()
    
    # Add new backup data
    log["backups"].append(backup_data)
    
    # Keep only the last 30 entries
    if len(log["backups"]) > 30:
        log["backups"] = log["backups"][-30:]
    
    # Save updated log
    save_backup_log(log)

def send_notification(subject, message):
    """Send an email notification"""
    smtp_config = get_smtp_config()
    
    if not smtp_config["username"] or not smtp_config["password"]:
        logger.error("SMTP credentials not configured")
        return False
    
    try:
        # Create email
        msg = MIMEMultipart()
        msg['From'] = smtp_config["username"]
        msg['To'] = NOTIFICATION_EMAIL
        msg['Subject'] = subject
        
        # Add message body
        msg.attach(MIMEText(message, 'plain'))
        
        # Connect to SMTP server
        server = smtplib.SMTP(smtp_config["server"], smtp_config["port"])
        server.starttls()
        server.login(smtp_config["username"], smtp_config["password"])
        
        # Send email
        server.send_message(msg)
        server.quit()
        
        logger.info(f"Notification sent: {subject}")
        return True
    
    except Exception as e:
        logger.error(f"Error sending notification: {str(e)}")
        return False

def check_backup_health():
    """Check the health of recent backups"""
    logger.info("Starting backup health check")
    
    # Get recent backups
    recent_backups = list_recent_backups(days=3)
    logger.info(f"Found {len(recent_backups)} recent backups")
    
    # Check if we have at least one backup in the last 36 hours
    has_recent_backup = False
    now = datetime.now()
    threshold_time = now - timedelta(hours=36)
    threshold_date_str = threshold_time.strftime("%Y-%m-%d")
    
    backup_summary = []
    
    for backup in recent_backups:
        try:
            # Extract details from filename
            filename = backup.split('/')[-1]
            parts = filename.split('_')
            date_str = parts[1]
            backup_type = parts[2].split('.')[0]
            
            # Get size
            size_mb = get_backup_size(backup)
            
            # Add to summary
            backup_info = {
                "filename": filename,
                "date": date_str,
                "type": backup_type,
                "size_mb": round(size_mb, 2),
                "path": backup
            }
            backup_summary.append(backup_info)
            
            # Check if it's recent enough
            if date_str >= threshold_date_str:
                has_recent_backup = True
                
        except Exception as e:
            logger.error(f"Error processing backup {backup}: {str(e)}")
    
    # Update backup log
    update_time = now.strftime("%Y-%m-%d %H:%M:%S")
    log_entry = {
        "timestamp": update_time,
        "backup_count": len(recent_backups),
        "has_recent_backup": has_recent_backup,
        "backups": backup_summary
    }
    update_backup_log(log_entry)
    
    # Check for issues
    issues = []
    
    if not recent_backups:
        issues.append("No recent backups found")
    
    if not has_recent_backup:
        issues.append("No backup found in the last 36 hours")
    
    for backup in backup_summary:
        if backup["size_mb"] < 0.1:  # Less than 100 KB
            issues.append(f"Backup {backup['filename']} is suspiciously small ({backup['size_mb']} MB)")
    
    # Send notification if issues found
    if issues:
        subject = "⚠️ Database Backup Issues Detected"
        message = "The following issues were detected with your database backups:\n\n"
        message += "\n".join([f"- {issue}" for issue in issues])
        message += "\n\nPlease check your backup system as soon as possible."
        
        send_notification(subject, message)
        logger.warning(f"Backup issues detected: {', '.join(issues)}")
        return False
    else:
        logger.info("Backup health check passed")
        return True

if __name__ == "__main__":
    check_backup_health()