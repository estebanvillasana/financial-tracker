# Expense Tracker GUI

A desktop expense tracking application built with Python, PyQt6, and SQLite.

## Features
- Add, view, edit, and delete expenses via a spreadsheet-like interface
- Categorize expenses (categories created automatically)
- Undo/Redo support for cell edits
- Visual indication of unsaved changes and validation errors
- Copy/Paste functionality in the table
- Dark theme for comfortable viewing
- Basic data validation on save

## Setup
1. Install Python 3.8 or higher
2. Install dependencies:
   ```bash
   pip install PyQt6==6.6.1
   # Other dependencies like tabulate/colorama are not needed for the GUI
   ```
3. Run the application:
   ```bash
   python -m financial_tracker_app.gui.main_window
   ```

   Alternatively, if you have a `financial_tracker_app/main.py` set up as the entry point:
   ```bash
   python financial_tracker_app/main.py
   ```

## Usage
The application provides a graphical user interface:
- **Add Transaction Form:** Quickly add new expenses or income using the form at the top. Defaults can be set via the 'Defaults' button.
- **Transaction Table:** View and edit existing transactions directly in the table.
    - Double-click, press Enter, or start typing on a cell to edit.
    - Use Enter to confirm edits, Escape to cancel.
    - Select rows and use the toolbar buttons or keyboard shortcuts (Ctrl+C, Ctrl+V, Delete).
    - Use the '+' button (bottom-right) or start typing in the empty row at the bottom to add a new transaction.
- **Action Buttons:** Access common actions like Save Changes, Discard Changes, Delete Selected, and Clear New Rows. Undo/Redo via Ctrl+Z/Ctrl+Y.
- **Status Messages:** Look for feedback messages below the action buttons.

## Data Persistence
- Transaction data is stored in an SQLite database file named `financial_tracker.db` in the project's root directory.
- Changes made in the table are highlighted (dark yellow for modified, dark blue for new) until saved.
- Click "Save Changes" to commit modifications to the database.
- Validation errors preventing a save will be highlighted (dark red background for the row, bright red for the specific cell).

## Database Structure
The application uses SQLite with the following tables:
- `transactions`: Stores individual transaction records (`rowid`, `transaction_name`, `transaction_value`, `account_id`, `transaction_type`, `transaction_category` (category_id), `transaction_sub_category` (sub_category_id), `transaction_description`, `transaction_date`).
- `bank_accounts`: Stores bank accounts (`id`, `account` (name), `currency`).
- `categories`: Stores transaction categories (`id`, `category` (name), `type` ('Income' or 'Expense')).
- `sub_categories`: Stores transaction subcategories (`id`, `sub_category` (name), `category_id`).
- `budgets`: (Currently unused by the GUI but table exists) Stores monthly budget information.