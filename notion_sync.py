import os
import json
import logging
from datetime import datetime, timedelta
from notion_client import Client
from sqlalchemy import func
from app import db
from models import TelegramMessage, SyncStatus, Setting

# Initialize logger
logger = logging.getLogger('notion_sync')
# Set up console handler if not already configured
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(console_handler)
    logger.setLevel(logging.INFO)

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
    """Format a Telegram message for Notion with URL detection and media handling"""
    import re
    
    timestamp = message.timestamp.strftime("%H:%M:%S")
    username = message.username if message.username else f"{message.first_name} {message.last_name}".strip()
    
    # Check if this is a media message
    if message.has_media():
        # Get media URL
        media_url = message.get_media_url()
        
        # Handle different media types
        if message.media_type == 'image':
            # Create an image block for the media
            image_block = {
                "object": "block",
                "type": "image",
                "image": {
                    "type": "external",
                    "external": {"url": media_url}
                }
            }
            
            # Create a text block for caption/metadata
            caption_blocks = []
            
            # Header with timestamp and username
            caption_blocks.append({
                "type": "text", 
                "text": {"content": f"**{timestamp}** - **{username}** shared an image: "}
            })
            
            # If there's a caption, add it
            if message.text:
                # Add URL detection for the caption
                url_pattern = r'(https?://[^\s]+)'
                
                # Check if the text contains URLs
                if re.search(url_pattern, message.text):
                    # Split text by URLs
                    parts = re.split(url_pattern, message.text)
                    
                    # Build text blocks with URLs as links
                    for i, part in enumerate(parts):
                        if i % 2 == 0:  # Regular text
                            if part:  # Only add if not empty
                                caption_blocks.append({
                                    "type": "text",
                                    "text": {"content": part}
                                })
                        else:  # URL part
                            caption_blocks.append({
                                "type": "text",
                                "text": {
                                    "content": part,
                                    "link": {"url": part}
                                }
                            })
                else:
                    # No URLs, just add the text as is
                    caption_blocks.append({
                        "type": "text",
                        "text": {"content": message.text}
                    })
            
            # Return both blocks (image and caption)
            return [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": caption_blocks
                    }
                },
                image_block
            ]
            
        elif message.media_type in ['document', 'video', 'audio']:
            # For non-image media, create a rich text block with file link
            media_blocks = []
            
            # Header with timestamp and username
            header_text = f"**{timestamp}** - **{username}** shared a {message.media_type}: "
            
            media_blocks.append({
                "type": "text", 
                "text": {"content": header_text}
            })
            
            # Add a link to the file
            media_blocks.append({
                "type": "text",
                "text": {
                    "content": message.media_filename or f"{message.media_type} file",
                    "link": {"url": media_url}
                }
            })
            
            # If there's a caption, add it
            if message.text:
                media_blocks.append({
                    "type": "text",
                    "text": {"content": f" - {message.text}"}
                })
            
            return {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": media_blocks
                }
            }
    
    # Regular text message handling
    # Header part (timestamp and username)
    header_text = f"**{timestamp}** - **{username}**: "
    
    # Start building rich text blocks
    rich_text_blocks = [
        {
            "type": "text", 
            "text": {"content": header_text}
        }
    ]
    
    # URL regex pattern
    url_pattern = r'(https?://[^\s]+)'
    
    # Check if the message contains URLs
    if re.search(url_pattern, message.text):
        # Split text by URLs
        parts = re.split(url_pattern, message.text)
        
        # Build rich text blocks with URLs as links
        for i, part in enumerate(parts):
            if i % 2 == 0:  # Regular text
                if part:  # Only add if not empty
                    rich_text_blocks.append({
                        "type": "text",
                        "text": {"content": part}
                    })
            else:  # URL part
                rich_text_blocks.append({
                    "type": "text",
                    "text": {
                        "content": part,
                        "link": {"url": part}
                    }
                })
    else:
        # No URLs, just add the text as is
        rich_text_blocks.append({
            "type": "text",
            "text": {"content": message.text}
        })
    
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": rich_text_blocks
        }
    }

def sync_messages_to_notion():
    """Sync unsynced messages to Notion"""
    logger.info("Starting Notion sync...")
    
    # Get Notion client and parent page ID
    notion_client = get_notion_client()
    parent_page_id = get_notion_page_id()  # Top level page ID that will contain monthly databases
    
    # Validate Notion client
    if not notion_client:
        error_msg = "Notion client not available - check your NOTION_INTEGRATION_SECRET environment variable"
        logger.error(error_msg)
        sync_status = SyncStatus()
        sync_status.messages_synced = 0
        sync_status.success = False
        sync_status.error_message = error_msg
        db.session.add(sync_status)
        db.session.commit()
        return
        
    # Validate parent page ID
    if not parent_page_id:
        error_msg = "Notion page ID not configured - check your NOTION_PAGE_ID environment variable"
        logger.error(error_msg)
        sync_status = SyncStatus()
        sync_status.messages_synced = 0
        sync_status.success = False
        sync_status.error_message = error_msg
        db.session.add(sync_status)
        db.session.commit()
        return
        
    # Log debug info
    logger.debug(f"Using Notion page ID: {parent_page_id}")
    
    # Verify Notion page exists
    try:
        logger.debug("Verifying parent page exists...")
        page_info = notion_client.pages.retrieve(page_id=parent_page_id)
        if isinstance(page_info, dict):
            logger.debug(f"Successfully verified parent page: {page_info.get('id')}")
        else:
            logger.debug(f"Successfully verified parent page exists (ID: {parent_page_id})")
    except Exception as e:
        error_msg = f"Error accessing Notion page with ID {parent_page_id}: {str(e)}"
        logger.error(error_msg)
        sync_status = SyncStatus()
        sync_status.messages_synced = 0
        sync_status.success = False
        sync_status.error_message = error_msg
        db.session.add(sync_status)
        db.session.commit()
        return
    
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
                # Create the database title to search for
                month_db_title = f"Messages {month_name} {year}"
                logger.debug(f"Looking for monthly database: '{month_db_title}'")
                
                # First, search for existing monthly databases in the parent page
                children_response = notion_client.blocks.children.list(block_id=parent_page_id)
                logger.debug(f"Found {len(children_response.get('results', []))} child blocks in parent page")
                
                # Look for child database blocks with matching title
                children_results = children_response.get("results", []) if isinstance(children_response, dict) else []
                for block in children_results:
                    if block.get("type") == "child_database":
                        block_id = block.get("id")
                        logger.debug(f"Found child database with ID: {block_id}")
                        
                        # Fetch database details to check title
                        db_details = notion_client.databases.retrieve(database_id=block_id)
                        db_title = db_details.get("title", []) if isinstance(db_details, dict) else []
                        
                        # Extract title text
                        title_parts = []
                        for text in db_title:
                            if isinstance(text, dict) and "text" in text:
                                title_parts.append(text["text"].get("content", ""))
                        title = "".join(title_parts)
                        logger.debug(f"Database title: '{title}'")
                        
                        if title == month_db_title:
                            logger.debug(f"Found matching monthly database with ID: {block_id}")
                            monthly_db_id = block_id
                            break
                
                if not monthly_db_id:
                    logger.debug(f"No matching monthly database found for '{month_db_title}'")
            except Exception as e:
                logger.error(f"Error searching for monthly database: {str(e)}", exc_info=True)
            
            # If not found, create new monthly database
            if not monthly_db_id:
                logger.debug(f"Creating new monthly database for {month_name} {year}")
                monthly_db_id = create_monthly_database(notion_client, parent_page_id, year, month)
            
            if not monthly_db_id:
                logger.error(f"Failed to get or create monthly database for {year}-{month}")
                continue
            
            # Get or create daily page
            daily_page_id = None
            
            # Try to find the daily page
            try:
                logger.debug(f"Searching for daily page for date: {date.strftime('%Y-%m-%d')} in database: {monthly_db_id}")
                daily_pages = notion_client.databases.query(
                    database_id=monthly_db_id,
                    filter={
                        "property": "Date",
                        "date": {
                            "equals": date.strftime("%Y-%m-%d")
                        }
                    }
                )
                
                if isinstance(daily_pages, dict):
                    results = daily_pages.get("results", [])
                    logger.debug(f"Found {len(results)} matching daily pages")
                    if results:
                        daily_page_id = results[0]["id"]
                        logger.debug(f"Using existing daily page: {daily_page_id}")
                else:
                    logger.debug(f"Query response is not a dictionary: {type(daily_pages)}")
            except Exception as e:
                logger.error(f"Error searching for daily page: {str(e)}", exc_info=True)
            
            if not daily_page_id:
                # Create new daily page
                logger.debug(f"Creating new daily page for date: {date.strftime('%Y-%m-%d')}")
                daily_page_id = create_daily_page(notion_client, monthly_db_id, date)
                if daily_page_id:
                    logger.debug(f"Created new daily page with ID: {daily_page_id}")
                else:
                    logger.error("Failed to create daily page")
            
            if not daily_page_id:
                logger.error(f"Failed to get or create daily page for {date}")
                continue
            
            # Format messages for Notion
            logger.debug(f"Formatting {len(messages)} messages for Notion")
            formatted_messages = []
            for message in messages:
                # Get formatted message blocks
                message_blocks = format_message_for_notion(message)
                
                # Handle both single blocks and lists of blocks
                if isinstance(message_blocks, list):
                    formatted_messages.extend(message_blocks)
                else:
                    formatted_messages.append(message_blocks)
            
            try:
                # Update daily page with messages
                logger.debug(f"Appending {len(formatted_messages)} message blocks to daily page {daily_page_id}")
                append_response = notion_client.blocks.children.append(
                    block_id=daily_page_id,
                    children=formatted_messages
                )
                logger.debug(f"Successfully appended blocks to page")
                
                # Get current message count if available
                current_count = 0
                try:
                    page_info = notion_client.pages.retrieve(page_id=daily_page_id)
                    if isinstance(page_info, dict) and "properties" in page_info:
                        message_prop = page_info["properties"].get("Messages", {})
                        if "number" in message_prop and message_prop["number"] is not None:
                            current_count = message_prop["number"]
                            logger.debug(f"Current message count: {current_count}")
                except Exception as e:
                    logger.warning(f"Could not retrieve current message count: {str(e)}")
                
                # Update messages count in the daily page (increment existing count)
                new_count = current_count + len(messages)
                logger.debug(f"Updating page properties to show {new_count} messages (added {len(messages)} new)")
                update_response = notion_client.pages.update(
                    page_id=daily_page_id,
                    properties={
                        "Messages": {"number": new_count},
                        "Status": {"select": {"name": "Synced"}}
                    }
                )
                logger.debug(f"Successfully updated page properties")
                
                # Mark messages as synced
                for message in messages:
                    message.synced = True
                    message.notion_page_id = daily_page_id
                
                total_synced += len(messages)
                logger.info(f"Successfully synced {len(messages)} messages for {date}")
            except Exception as e:
                logger.error(f"Error syncing messages to daily page: {str(e)}", exc_info=True)
                continue
        
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
