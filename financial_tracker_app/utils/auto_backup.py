"""
Automatic Database Backup Utility
Handles automatic database backups on application startup
"""

import os
import sys
import importlib.util
from pathlib import Path

def get_backup_script_path():
    """Get the path to the db_backup.py script"""
    project_root = Path(__file__).parent.parent.parent
    backup_script = project_root / "scripts" / "db_backup.py"
    return str(backup_script)

def load_backup_module():
    """Load the backup module dynamically"""
    backup_script = get_backup_script_path()
    if not os.path.exists(backup_script):
        print(f"Warning: Backup script not found at: {backup_script}")
        return None
    
    try:
        # Load the backup module dynamically
        spec = importlib.util.spec_from_file_location("db_backup", backup_script)
        backup_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(backup_module)
        return backup_module
    except Exception as e:
        print(f"Error loading backup module: {e}")
        return None

def run_auto_backup():
    """Run automatic backup on application startup"""
    backup_module = load_backup_module()
    if backup_module:
        # Check if a backup should be created (based on time elapsed)
        if backup_module.should_create_backup():
            print("Creating automatic database backup...")
            backup_module.create_backup()
        else:
            print("Skipping automatic backup: Not enough time has passed since last backup")
    
        # Always apply retention policy to clean up old backups
        backup_module.apply_retention_policy()

if __name__ == "__main__":
    # For testing
    run_auto_backup()