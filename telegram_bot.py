import os
import json
import logging
from datetime import datetime
from flask import jsonify
import requests
from app import db
from models import TelegramMessage, Setting
# Import the module that causes the "No module named 'replit.object_storage'" error
# when handle_telegram_update is called
import storage  # This pre-loads the storage module with all its dependencies

# Initialize logger
logger = logging.getLogger(__name__)

def get_telegram_token():
    """Get Telegram bot token from environment secrets"""
    import os
    return os.environ.get("TELEGRAM_BOT_TOKEN")

def setup_telegram_webhook(token, webhook_url):
    """Set up Telegram webhook URL"""
    try:
        api_url = f"https://api.telegram.org/bot{token}/setWebhook"
        response = requests.post(api_url, json={"url": webhook_url})
        data = response.json()
        
        if data.get("ok"):
            logger.info(f"Webhook set up successfully: {webhook_url}")
            return True
        else:
            logger.error(f"Failed to set up webhook: {data}")
            return False
    except Exception as e:
        logger.error(f"Error setting up webhook: {str(e)}")
        return False

def get_file_info(token, file_id):
    """Get file information from Telegram"""
    try:
        url = f"https://api.telegram.org/bot{token}/getFile"
        response = requests.get(url, params={"file_id": file_id})
        response.raise_for_status()
        data = response.json()
        
        if data.get("ok"):
            return data.get("result", {})
            
        logger.error(f"Failed to get file info: {data}")
        return None
    except Exception as e:
        logger.error(f"Error getting file info: {str(e)}")
        return None

def handle_telegram_update(update):
    """Process incoming Telegram update from webhook"""
    try:
        # Check if update contains a message
        if 'message' not in update:
            logger.debug("Update does not contain a message")
            return jsonify({"status": "ok", "message": "No message in update"})
        
        message = update['message']
        
        # Extract message details
        message_id = message.get('message_id')
        chat = message.get('chat', {})
        chat_id = chat.get('id')
        chat_title = chat.get('title', 'Private Chat')
        
        user = message.get('from', {})
        user_id = user.get('id')
        username = user.get('username', '')
        first_name = user.get('first_name', '')
        last_name = user.get('last_name', '')
        
        # Default to empty text
        text = ""
        
        # Handle different message types
        has_media = False
        media_type = None
        media_file_id = None
        
        # Check for text message
        if 'text' in message:
            text = message.get('text', '')
        
        # Check for photos
        elif 'photo' in message:
            has_media = True
            media_type = 'image'
            # Get largest photo
            photos = message.get('photo', [])
            if photos:
                # Sort by file size (largest last)
                photos.sort(key=lambda x: x.get('file_size', 0))
                photo = photos[-1]  # Get the largest photo
                media_file_id = photo.get('file_id')
                # Check if there's a caption
                text = message.get('caption', '')
        
        # Check for documents (files)
        elif 'document' in message:
            has_media = True
            document = message.get('document', {})
            media_file_id = document.get('file_id')
            mime_type = document.get('mime_type', '')
            
            # Set media type based on MIME type
            if mime_type.startswith('image/'):
                media_type = 'image'
            elif mime_type.startswith('video/'):
                media_type = 'video'
            elif mime_type.startswith('audio/'):
                media_type = 'audio'
            else:
                media_type = 'document'
                
            # Check if there's a caption
            text = message.get('caption', '')
        
        # Check for videos
        elif 'video' in message:
            has_media = True
            media_type = 'video'
            video = message.get('video', {})
            media_file_id = video.get('file_id')
            text = message.get('caption', '')
        
        # Check for audio
        elif 'audio' in message or 'voice' in message:
            has_media = True
            media_type = 'audio'
            audio = message.get('audio', message.get('voice', {}))
            media_file_id = audio.get('file_id')
            text = message.get('caption', '')
        
        # If no text and no media, skip this message
        if not text and not has_media:
            logger.debug("Message does not contain text or media")
            return jsonify({"status": "ok", "message": "No content in message"})
            
        date = message.get('date', 0)
        timestamp = datetime.fromtimestamp(date)
        
        # Create new message record
        new_message = TelegramMessage(
            message_id=message_id,
            chat_id=chat_id,
            chat_title=chat_title,
            user_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            text=text,
            timestamp=timestamp,
            synced=False
        )
        
        # Handle media if present
        if has_media and media_file_id:
            from storage import save_file_from_url
            
            # Get the token
            token = get_telegram_token()
            if not token:
                logger.error("No Telegram token found in settings")
                return jsonify({"status": "error", "message": "No Telegram token configured"})
            
            # Get file info from Telegram
            file_info = get_file_info(token, media_file_id)
            
            if file_info and 'file_path' in file_info:
                # Get file URL from Telegram
                file_path = file_info.get('file_path')
                file_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
                
                # Determine original filename
                original_filename = os.path.basename(file_path)
                
                # Save file to storage
                media_data = save_file_from_url(file_url, original_filename)
                
                if media_data:
                    # Update message with media data
                    new_message.media_type = media_data.get('media_type')
                    new_message.media_file_id = media_file_id
                    new_message.media_original_url = file_url
                    new_message.media_stored_path = media_data.get('stored_path')
                    new_message.media_size = media_data.get('size')
                    new_message.media_filename = original_filename
                    new_message.media_content_type = media_data.get('content_type')
                    
                    logger.info(f"Saved media file: {media_data.get('stored_path')}")
                else:
                    logger.error(f"Failed to save media file from URL: {file_url}")
            else:
                logger.error(f"Failed to get file info from Telegram for file ID: {media_file_id}")
        
        # Store full message data
        new_message.set_message_data(message)
        
        # Save to database
        db.session.add(new_message)
        db.session.commit()
        
        if has_media:
            logger.info(f"Saved message with {media_type} from {username} in {chat_title}")
        else:
            logger.info(f"Saved text message from {username} in {chat_title}")
            
        return jsonify({"status": "ok", "message": "Message saved"})
        
    except Exception as e:
        logger.error(f"Error processing Telegram update: {str(e)}")
        return jsonify({"status": "error", "message": str(e)})

def send_telegram_message(chat_id, text):
    """Send a message using the Telegram Bot API"""
    token = get_telegram_token()
    if not token:
        logger.error("No Telegram token found in settings")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        response = requests.post(url, json=data)
        result = response.json()
        
        if result.get("ok"):
            return True
        else:
            logger.error(f"Failed to send message: {result}")
            return False
    except Exception as e:
        logger.error(f"Error sending Telegram message: {str(e)}")
        return False
