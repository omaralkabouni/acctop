import os
import shutil
from datetime import datetime, timedelta
import requests
from flask import current_app

def get_backup_dir():
    backup_dir = os.path.join(current_app.instance_path, 'backups')
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    return backup_dir

def create_backup(send_to_n8n=False):
    uri = current_app.config['SQLALCHEMY_DATABASE_URI']
    if uri.startswith('sqlite:///'):
        db_path = uri.replace('sqlite:///', '')
    else:
        # Fallback for other potential formats
        db_path = uri.split('///')[-1]

    # If relative, resolve it
    if not os.path.isabs(db_path):
        # Check standard locations: instance/ or root/
        possible_paths = [
            os.path.join(current_app.instance_path, db_path),
            os.path.join(current_app.instance_path, '..', db_path),
            os.path.join(os.getcwd(), db_path),
            db_path
        ]
        found = False
        for p in possible_paths:
            if os.path.exists(p):
                db_path = p
                found = True
                break
        if not found:
            raise FileNotFoundError(f"Database file not found at {db_path} or instance/ directory.")
    
    backup_dir = get_backup_dir()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f'backup_{timestamp}.db'
    backup_path = os.path.join(backup_dir, backup_filename)
    
    shutil.copy2(db_path, backup_path)
    
    # Cleanup old backups (older than 7 days)
    cleanup_old_backups()
    
    # Trigger n8n if requested and configured
    if send_to_n8n:
        from ..models.settings import SystemSettings
        settings = SystemSettings.get_settings()
        if settings.n8n_webhook_url:
            try:
                with open(backup_path, 'rb') as f:
                    requests.post(
                        settings.n8n_webhook_url,
                        files={'backup': f},
                        data={'event': 'daily_backup', 'filename': backup_filename}
                    )
            except Exception as e:
                print(f"Error sending backup to n8n: {e}")
            
    return backup_filename

def cleanup_old_backups():
    backup_dir = get_backup_dir()
    now = datetime.now()
    retention_days = 7
    
    for filename in os.listdir(backup_dir):
        file_path = os.path.join(backup_dir, filename)
        if os.path.isfile(file_path):
            file_time = datetime.fromtimestamp(os.path.getctime(file_path))
            if now - file_time > timedelta(days=retention_days):
                os.remove(file_path)

def restore_backup(filename):
    backup_dir = get_backup_dir()
    backup_path = os.path.join(backup_dir, filename)
    
    if not os.path.exists(backup_path):
        raise FileNotFoundError(f"Backup file {filename} not found.")

    # Find current DB path
    uri = current_app.config['SQLALCHEMY_DATABASE_URI']
    db_path = uri.replace('sqlite:///', '')
    if not os.path.isabs(db_path):
        # Resolve path - using same logic as create_backup or just instance path
        db_path = os.path.join(current_app.instance_path, db_path)

    # Create a safety backup of current state
    safety_name = f"safety_pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    shutil.copy2(db_path, os.path.join(backup_dir, safety_name))

    # Perform restore (overwrite)
    shutil.copy2(backup_path, db_path)
    return True

def list_backups():
    backup_dir = get_backup_dir()
    backups = []
    for filename in os.listdir(backup_dir):
        file_path = os.path.join(backup_dir, filename)
        if os.path.isfile(file_path):
            backups.append({
                'filename': filename,
                'size': os.path.getsize(file_path),
                'created_at': datetime.fromtimestamp(os.path.getctime(file_path))
            })
    return sorted(backups, key=lambda x: x['created_at'], reverse=True)
