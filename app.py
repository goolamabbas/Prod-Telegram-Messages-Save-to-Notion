import os
import logging
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from apscheduler.schedulers.background import BackgroundScheduler
import telegram
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

# Initialize logger
logger = logging.getLogger(__name__)

# Create SQLAlchemy base
class Base(DeclarativeBase):
    pass

# Initialize SQLAlchemy
db = SQLAlchemy(model_class=Base)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "a_default_secret_key_for_development")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize database with app
db.init_app(app)

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Import models after db initialization to avoid circular imports
with app.app_context():
    from models import User, TelegramMessage, SyncStatus, Setting
    db.create_all()
    
    # Create admin user if it doesn't exist
    admin = User.query.filter_by(username="admin").first()
    if not admin:
        admin = User(
            username="admin",
            email="admin@example.com",
            password_hash=generate_password_hash("admin")  # Default password, should be changed
        )
        db.session.add(admin)
        
        # Create default settings
        token_setting = Setting()
        token_setting.key = "telegram_token"
        token_setting.value = ""
        
        notion_secret = Setting()
        notion_secret.key = "notion_integration_secret"
        notion_secret.value = ""
        
        notion_page = Setting()
        notion_page.key = "notion_page_id"
        notion_page.value = ""
        
        db.session.add_all([token_setting, notion_secret, notion_page])
        db.session.commit()
        logger.info("Created admin user and default settings")

# Import route handlers
from telegram_bot import setup_telegram_webhook, handle_telegram_update, get_telegram_token
from notion_sync import sync_messages_to_notion

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    from datetime import datetime
    return render_template('index.html', now=datetime.now())

@app.route('/login', methods=['GET', 'POST'])
def login():
    from datetime import datetime
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and password and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('admin'))
        else:
            flash('Invalid username or password')
    
    return render_template('login.html', now=datetime.now())

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/admin')
@login_required
def admin():
    from datetime import datetime
    from models import TelegramMessage, SyncStatus, Setting
    
    # Get counts and stats
    total_messages = TelegramMessage.query.count()
    synced_messages = TelegramMessage.query.filter_by(synced=True).count()
    failed_syncs = SyncStatus.query.filter_by(success=False).count()
    
    # Get settings
    settings = {setting.key: setting.value for setting in Setting.query.all()}
    
    # Get recent messages
    recent_messages = TelegramMessage.query.order_by(TelegramMessage.timestamp.desc()).limit(10).all()
    
    # Get sync status
    sync_history = SyncStatus.query.order_by(SyncStatus.timestamp.desc()).limit(10).all()
    
    return render_template(
        'admin.html',
        total_messages=total_messages,
        synced_messages=synced_messages,
        failed_syncs=failed_syncs,
        settings=settings,
        recent_messages=recent_messages,
        sync_history=sync_history,
        now=datetime.now()
    )

# Settings now managed through Replit Secrets

@app.route('/admin/credentials', methods=['POST'])
@login_required
def update_admin_credentials():
    from models import User
    
    # Get form data
    new_username = request.form.get('new_username')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    # Validate input
    if not new_username and not new_password:
        flash('No changes provided', 'warning')
        return redirect(url_for('admin'))
    
    if new_password and new_password != confirm_password:
        flash('Passwords do not match', 'danger')
        return redirect(url_for('admin'))
    
    # Get the current admin user
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        flash('Admin user not found', 'danger')
        return redirect(url_for('admin'))
    
    # Update username if provided
    if new_username:
        # Check if username is already taken by another user
        existing_user = User.query.filter_by(username=new_username).first()
        if existing_user and existing_user.id != admin.id:
            flash(f'Username "{new_username}" is already taken', 'danger')
            return redirect(url_for('admin'))
        
        admin.username = new_username
    
    # Update password if provided
    if new_password:
        admin.password_hash = generate_password_hash(new_password)
    
    # Save changes
    db.session.commit()
    flash('Admin credentials updated successfully', 'success')
    
    # If the current user changed their own credentials, redirect to login
    if current_user.id == admin.id:
        logout_user()
        flash('Please login with your new credentials', 'info')
        return redirect(url_for('login'))
    
    return redirect(url_for('admin'))

@app.route('/admin/reset_database', methods=['POST'])
@login_required
def reset_database():
    from models import TelegramMessage, SyncStatus
    
    try:
        # Delete all messages and sync statuses
        TelegramMessage.query.delete()
        SyncStatus.query.delete()
        db.session.commit()
        flash('Database reset successfully')
    except Exception as e:
        db.session.rollback()
        flash(f'Error resetting database: {str(e)}', 'error')
    
    return redirect(url_for('admin'))

@app.route('/admin/sync_now', methods=['POST'])
@login_required
def trigger_sync():
    try:
        sync_messages_to_notion()
        flash('Sync triggered successfully')
    except Exception as e:
        flash(f'Error triggering sync: {str(e)}', 'error')
    
    return redirect(url_for('admin'))

@app.route('/api/stats')
@login_required
def get_stats():
    from models import TelegramMessage, SyncStatus
    from sqlalchemy import func
    
    # Get message counts by day (last 7 days)
    message_stats = db.session.query(
        func.date(TelegramMessage.timestamp).label('date'),
        func.count().label('count')
    ).group_by(func.date(TelegramMessage.timestamp)).order_by(func.date(TelegramMessage.timestamp).desc()).limit(7).all()
    
    # Get sync status counts
    from sqlalchemy.sql.expression import case
    sync_stats = db.session.query(
        func.date(SyncStatus.timestamp).label('date'),
        func.sum(case((SyncStatus.success == True, 1), else_=0)).label('success'),
        func.sum(case((SyncStatus.success == False, 1), else_=0)).label('failure')
    ).group_by(func.date(SyncStatus.timestamp)).order_by(func.date(SyncStatus.timestamp).desc()).limit(7).all()
    
    return jsonify({
        'message_stats': [{'date': str(row.date), 'count': row.count} for row in message_stats],
        'sync_stats': [{'date': str(row.date), 'success': row.success, 'failure': row.failure} for row in sync_stats]
    })

@app.route('/telegram/webhook', methods=['POST'])
def telegram_webhook():
    update = request.get_json()
    logger.debug(f"Received Telegram update: {update}")
    return handle_telegram_update(update)

@app.route('/api/setup_webhook', methods=['POST'])
@login_required
def api_setup_webhook():
    token = get_telegram_token()
    if not token:
        return jsonify({"success": False, "message": "Telegram token not set. Please save your token first."})
    
    # Generate webhook URL based on request URL
    host_url = request.host_url.rstrip('/')
    webhook_url = f"{host_url}/telegram/webhook"
    
    # Setup webhook with Telegram
    success = setup_telegram_webhook(token, webhook_url)
    
    if success:
        return jsonify({"success": True, "message": f"Webhook set up successfully: {webhook_url}"})
    else:
        return jsonify({"success": False, "message": "Failed to set up webhook. Please check your token and try again."})

# Define a wrapper for sync function to use app context
def sync_messages_job():
    with app.app_context():
        try:
            sync_messages_to_notion()
        except Exception as e:
            logger.error(f"Error in scheduled sync job: {str(e)}")

# Set up background tasks
scheduler = BackgroundScheduler()
scheduler.add_job(sync_messages_job, 'interval', minutes=5)
scheduler.start()

# Shutdown scheduler when app stops
import atexit
atexit.register(lambda: scheduler.shutdown())
