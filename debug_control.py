"""
Debug Control Interface for Financial Tracker

This module provides a simple command-line interface to control debug settings.
It can be imported and used directly in the application or run as a standalone script.
"""

import sys
from debug_config import debug_config

def show_debug_menu():
    """Display the debug configuration menu"""
    while True:
        debug_config.print_status()

        print("Debug Control Menu:")
        print("------------------")
        print("1. Toggle a debug category")
        print("2. Enable all categories")
        print("3. Disable all categories")
        print("4. Return to application")
        print("5. Exit program")

        choice = input("\nEnter your choice (1-5): ")

        if choice == "1":
            toggle_category()
            # Save settings after changes
            debug_config.save_settings()
        elif choice == "2":
            debug_config.enable_all()
            print("All debug categories enabled.")
            # Save settings after changes
            debug_config.save_settings()
        elif choice == "3":
            debug_config.disable_all()
            print("All debug categories disabled.")
            # Save settings after changes
            debug_config.save_settings()
        elif choice == "4":
            # Save settings before returning to application
            debug_config.save_settings()
            break
        elif choice == "5":
            print("Exiting program...")
            # Save settings before exiting
            debug_config.save_settings()
            sys.exit(0)
        else:
            print("Invalid choice. Please try again.")

def toggle_category():
    """Toggle a specific debug category"""
    # Display categories with numbers
    categories = list(debug_config.CATEGORIES.keys())

    print("\nAvailable Categories:")
    for i, category in enumerate(categories, 1):
        status = "ENABLED" if debug_config.is_enabled(category) else "disabled"
        print(f"{i}. {category} ({status})")

    try:
        choice = int(input("\nEnter category number to toggle (or 0 to cancel): "))
        if choice == 0:
            return
        elif 1 <= choice <= len(categories):
            category = categories[choice - 1]
            debug_config.toggle(category)
            status = "enabled" if debug_config.is_enabled(category) else "disabled"
            print(f"{category} is now {status}.")
        else:
            print("Invalid category number.")
    except ValueError:
        print("Please enter a valid number.")

if __name__ == "__main__":
    print("Financial Tracker Debug Control")
    print("===============================")
    show_debug_menu()
