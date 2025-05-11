import logging
import json
from datetime import datetime, timedelta
from app import db
from models import TelegramMessage, SyncStatus, Setting

# Initialize logger
logger = logging.getLogger(__name__)

def get_setting(key, default=None):
    """Get a setting value from the database"""
    setting = Setting.query.filter_by(key=key).first()
    if setting and setting.value:
        return setting.value
    return default

def set_setting(key, value):
    """Set a setting value in the database"""
    setting = Setting.query.filter_by(key=key).first()
    if setting:
        setting.value = value
    else:
        setting = Setting(key=key, value=value)
        db.session.add(setting)
    db.session.commit()
    return True

def get_message_stats(days=7):
    """Get message statistics for the last X days"""
    from sqlalchemy import func
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Get message counts by day
    results = db.session.query(
        func.date(TelegramMessage.timestamp).label('date'),
        func.count().label('count')
    ).filter(
        TelegramMessage.timestamp >= start_date,
        TelegramMessage.timestamp <= end_date
    ).group_by(
        func.date(TelegramMessage.timestamp)
    ).order_by(
        func.date(TelegramMessage.timestamp)
    ).all()
    
    # Convert to dictionary with date as key
    stats = {}
    for date, count in results:
        stats[date.strftime('%Y-%m-%d')] = count
    
    # Fill in missing dates with zero counts
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        if date_str not in stats:
            stats[date_str] = 0
        current_date += timedelta(days=1)
    
    return stats

def get_sync_stats(days=7):
    """Get sync statistics for the last X days"""
    from sqlalchemy import func, case
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Get sync status counts by day
    results = db.session.query(
        func.date(SyncStatus.timestamp).label('date'),
        func.sum(case((SyncStatus.success == True, 1), else_=0)).label('success'),
        func.sum(case((SyncStatus.success == False, 1), else_=0)).label('failure')
    ).filter(
        SyncStatus.timestamp >= start_date,
        SyncStatus.timestamp <= end_date
    ).group_by(
        func.date(SyncStatus.timestamp)
    ).order_by(
        func.date(SyncStatus.timestamp)
    ).all()
    
    # Convert to dictionary with date as key
    stats = {}
    for date, success, failure in results:
        stats[date.strftime('%Y-%m-%d')] = {
            'success': success or 0,
            'failure': failure or 0
        }
    
    # Fill in missing dates with zero counts
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        if date_str not in stats:
            stats[date_str] = {
                'success': 0,
                'failure': 0
            }
        current_date += timedelta(days=1)
    
    return stats
