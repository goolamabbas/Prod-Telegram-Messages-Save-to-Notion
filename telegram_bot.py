import os
import json
import logging
from datetime import datetime
from flask import jsonify
import requests
from app import db
from models import TelegramMessage, Setting

# Initialize logger
logger = logging.getLogger(__name__)

def get_telegram_token():
    """Get Telegram bot token from settings database"""
    setting = Setting.query.filter_by(key="telegram_token").first()
    if setting and setting.value:
        return setting.value
    return None

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

def handle_telegram_update(update):
    """Process incoming Telegram update from webhook"""
    try:
        # Check if update contains a message
        if 'message' not in update:
            logger.debug("Update does not contain a message")
            return jsonify({"status": "ok", "message": "No message in update"})
        
        message = update['message']
        
        # Skip messages without text
        if 'text' not in message:
            logger.debug("Message does not contain text")
            return jsonify({"status": "ok", "message": "No text in message"})
        
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
        
        text = message.get('text', '')
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
        
        # Store full message data
        new_message.set_message_data(message)
        
        # Save to database
        db.session.add(new_message)
        db.session.commit()
        
        logger.info(f"Saved message from {username} in {chat_title}")
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
