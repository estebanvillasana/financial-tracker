#!/usr/bin/env python3
"""
Enhanced database backup and restore script for Financial Tracker
with intelligent backup rotation and retention policies
"""

import os
import sys
import shutil
import datetime
import sqlite3
import json
import time
from pathlib import Path

# Add parent directory to Python path to import from project modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configuration
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB_FILE = os.path.join(PROJECT_ROOT, "financial_tracker_app", "data", "financial_tracker.db")
BACKUP_DIR = os.path.join(PROJECT_ROOT, "db_backups")
BACKUP_CONFIG_FILE = os.path.join(PROJECT_ROOT, "scripts", "backup_config.json")

# Default backup configuration
DEFAULT_CONFIG = {
    "min_hours_between_backups": 24,  # Minimum hours between regular backups
    "max_daily_backups": 2,           # Maximum number of backups to keep per day
    "max_weekly_backups": 7,          # Maximum number of weekly backups to keep
    "max_monthly_backups": 6,         # Maximum number of monthly backups to keep
    "max_yearly_backups": 5,          # Maximum number of yearly backups to keep
    "last_backup_time": 0             # Timestamp of the last backup
}

def load_backup_config():
    """Load backup configuration from file or create with defaults"""
    if os.path.exists(BACKUP_CONFIG_FILE):
        try:
            with open(BACKUP_CONFIG_FILE, 'r') as f:
                config = json.load(f)
                # Ensure all required fields are present
                for key, value in DEFAULT_CONFIG.items():
                    if key not in config:
                        config[key] = value
                return config
        except Exception as e:
            print(f"Error loading backup config: {e}")
    
    # If file doesn't exist or error occurred, create a new one with defaults
    save_backup_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG.copy()

def save_backup_config(config):
    """Save the backup configuration to file"""
    try:
        os.makedirs(os.path.dirname(BACKUP_CONFIG_FILE), exist_ok=True)
        with open(BACKUP_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"Error saving backup config: {e}")

def ensure_backup_dir():
    """Make sure the backup directory exists"""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
        print(f"Created backup directory: {BACKUP_DIR}")

def should_create_backup():
    """Determine if a backup should be created based on elapsed time"""
    config = load_backup_config()
    current_time = time.time()
    elapsed_hours = (current_time - config["last_backup_time"]) / 3600
    
    # Check if minimum time has passed since last backup
    if elapsed_hours < config["min_hours_between_backups"]:
        return False
    
    return True

def get_all_backups():
    """Get a list of all backup files with their metadata"""
    ensure_backup_dir()
    
    backups = []
    for file in os.listdir(BACKUP_DIR):
        if file.endswith(os.path.basename(DB_FILE)):
            backup_path = os.path.join(BACKUP_DIR, file)
            
            # Extract timestamp from filename
            try:
                timestamp_str = file.split('_')[0] + "_" + file.split('_')[1]
                timestamp = datetime.datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
            except:
                # If filename doesn't match expected format, use file creation time
                timestamp = datetime.datetime.fromtimestamp(os.path.getctime(backup_path))
            
            file_size = os.path.getsize(backup_path)
            
            # Try to get transaction count
            try:
                conn = sqlite3.connect(backup_path)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM transactions")
                count = cursor.fetchone()[0]
                conn.close()
            except:
                count = -1
            
            backups.append({
                "filename": file,
                "path": backup_path,
                "timestamp": timestamp,
                "date": timestamp.strftime("%Y-%m-%d"),
                "datetime_str": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "size": file_size,
                "size_mb": file_size / (1024 * 1024),
                "transactions": count
            })
    
    # Sort by timestamp (newest first)
    backups.sort(key=lambda x: x["timestamp"], reverse=True)
    return backups

def apply_retention_policy():
    """Apply the retention policy to remove excess backups"""
    config = load_backup_config()
    backups = get_all_backups()
    
    if not backups:
        return
    
    # Group backups by date, week, month, and year
    daily_backups = {}
    weekly_backups = {}
    monthly_backups = {}
    yearly_backups = {}
    
    for backup in backups:
        date = backup["timestamp"].date()
        
        # Daily grouping
        date_str = date.strftime("%Y-%m-%d")
        if date_str not in daily_backups:
            daily_backups[date_str] = []
        daily_backups[date_str].append(backup)
        
        # Weekly grouping (using ISO week)
        year, week, _ = date.isocalendar()
        week_key = f"{year}-W{week:02d}"
        if week_key not in weekly_backups:
            weekly_backups[week_key] = []
        weekly_backups[week_key].append(backup)
        
        # Monthly grouping
        month_key = date.strftime("%Y-%m")
        if month_key not in monthly_backups:
            monthly_backups[month_key] = []
        monthly_backups[month_key].append(backup)
        
        # Yearly grouping
        year_key = date.strftime("%Y")
        if year_key not in yearly_backups:
            yearly_backups[year_key] = []
        yearly_backups[year_key].append(backup)
    
    to_delete = set()
    
    # Remove excess daily backups, keeping the newest ones
    for day, day_backups in daily_backups.items():
        if len(day_backups) > config["max_daily_backups"]:
            # Skip the first max_daily_backups (newest ones)
            for backup in day_backups[config["max_daily_backups"]:]:
                to_delete.add(backup["path"])
    
    # Weekly retention (keep first backup of each week)
    week_keys = sorted(weekly_backups.keys(), reverse=True)
    for i, week_key in enumerate(week_keys):
        if i >= config["max_weekly_backups"]:
            for backup in weekly_backups[week_key]:
                to_delete.add(backup["path"])
        else:
            # For kept weeks, only keep the first (newest) backup
            for backup in weekly_backups[week_key][1:]:
                to_delete.add(backup["path"])
    
    # Monthly retention (similar logic)
    month_keys = sorted(monthly_backups.keys(), reverse=True)
    for i, month_key in enumerate(month_keys):
        if i >= config["max_monthly_backups"]:
            for backup in monthly_backups[month_key]:
                to_delete.add(backup["path"])
        else:
            # For kept months, retain only the first backup
            for backup in monthly_backups[month_key][1:]:
                if backup["path"] not in to_delete:
                    to_delete.add(backup["path"])
    
    # Yearly retention
    year_keys = sorted(yearly_backups.keys(), reverse=True)
    for i, year_key in enumerate(year_keys):
        if i >= config["max_yearly_backups"]:
            for backup in yearly_backups[year_key]:
                to_delete.add(backup["path"])
        else:
            # For kept years, retain only the first backup
            for backup in yearly_backups[year_key][1:]:
                if backup["path"] not in to_delete:
                    to_delete.add(backup["path"])
    
    # Delete the excess backups
    deleted_count = 0
    for path in to_delete:
        try:
            os.remove(path)
            deleted_count += 1
        except Exception as e:
            print(f"Error deleting {path}: {e}")
    
    if deleted_count > 0:
        print(f"Removed {deleted_count} old backups according to retention policy")

def create_backup(force=False):
    """Create a backup of the database"""
    if not os.path.exists(DB_FILE):
        print(f"Error: Database file {DB_FILE} not found!")
        return False
    
    # Check if we should create a backup
    if not force and not should_create_backup():
        print("Skipping backup: Not enough time has passed since last backup")
        return False
    
    ensure_backup_dir()
    
    # Create a timestamp for the backup filename
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(BACKUP_DIR, f"{timestamp}_{os.path.basename(DB_FILE)}")
    
    # Copy the database file
    try:
        shutil.copy2(DB_FILE, backup_file)
        print(f"Backup created: {backup_file}")
        
        # Update last backup time in config
        config = load_backup_config()
        config["last_backup_time"] = time.time()
        save_backup_config(config)
        
        # Apply retention policy
        apply_retention_policy()
        
        return True
    except Exception as e:
        print(f"Error creating backup: {e}")
        return False

def list_backups():
    """List all available backups"""
    backups = get_all_backups()
    
    if not backups:
        print("No backups found.")
        return
    
    # Print the backups
    print("\nAvailable Backups:")
    print(f"{'ID':<3} | {'Date':<19} | {'Size':<10} | {'Transactions':<12} | {'Filename'}")
    print("-" * 80)
    
    for i, backup in enumerate(backups, 1):
        size_str = f"{backup['size_mb']:.2f} MB"
        print(f"{i:<3} | {backup['datetime_str']:<19} | {size_str:<10} | {backup['transactions']:<12} | {backup['filename']}")
    
    print(f"\nTotal: {len(backups)} backups")

def restore_backup(backup_id=None):
    """Restore a database from backup"""
    backups = get_all_backups()
    
    if not backups:
        print("No backups found to restore.")
        return False
    
    if backup_id is None:
        # List backups and ask user to choose
        list_backups()
        try:
            choice = int(input("\nEnter backup ID to restore (or 0 to cancel): "))
            if choice == 0:
                print("Restore cancelled.")
                return False
            if choice < 1 or choice > len(backups):
                print("Invalid backup ID.")
                return False
            backup_file = backups[choice-1]["path"]
        except ValueError:
            print("Invalid input. Please enter a number.")
            return False
    else:
        try:
            idx = int(backup_id) - 1
            if idx < 0 or idx >= len(backups):
                print(f"Invalid backup ID: {backup_id}")
                return False
            backup_file = backups[idx]["path"]
        except ValueError:
            print(f"Invalid backup ID: {backup_id}")
            return False
    
    # Check if the current database exists and create a backup if it does
    if os.path.exists(DB_FILE):
        # Create a backup of the current database before restoring
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        pre_restore_backup = os.path.join(BACKUP_DIR, f"{timestamp}_pre_restore_{os.path.basename(DB_FILE)}")
        try:
            shutil.copy2(DB_FILE, pre_restore_backup)
            print(f"Created backup of current database: {pre_restore_backup}")
        except Exception as e:
            print(f"Warning: Could not backup current database: {e}")
    
    # Restore the selected backup
    try:
        shutil.copy2(backup_file, DB_FILE)
        print(f"Successfully restored database from: {os.path.basename(backup_file)}")
        return True
    except Exception as e:
        print(f"Error restoring backup: {e}")
        return False

def configure_backup_settings():
    """Configure backup retention settings"""
    config = load_backup_config()
    
    print("\nCurrent Backup Configuration:")
    print(f"- Minimum hours between backups: {config['min_hours_between_backups']}")
    print(f"- Maximum daily backups: {config['max_daily_backups']}")
    print(f"- Maximum weekly backups: {config['max_weekly_backups']}")
    print(f"- Maximum monthly backups: {config['max_monthly_backups']}")
    print(f"- Maximum yearly backups: {config['max_yearly_backups']}")
    print(f"- Last backup time: {datetime.datetime.fromtimestamp(config['last_backup_time']).strftime('%Y-%m-%d %H:%M:%S') if config['last_backup_time'] > 0 else 'Never'}")
    
    print("\nUpdate settings (press Enter to keep current value):")
    
    try:
        min_hours = input(f"Minimum hours between backups [{config['min_hours_between_backups']}]: ")
        if min_hours.strip():
            config['min_hours_between_backups'] = float(min_hours)
        
        max_daily = input(f"Maximum daily backups [{config['max_daily_backups']}]: ")
        if max_daily.strip():
            config['max_daily_backups'] = int(max_daily)
        
        max_weekly = input(f"Maximum weekly backups [{config['max_weekly_backups']}]: ")
        if max_weekly.strip():
            config['max_weekly_backups'] = int(max_weekly)
        
        max_monthly = input(f"Maximum monthly backups [{config['max_monthly_backups']}]: ")
        if max_monthly.strip():
            config['max_monthly_backups'] = int(max_monthly)
        
        max_yearly = input(f"Maximum yearly backups [{config['max_yearly_backups']}]: ")
        if max_yearly.strip():
            config['max_yearly_backups'] = int(max_yearly)
        
        save_backup_config(config)
        print("Backup settings updated successfully.")
        
        # Apply retention policy with new settings
        apply_retention_policy()
        
    except ValueError:
        print("Invalid input. Settings not updated.")

def show_help():
    """Show help information"""
    print("""
Enhanced Database Backup Tool for Financial Tracker

Usage:
  python db_backup.py [command]

Commands:
  backup             - Create a new backup of the database
  backup-force       - Force creation of a backup, ignoring time constraints
  list               - List all available backups
  restore            - Restore the database from a backup (interactive)
  cleanup            - Apply retention policy to remove old backups
  config             - Configure backup settings
  help               - Show this help message

Examples:
  python db_backup.py backup        # Create a new backup if enough time has passed
  python db_backup.py backup-force  # Force creation of a backup
  python db_backup.py list          # List all backups
  python db_backup.py restore       # Restore from a backup (interactive)
  python db_backup.py cleanup       # Clean up old backups
  python db_backup.py config        # Configure backup settings
    """)

def main():
    """Main function to handle command line arguments"""
    if len(sys.argv) < 2:
        show_help()
        sys.exit(0)
    
    command = sys.argv[1].lower()
    
    if command == "backup":
        create_backup()
    elif command == "backup-force":
        create_backup(force=True)
    elif command == "list":
        list_backups()
    elif command == "restore":
        restore_backup()
    elif command == "cleanup":
        apply_retention_policy()
    elif command == "config":
        configure_backup_settings()
    elif command == "help":
        show_help()
    else:
        print(f"Unknown command: {command}")
        show_help()

if __name__ == "__main__":
    main()
