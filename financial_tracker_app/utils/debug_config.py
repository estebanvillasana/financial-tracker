"""
Debug Configuration Module for Financial Tracker

This module provides a centralized way to control debug output in the application.
It allows enabling/disabling different categories of debug messages.
"""

import os
import json

# Configuration file path
DEBUG_CONFIG_FILE = "debug_settings.json"

class DebugConfig:
    """Configuration class for controlling debug output"""

    # Debug categories
    CATEGORIES = {
        'TABLE_DISPLAY': 'Table contents display',
        'UNDERLYING_DATA': 'Underlying data structures',
        'DATE_ARROWS': 'Date arrow rectangles positioning',
        'ACCOUNT_CONVERSION': 'Account ID conversion',
        'SUBCATEGORY': 'Subcategory handling',
        'CATEGORY': 'Category handling',
        'CURRENCY': 'Currency formatting',
        'DROPDOWN': 'Dropdown selection',
        'FOREIGN_KEYS': 'Foreign key validation',
        'CLICK_DETECTION': 'Mouse click detection',
    }

    def __init__(self):
        # Default configuration - all disabled except for a few
        self.default_settings = {
            'TABLE_DISPLAY': True,      # Keep table display on by default
            'UNDERLYING_DATA': True,    # Keep underlying data on by default
            'DATE_ARROWS': False,
            'ACCOUNT_CONVERSION': False,
            'SUBCATEGORY': False,
            'CATEGORY': False,
            'CURRENCY': False,
            'DROPDOWN': False,
            'FOREIGN_KEYS': False,
            'CLICK_DETECTION': False,
        }

        # Initialize with defaults
        self.enabled_categories = self.default_settings.copy()

        # Try to load saved settings
        self.load_settings()

    def is_enabled(self, category):
        """Check if a debug category is enabled"""
        return self.enabled_categories.get(category, False)

    def enable(self, category):
        """Enable a debug category"""
        if category in self.enabled_categories:
            self.enabled_categories[category] = True

    def disable(self, category):
        """Disable a debug category"""
        if category in self.enabled_categories:
            self.enabled_categories[category] = False

    def toggle(self, category):
        """Toggle a debug category"""
        if category in self.enabled_categories:
            self.enabled_categories[category] = not self.enabled_categories[category]

    def enable_all(self):
        """Enable all debug categories"""
        for category in self.enabled_categories:
            self.enabled_categories[category] = True

    def disable_all(self):
        """Disable all debug categories"""
        for category in self.enabled_categories:
            self.enabled_categories[category] = False

    def save_settings(self):
        """Save debug settings to a JSON file"""
        try:
            with open(DEBUG_CONFIG_FILE, 'w') as f:
                json.dump(self.enabled_categories, f, indent=4)
            print("Debug settings saved.")
        except Exception as e:
            print(f"Error saving debug settings: {e}")

    def load_settings(self):
        """Load debug settings from a JSON file"""
        try:
            if os.path.exists(DEBUG_CONFIG_FILE):
                with open(DEBUG_CONFIG_FILE, 'r') as f:
                    saved_settings = json.load(f)

                    # Validate loaded settings against known categories
                    for category in self.CATEGORIES:
                        if category in saved_settings:
                            self.enabled_categories[category] = saved_settings[category]
        except Exception as e:
            print(f"Error loading debug settings: {e}")
            # Fall back to defaults if there's an error
            self.enabled_categories = self.default_settings.copy()

    def print_status(self):
        """Print the current debug configuration status"""
        print("\n===== DEBUG CONFIGURATION =====")
        for category, description in self.CATEGORIES.items():
            status = "ENABLED" if self.enabled_categories.get(category, False) else "disabled"
            print(f"{category:<20}: {status:<10} - {description}")
        print("==============================\n")


# Create a global instance for use throughout the application
debug_config = DebugConfig()


def debug_print(category, message):
    """Print a debug message if the category is enabled"""
    if debug_config.is_enabled(category):
        print(f"DEBUG {category}: {message}")
