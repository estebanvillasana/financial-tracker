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
   python expense_tracker_gui.py
   ```

## Usage
The application provides a graphical user interface:
- **Add Transaction Form:** Quickly add new expenses using the form at the top.
- **Transaction Table:** View and edit existing transactions directly in the table.
    - Double-click or start typing on a cell to edit.
    - Use Enter to confirm edits, Escape to cancel.
    - Select rows and use the toolbar buttons or keyboard shortcuts (Ctrl+C, Ctrl+V, Delete).
    - Use the '+' button or Alt+N to add a new blank row for entry.
- **Toolbar:** Access common actions like Save, Discard, Delete, Clear New Rows, Undo, and Redo.
- **Status Messages:** Look for feedback messages at the bottom of the window.

## Data Persistence
- Expense data is stored in an SQLite database file named `expenses.db` in the same directory as the script.
- Changes made in the table are highlighted (yellowish for modified, bluish for new) until saved.
- Click "Save Changes" in the toolbar to commit modifications to the database.
- Validation errors preventing a save will be highlighted (red background).

## Database Structure
The application uses SQLite with the following tables:
- `expenses`: Stores individual expense records (id, name, amount, category_id, description, date)
- `categories`: Stores expense categories (id, name)
- `budgets`: (Currently unused by the GUI but table exists) Stores monthly budget information (id, category_id, amount, month)
```