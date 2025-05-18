# Database Backup and Recovery System

This documentation provides instructions for the backup and recovery system implemented for the Telegram-Notion integration application.

## Overview

The backup system is designed to:

1. Create daily backups of your PostgreSQL database
2. Store backups in Replit Object Storage
3. Transfer weekly backups to offsite storage (AWS S3)
4. Monitor backup health and send alerts on issues
5. Provide tools for database restoration when needed

## Components

The backup system consists of the following components:

- **backup_database.py** - Creates and manages database backups
- **offsite_backup.py** - Transfers backups to offsite storage for redundancy
- **backup_monitor.py** - Monitors backup health and sends alerts
- **backup_restore.py** - Provides tools for database restoration
- **setup_backup_schedule.py** - Configures the backup schedule

## Setup Instructions

### 1. Configure Replit Secrets

For security, use Replit Secrets to store sensitive credentials. Configure the following secrets:

**Database Connection** (already configured by Replit):
- `PGHOST` - PostgreSQL host
- `PGPORT` - PostgreSQL port
- `PGDATABASE` - PostgreSQL database name
- `PGUSER` - PostgreSQL username
- `PGPASSWORD` - PostgreSQL password

**Replit Object Storage**:
- `REPLIT_OBJECT_STORAGE` - Needed for storing backups in Replit's cloud storage

**Offsite Backup** (AWS S3):
- `REPLIT_AWS_ACCESS_KEY_ID` - AWS access key
- `REPLIT_AWS_SECRET_ACCESS_KEY` - AWS secret key
- `REPLIT_AWS_S3_BUCKET` - AWS S3 bucket name for offsite backups

**Monitoring** (Email notifications):
- `SMTP_SERVER` - SMTP server (default: smtp.gmail.com)
- `SMTP_PORT` - SMTP port (default: 587)
- `SMTP_USERNAME` - SMTP username
- `SMTP_PASSWORD` - SMTP password

To add these secrets:
1. Go to the "Secrets" tab in your Replit workspace
2. Add each secret key and its corresponding value
3. Click "Add new secret" for each entry
4. The secrets will be available as environment variables in your application

### 2. Set Up the Backup Schedule

Run the following command to set up the backup schedule:

```bash
python setup_backup_schedule.py
```

This will:
- Schedule daily backups at 3:00 AM UTC
- Schedule weekly offsite backups on Sundays at 4:00 AM UTC

### 3. Verify Configuration

Run a manual backup to ensure everything is set up correctly:

```bash
python setup_backup_schedule.py --manual
```

## Backup Schedule

- **Daily backups** run at 3:00 AM UTC
- **Weekly offsite backups** run on Sundays at 4:00 AM UTC
- **Daily backup monitoring** runs at 9:00 AM UTC

## Backup Retention Policy

The system maintains:
- Last 7 daily backups
- Last 4 weekly backups (Sundays)
- Last 3 monthly backups (1st of the month)

## Storage Requirements

Estimated storage requirements:
- Average database size: ~10-50 MB per backup (compressed)
- Daily backups (7): 70-350 MB
- Weekly backups (4): 40-200 MB
- Monthly backups (3): 30-150 MB
- Total storage needed: ~140-700 MB

## Backup Monitoring

The monitoring system:
- Checks for successful daily backups
- Verifies backup file sizes
- Sends email notifications on issues

## Restoring from Backup

To restore the database from a backup:

```bash
python backup_restore.py
```

This will:
1. List available backups
2. Allow you to select a backup
3. Download and decompress the backup
4. Restore it to your PostgreSQL database

⚠️ **IMPORTANT**: Restoration will replace your current database completely. Make sure you understand the implications before proceeding.

## Troubleshooting

If you encounter issues with the backup system:

1. Check the application logs for error messages
2. Verify that database connection parameters are correct
3. Ensure Replit Object Storage is enabled and accessible
   - Check that the `REPLIT_OBJECT_STORAGE` secret is properly configured
   - Run `python test_object_storage_access.py` to verify storage access
4. Check AWS credentials if offsite backups are failing
   - Verify the AWS credentials with `python test_aws_backup.py`
5. Test the backup and restore cycle with `python test_backup_restore.py`
6. Verify SMTP settings if notifications aren't being received

## Manual Backup

To perform a manual backup:

```bash
python backup_database.py
```

## Manual Offsite Backup

To manually transfer backups to offsite storage:

```bash
python offsite_backup.py
```

## Best Practices

1. **Regularly test restores** - Periodically restore a backup to a test database to ensure recovery works
2. **Monitor backup notifications** - Address any alerts promptly
3. **Review backup logs** - Check for any warnings or errors in the logs
4. **Keep credentials secure** - Protect your AWS and SMTP credentials
5. **Update documentation** - Keep this guide updated as you make changes to the backup system