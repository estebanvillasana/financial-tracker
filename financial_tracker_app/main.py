import sys
from PyQt6.QtWidgets import QApplication

# Import necessary components from the new structure
from financial_tracker_app.gui.main_window import ExpenseTrackerGUI
from financial_tracker_app.gui.custom_style import CustomProxyStyle
from financial_tracker_app.utils.debug_control import show_debug_menu
from financial_tracker_app.utils.auto_backup import run_auto_backup

def main():
    """Main function to run the application."""
    app = QApplication(sys.argv)

    # Apply the custom style to the entire application
    custom_style = CustomProxyStyle()
    app.setStyle(custom_style)
    
    # Run automatic database backup
    print("Checking for automatic database backup...")
    run_auto_backup()

    # Add debug menu option
    if len(sys.argv) > 1 and sys.argv[1] == '--debug':
        show_debug_menu() # Assuming show_debug_menu handles its own logic now

    gui = ExpenseTrackerGUI()
    gui.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
