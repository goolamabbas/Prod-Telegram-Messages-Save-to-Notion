import os
import json
import logging
from datetime import datetime, timedelta
from notion_client import Client
from sqlalchemy import func
from app import db
from models import TelegramMessage, SyncStatus, Setting

# Initialize logger
logger = logging.getLogger(__name__)

def get_notion_client():
    """Get Notion client from environment secrets"""
    import os
    notion_secret = os.environ.get("NOTION_INTEGRATION_SECRET")
    if notion_secret:
        return Client(auth=notion_secret)
    return None

def get_notion_page_id():
    """Get Notion page ID from environment secrets"""
    import os
    return os.environ.get("NOTION_PAGE_ID")

def create_monthly_database(client, parent_page_id, year, month):
    """Create a new database for the given month"""
    month_name = datetime(year, month, 1).strftime("%B")
    title = f"Messages {month_name} {year}"
    
    # Log the creation attempt
    logger.info(f"Creating monthly database '{title}' in parent page {parent_page_id}")
    
    # Create monthly database as a child of main page
    try:
        response = client.databases.create(
            parent={"page_id": parent_page_id},
            title=[{"type": "text", "text": {"content": title}}],
            properties={
                "Day": {"title": {}},
                "Date": {"date": {}},
                "Messages": {"number": {}},
                "Status": {"select": {
                    "options": [
                        {"name": "Synced", "color": "green"},
                        {"name": "Pending", "color": "yellow"},
                        {"name": "Failed", "color": "red"},
                    ]
                }}
            }
        )
        logger.info(f"Created monthly database for {month_name} {year}")
        return response["id"]
    except Exception as e:
        logger.error(f"Error creating monthly database: {str(e)}")
        return None

def create_daily_page(client, monthly_database_id, date):
    """Create a new page for the given day"""
    day_name = date.strftime("%A")
    day_str = date.strftime("%Y-%m-%d")
    
    try:
        response = client.pages.create(
            parent={"database_id": monthly_database_id},
            properties={
                "Day": {"title": [{"type": "text", "text": {"content": day_name}}]},
                "Date": {"date": {"start": day_str}},
                "Messages": {"number": 0},
                "Status": {"select": {"name": "Pending"}}
            },
            children=[
                {
                    "object": "block",
                    "type": "heading_1",
                    "heading_1": {
                        "rich_text": [{"type": "text", "text": {"content": f"Messages for {day_str}"}}]
                    }
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": "All messages from Telegram for this day."}}]
                    }
                }
            ]
        )
        logger.info(f"Created daily page for {day_str}")
        return response["id"]
    except Exception as e:
        logger.error(f"Error creating daily page: {str(e)}")
        return None

def format_message_for_notion(message):
    """Format a Telegram message for Notion"""
    timestamp = message.timestamp.strftime("%H:%M:%S")
    username = message.username if message.username else f"{message.first_name} {message.last_name}".strip()
    
    # Format full message
    formatted_text = f"**{timestamp}** - **{username}**: {message.text}"
    
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": formatted_text}}]
        }
    }

def sync_messages_to_notion():
    """Sync unsynced messages to Notion"""
    logger.info("Starting Notion sync...")
    
    notion_client = get_notion_client()
    parent_page_id = get_notion_page_id()  # Top level page ID that will contain monthly databases
    
    if not notion_client:
        logger.error("Notion client not available - check your NOTION_INTEGRATION_SECRET environment variable")
        sync_status = SyncStatus()
        sync_status.messages_synced = 0
        sync_status.success = False
        sync_status.error_message = "Notion client not available - check your NOTION_INTEGRATION_SECRET environment variable"
        db.session.add(sync_status)
        db.session.commit()
        return
        
    if not parent_page_id:
        logger.error("Notion page ID not configured - check your NOTION_PAGE_ID environment variable")
        sync_status = SyncStatus()
        sync_status.messages_synced = 0
        sync_status.success = False
        sync_status.error_message = "Notion page ID not configured - check your NOTION_PAGE_ID environment variable"
        db.session.add(sync_status)
        db.session.commit()
        return
        
    # Log debug info
    logger.info(f"Using Notion page ID: {parent_page_id}")
    
    try:
        # Get unsynced messages
        unsynced_messages = TelegramMessage.query.filter_by(synced=False).order_by(TelegramMessage.timestamp).all()
        
        if not unsynced_messages:
            logger.info("No unsynced messages found")
            sync_status = SyncStatus()
            sync_status.messages_synced = 0
            sync_status.success = True
            db.session.add(sync_status)
            db.session.commit()
            return
        
        # Group messages by date
        messages_by_date = {}
        for message in unsynced_messages:
            date_key = message.timestamp.date()
            if date_key not in messages_by_date:
                messages_by_date[date_key] = []
            messages_by_date[date_key].append(message)
        
        # Process messages by date
        total_synced = 0
        
        for date, messages in messages_by_date.items():
            year = date.year
            month = date.month
            month_name = date.strftime("%B")
            
            # Get or create monthly database
            monthly_db_id = None
            
            # Try to find the monthly database by listing child blocks
            try:
                # First, search for existing monthly databases in the parent page
                children_response = notion_client.blocks.children.list(block_id=parent_page_id)
                
                # Look for child database blocks with matching title
                children_results = children_response.get("results", []) if isinstance(children_response, dict) else []
                for block in children_results:
                    if block.get("type") == "child_database":
                        # Fetch database details to check title
                        db_details = notion_client.databases.retrieve(database_id=block["id"])
                        db_title = db_details.get("title", []) if isinstance(db_details, dict) else []
                        title_parts = []
                        for text in db_title:
                            if isinstance(text, dict) and "text" in text:
                                title_parts.append(text["text"].get("content", ""))
                        title = "".join(title_parts)
                        
                        if title == f"Messages {month_name} {year}":
                            monthly_db_id = block["id"]
                            break
            except Exception as e:
                logger.error(f"Error searching for monthly database: {str(e)}")
            
            # If not found, create new monthly database
            if not monthly_db_id:
                monthly_db_id = create_monthly_database(notion_client, parent_page_id, year, month)
            
            if not monthly_db_id:
                logger.error(f"Failed to get or create monthly database for {year}-{month}")
                continue
            
            # Get or create daily page
            daily_page_id = None
            
            # Try to find the daily page
            try:
                daily_pages = notion_client.databases.query(
                    database_id=monthly_db_id,
                    filter={
                        "property": "Date",
                        "date": {
                            "equals": date.strftime("%Y-%m-%d")
                        }
                    }
                )
                
                if isinstance(daily_pages, dict) and "results" in daily_pages and daily_pages["results"]:
                    daily_page_id = daily_pages["results"][0]["id"]
            except Exception as e:
                logger.error(f"Error searching for daily page: {str(e)}")
            
            if not daily_page_id:
                # Create new daily page
                daily_page_id = create_daily_page(notion_client, monthly_db_id, date)
            
            if not daily_page_id:
                logger.error(f"Failed to get or create daily page for {date}")
                continue
            
            # Format messages for Notion
            formatted_messages = [format_message_for_notion(message) for message in messages]
            
            # Update daily page with messages
            notion_client.blocks.children.append(
                block_id=daily_page_id,
                children=formatted_messages
            )
            
            # Update messages count in the daily page
            notion_client.pages.update(
                page_id=daily_page_id,
                properties={
                    "Messages": {"number": len(messages)},
                    "Status": {"select": {"name": "Synced"}}
                }
            )
            
            # Mark messages as synced
            for message in messages:
                message.synced = True
                message.notion_page_id = daily_page_id
            
            total_synced += len(messages)
            logger.info(f"Synced {len(messages)} messages for {date}")
        
        # Commit changes to database
        db.session.commit()
        
        # Create sync status record
        sync_status = SyncStatus()
        sync_status.messages_synced = total_synced
        sync_status.success = True
        db.session.add(sync_status)
        db.session.commit()
        
        logger.info(f"Successfully synced {total_synced} messages to Notion")
        
    except Exception as e:
        logger.error(f"Error syncing messages to Notion: {str(e)}")
        
        # Create failed sync status
        sync_status = SyncStatus()
        sync_status.messages_synced = 0
        sync_status.success = False
        sync_status.error_message = str(e)
        db.session.add(sync_status)
        db.session.commit()
