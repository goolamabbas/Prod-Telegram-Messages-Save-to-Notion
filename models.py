from datetime import datetime
from app import db
from flask_login import UserMixin
import json

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

class TelegramMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, nullable=False)
    chat_id = db.Column(db.BigInteger, nullable=False)
    chat_title = db.Column(db.String(255))
    user_id = db.Column(db.BigInteger)
    username = db.Column(db.String(255))
    first_name = db.Column(db.String(255))
    last_name = db.Column(db.String(255))
    text = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    message_data = db.Column(db.Text)  # Store full message JSON
    synced = db.Column(db.Boolean, default=False)
    notion_page_id = db.Column(db.String(255), nullable=True)
    
    def set_message_data(self, message_data):
        self.message_data = json.dumps(message_data)
    
    def get_message_data(self):
        if self.message_data:
            return json.loads(self.message_data)
        return None

class SyncStatus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    messages_synced = db.Column(db.Integer, default=0)
    success = db.Column(db.Boolean, default=True)
    error_message = db.Column(db.Text, nullable=True)
    
class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(255), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
