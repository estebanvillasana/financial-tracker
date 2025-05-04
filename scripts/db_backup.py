#!/usr/bin/env python3
"""
Simple database backup and restore script for Financial Tracker
"""

import os
import sys
import shutil
import datetime
import sqlite3
from pathlib import Path

# Configuration
DB_FILE = "financial_tracker.db"
BACKUP_DIR = "db_backups"

def ensure_backup_dir():
    """Make sure the backup directory exists"""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
        print(f"Created backup directory: {BACKUP_DIR}")

def create_backup():
    """Create a backup of the database"""
    if not os.path.exists(DB_FILE):
        print(f"Error: Database file {DB_FILE} not found!")
        return False
    
    ensure_backup_dir()
    
    # Create a timestamp for the backup filename
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(BACKUP_DIR, f"{timestamp}_{DB_FILE}")
    
    # Copy the database file
    try:
        shutil.copy2(DB_FILE, backup_file)
        print(f"Backup created: {backup_file}")
        return True
    except Exception as e:
        print(f"Error creating backup: {e}")
        return False

def list_backups():
    """List all available backups"""
    ensure_backup_dir()
    
    backups = []
    for file in os.listdir(BACKUP_DIR):
        if file.endswith(DB_FILE):
            backup_path = os.path.join(BACKUP_DIR, file)
            timestamp = file.split('_')[0]
            size = os.path.getsize(backup_path) / (1024 * 1024)  # Size in MB
            
            # Try to get transaction count
            try:
                conn = sqlite3.connect(backup_path)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM transactions")
                count = cursor.fetchone()[0]
                conn.close()
            except:
                count = "Unknown"
            
            # Format the timestamp for display
            try:
                date_obj = datetime.datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
                formatted_date = date_obj.strftime("%Y-%m-%d %H:%M:%S")
            except:
                formatted_date = timestamp
            
            backups.append((file, formatted_date, f"{size:.2f} MB", count))
    
    if not backups:
        print("No backups found.")
        return
    
    # Print the backups
    print("\nAvailable Backups:")
    print(f"{'ID':<3} | {'Date':<19} | {'Size':<10} | {'Transactions':<12} | {'Filename'}")
    print("-" * 80)
    
    for i, (file, date, size, count) in enumerate(backups, 1):
        print(f"{i:<3} | {date:<19} | {size:<10} | {count:<12} | {file}")

def restore_backup(backup_id=None):
    """Restore a database from backup"""
    ensure_backup_dir()
    
    backups = [f for f in os.listdir(BACKUP_DIR) if f.endswith(DB_FILE)]
    if not backups:
        print("No backups found to restore.")
        return False
    
    # Sort backups by timestamp (newest first)
    backups.sort(reverse=True)
    
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
            backup_file = os.path.join(BACKUP_DIR, backups[choice-1])
        except ValueError:
            print("Invalid input. Please enter a number.")
            return False
    else:
        try:
            idx = int(backup_id) - 1
            if idx < 0 or idx >= len(backups):
                print(f"Invalid backup ID: {backup_id}")
                return False
            backup_file = os.path.join(BACKUP_DIR, backups[idx])
        except ValueError:
            print(f"Invalid backup ID: {backup_id}")
            return False
    
    # Check if the current database exists and create a backup if it does
    if os.path.exists(DB_FILE):
        # Create a backup of the current database before restoring
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        pre_restore_backup = os.path.join(BACKUP_DIR, f"{timestamp}_pre_restore_{DB_FILE}")
        try:
            shutil.copy2(DB_FILE, pre_restore_backup)
            print(f"Created backup of current database: {pre_restore_backup}")
        except Exception as e:
            print(f"Warning: Could not backup current database: {e}")
    
    # Restore the selected backup
    try:
        shutil.copy2(backup_file, DB_FILE)
        print(f"Successfully restored database from: {backup_file}")
        return True
    except Exception as e:
        print(f"Error restoring backup: {e}")
        return False

def show_help():
    """Show help information"""
    print("""
Database Backup Tool for Financial Tracker

Usage:
  python db_backup.py [command]

Commands:
  backup   - Create a new backup of the database
  list     - List all available backups
  restore  - Restore the database from a backup
  help     - Show this help message

Examples:
  python db_backup.py backup   # Create a new backup
  python db_backup.py list     # List all backups
  python db_backup.py restore  # Restore from a backup (interactive)
    """)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        show_help()
        sys.exit(0)
    
    command = sys.argv[1].lower()
    
    if command == "backup":
        create_backup()
    elif command == "list":
        list_backups()
    elif command == "restore":
        restore_backup()
    elif command == "help":
        show_help()
    else:
        print(f"Unknown command: {command}")
        show_help()
