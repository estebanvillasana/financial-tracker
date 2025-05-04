"""
Debug Control Interface for Financial Tracker

This module provides a simple command-line interface to control debug settings.
It can be imported and used directly in the application or run as a standalone script.
"""

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
        
        choice = input("\nEnter your choice (1-4): ")
        
        if choice == "1":
            toggle_category()
        elif choice == "2":
            debug_config.enable_all()
            print("All debug categories enabled.")
        elif choice == "3":
            debug_config.disable_all()
            print("All debug categories disabled.")
        elif choice == "4":
            break
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
        choice = int(input("\nEnter category number to toggle: "))
        if 1 <= choice <= len(categories):
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
