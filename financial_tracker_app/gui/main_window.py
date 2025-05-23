# --- START OF FILE expense_tracker_gui.py ---

import sys
import os
import re
import sqlite3
from datetime import datetime
from decimal import Decimal, InvalidOperation # Import Decimal

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QTableWidget, QTableWidgetItem,
                             QPushButton, QLineEdit, QComboBox, QLabel,
                             QMessageBox, QHeaderView, QAbstractItemView, QFrame, QDialog,
                             QGridLayout, QGroupBox, QDateEdit, QToolButton,
                             QStyle, QToolBar, QTableWidgetSelectionRange)
# Import QEvent for eventFilter
from PyQt6.QtCore import Qt, QTimer, QDate, QModelIndex, QSize, QLocale, QEvent, QPoint
# Import QIcon
from PyQt6.QtGui import (QKeySequence, QShortcut, QColor, QFont, QIcon,
                         QKeyEvent, QUndoStack, QGuiApplication, QBrush)

# --- Updated Imports ---
from financial_tracker_app.data.database import Database
from financial_tracker_app.gui.delegates import SpreadsheetDelegate
from financial_tracker_app.logic.commands import CellEditCommand
from financial_tracker_app.data.column_config import TRANSACTION_COLUMNS, DB_FIELDS, DISPLAY_TITLES, get_column_config
from financial_tracker_app.gui.custom_widgets import ArrowComboBox, ArrowDateEdit
from financial_tracker_app.gui.custom_style import CustomProxyStyle
from financial_tracker_app.logic.default_values import default_values
from financial_tracker_app.gui.default_values_ui import show_default_values_dialog
from financial_tracker_app.gui.description_dialog import show_description_dialog
from financial_tracker_app.gui.transaction_details_dialog import show_transaction_details_dialog
from financial_tracker_app.utils.debug_config import debug_config, debug_print
from financial_tracker_app.utils.debug_control import show_debug_menu
# Import field mapping utilities
from financial_tracker_app.utils.field_mappings import (
    ensure_related_fields, ensure_id_field, ensure_display_field,
    get_id_for_name, get_name_for_id, get_data_source_for_field
)
# --- End Updated Imports ---

class ExpenseTrackerGUI(QMainWindow):
    # Define the columns for the *display* table (match the data we'll fetch)
    # Use the column configuration from column_config.py
    COLS = DB_FIELDS

    def __init__(self):
        super().__init__()
        self.db = Database()

        # Use category manager from database
        self.category_manager = self.db.category_manager

        self.transactions = []
        self.pending = []
        self.dirty = set()
        self.dirty_fields = {}
        self.errors = {}
        self._original_data_cache = {}
        self.undo_stack = QUndoStack(self)
        self.last_saved_undo_index = 0
        self.selected_rows = set()
        self.locale = QLocale() # Add locale for consistent formatting
        self.form_widgets = {} # Dictionary to hold form input widgets

        # Initialize dropdown data
        self._accounts_data = []
        self._categories_data = []
        self._subcategories_data = []

        self._build_ui()
        self._load_dropdown_data() # Load dropdown data first
        self._load_transactions() # Then load transactions
        self._populate_initial_form_dropdowns() # Populate dropdowns based on loaded data
        # Apply default values to the form inputs on startup
        default_values.apply_to_form(self.form_widgets)

        # Pass data sources to the delegate
        delegate = self.tbl.itemDelegate()
        if isinstance(delegate, SpreadsheetDelegate): # Ensure it's the correct type
            delegate.setEditorDataSources(self._accounts_data, self._categories_data, self._subcategories_data)

    def _build_ui(self):
        self.setWindowTitle('Expense Tracker')
        self.resize(1200, 800)
        central = QWidget(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # Create menu bar
        menubar = self.menuBar()

        # Add Help menu
        help_menu = menubar.addMenu('Help')

        # Add Debug Settings action
        debug_action = help_menu.addAction('Debug Settings')
        debug_action.triggered.connect(show_debug_menu)

        # --- Stylesheet (Simplified Arrow Styling) ---
        self.setStyleSheet(r'''
            QMainWindow { background:#23272e; }
            QWidget, QTableWidget, QDateEdit, QDateEdit QCalendarWidget QWidget {
                background:#23272e; color:#f3f3f3;
                font-family:Segoe UI,Arial,sans-serif; font-size:14px; }
            QLineEdit, QComboBox, QDateEdit {
                border: 1.5px solid #444;
                border-radius: 4px;
                padding: 6px;
                background: #2d323b;
                color: #f3f3f3;
            }
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus {
                border: 1.5px solid #4fc3f7;
            }

            ArrowComboBox:focus {
                border: 1.5px solid #4fc3f7;
                outline: none;
            }
            QLineEdit[error="true"], QComboBox[error="true"] {
                border: 2px solid #ff5252;
                background: #5c2c2c;
            }
            QHeaderView::section { background:#23272e; color:#f3f3f3;
                                   font-weight:bold; border:1px solid #444; padding:6px; }
            QLineEdit, QComboBox, QDateEdit, QDateEdit QAbstractItemView {
                background:#2d323b; color:#f3f3f3;
                border:1px solid #444; border-radius:4px; padding:6px; }

            /* Common styling for all dropdown widgets */
            QComboBox, QDateEdit {
                background: #2d323b;
                color: #f3f3f3;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 6px;
                padding-right: 15px; /* Minimal padding for the arrow */
                min-height: 20px;
            }

            /* Style the dropdown button for standard QComboBox */
            QComboBox::drop-down, QDateEdit::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 12px; /* Minimal width of the clickable area */
                background: transparent;
                border: none; /* No border */
            }

            /* Hide the default down arrow for QComboBox and QDateEdit */
            QComboBox::down-arrow, QDateEdit::down-arrow {
                width: 0px;
                height: 0px;
                background: transparent;
            }

            /* Ensure date fields have the same styling as dropdowns */
            QDateEdit {
                padding-right: 15px; /* Space for our custom arrow */
            }

            /* Style the dropdown popup */
            QComboBox QAbstractItemView, ArrowComboBox QAbstractItemView, QDateEdit QAbstractItemView {
                background-color: #2d323b;
                border: 1px solid #555;
                selection-background-color: #4a6984;
                padding: 4px;
                border-radius: 3px;
            }

            /* Focus styling */
            QComboBox:focus, ArrowComboBox:focus, QDateEdit:focus {
                border: 1.5px solid #4fc3f7;
                outline: none;
            }
            QCalendarWidget QToolButton {
                color: #f3f3f3; background-color: #3a3f4b; border: none; font-weight: bold;
                icon-size: 18px; padding: 5px; margin: 2px; }
            QCalendarWidget QMenu { background-color: #2d323b; color: #f3f3f3; }
            QCalendarWidget QSpinBox { background-color: #2d323b; color: #f3f3f3; border: 1px solid #444; }
            QCalendarWidget QWidget#qt_calendar_navigationbar { background-color: #23272e; border-bottom: 1px solid #444; }
            QCalendarWidget QTableView { background-color: #23272e; alternate-background-color: #262b33; selection-background-color: #4a6984; }
            QCalendarWidget QWidget#qt_calendar_calendarview { border: none; }
            QPushButton { background:#3a3f4b; color:#f3f3f3;
                                   border-radius:6px; padding:8px 15px;
                                   font-weight:bold;
                                   padding-left: 30px; /* Space on left for icon */
                                   text-align: left; /* Align text next to icon */
                                   }
            QPushButton#fab { /* Specific style for FAB */
                padding: 0px; padding-left: 0px; text-align: center;
                background:#4fc3f7; color:#23272e; border-radius:28px;
                font-size:28px; font-weight:bold;
            }
            QPushButton#fab:hover { background:#29b6f6; }
            QPushButton:hover { background:#4a4f5b; }
            QPushButton:disabled { background:#444; color:#888; }
            QTableWidget { gridline-color: #444; }
            QTableWidget::item { padding: 4px; }
            QTableWidget::item:selected { background-color: #4a6984; color: #f3f3f3; }
            QGroupBox { border: 1px solid #444; border-radius: 6px; margin-top: 10px; padding: 10px; }
            QGroupBox:title { subcontrol-origin: margin; left: 10px; padding: 0 4px 0 4px; color: #81d4fa; font-size: 14px; font-weight: bold; }
            QToolButton { background-color: #3a3f4b; border-radius: 4px; padding: 4px; }
            QToolButton:hover { background-color: #4a4f5b; }
            QToolBar { background-color: #23272e; border: none; spacing: 6px; }
        ''')

        # --- Form Group ---
        form_group = QGroupBox('Add Transaction')
        form_grid = QGridLayout()
        form_grid.setHorizontalSpacing(15)
        form_grid.setVerticalSpacing(10)
        form_group.setLayout(form_grid)

        # Create and register form widgets
        self.name_in = QLineEdit(placeholderText='Transaction Name')
        self.value_in = QLineEdit(placeholderText='Value (e.g., 12.34)')
        self.type_in = ArrowComboBox()
        self.type_in.addItems(['Expense', 'Income'])
        self.account_in = ArrowComboBox()
        self.cat_in = ArrowComboBox()
        self.subcat_in = ArrowComboBox()

        # Create a single-line text field for description with a button to open dialog
        self.desc_in = QLineEdit(placeholderText='Description')

        # Create a button to open the description dialog
        self.desc_btn = QPushButton("...")
        self.desc_btn.setToolTip("Edit description in multi-line editor")
        self.desc_btn.setFixedWidth(30)
        self.desc_btn.clicked.connect(self._open_description_dialog)

        self.date_in = ArrowDateEdit(parent=self)
        self.date_in.setDate(QDate.currentDate())
        self.date_in.setDisplayFormat("dd MMM yyyy")

        # Register form widgets for default values dialog and application
        self.form_widgets = {
            'name_in': self.name_in,
            'value_in': self.value_in,
            'type_in': self.type_in,
            'account_in': self.account_in,
            'cat_in': self.cat_in,
            'subcat_in': self.subcat_in,
            'desc_in': self.desc_in,
            'date_in': self.date_in
        }

        form_grid.addWidget(QLabel('Name:'), 0, 0)
        form_grid.addWidget(self.name_in, 0, 1)
        form_grid.addWidget(QLabel('Value:'), 0, 2)
        form_grid.addWidget(self.value_in, 0, 3)
        form_grid.addWidget(QLabel('Type:'), 1, 0)
        form_grid.addWidget(self.type_in, 1, 1)
        form_grid.addWidget(QLabel('Account:'), 1, 2)
        form_grid.addWidget(self.account_in, 1, 3)
        form_grid.addWidget(QLabel('Category:'), 2, 0)
        form_grid.addWidget(self.cat_in, 2, 1)
        form_grid.addWidget(QLabel('Sub Category:'), 2, 2)
        form_grid.addWidget(self.subcat_in, 2, 3)
        form_grid.addWidget(QLabel('Description:'), 3, 0)

        # Create a horizontal layout for description field and button
        desc_layout = QHBoxLayout()
        desc_layout.setContentsMargins(0, 0, 0, 0)
        desc_layout.addWidget(self.desc_in, stretch=1)
        desc_layout.addWidget(self.desc_btn)

        # Add the layout to the form grid
        desc_container = QWidget()
        desc_container.setLayout(desc_layout)
        form_grid.addWidget(desc_container, 3, 1, 1, 3)
        form_grid.addWidget(QLabel('Date:'), 4, 0)
        form_grid.addWidget(self.date_in, 4, 1)

        self.add_btn = QPushButton('Add Transaction')
        self.add_btn.setIcon(QIcon.fromTheme("list-add", QIcon(":/icons/add.png")))
        self.add_btn.clicked.connect(self._add_form)
        form_grid.addWidget(self.add_btn, 5, 0, 1, 2) # Span 2 columns

        # Button to open Default Values dialog
        self.defaults_btn = QPushButton('Defaults')
        self.defaults_btn.setIcon(QIcon.fromTheme("preferences-system", QIcon(":/icons/settings.png")))
        self.defaults_btn.setToolTip("Set default values for new transactions")
        self.defaults_btn.clicked.connect(self._open_default_values)
        form_grid.addWidget(self.defaults_btn, 5, 2, 1, 2) # Span 2 columns

        root.addWidget(form_group)
        # --- End Form Group ---

        # --- Action Buttons ---
        btn_layout = QHBoxLayout()

        # Create a group for data manipulation buttons (left side)
        data_btn_layout = QHBoxLayout()
        data_btn_layout.setSpacing(8)

        # Edit Transaction button - first in the group for prominence
        self.edit_btn = QPushButton('Edit Transaction')
        self.edit_btn.setIcon(QIcon.fromTheme("document-properties", QIcon(":/icons/edit.png")))
        self.edit_btn.setToolTip("Edit the selected transaction in a detailed form")
        self.edit_btn.clicked.connect(self._edit_selected_transaction)
        self.edit_btn.setEnabled(False)  # Disabled until a row is selected
        data_btn_layout.addWidget(self.edit_btn)

        # Delete Transaction button
        self.del_btn = QPushButton('Delete')
        self.del_btn.setIcon(QIcon.fromTheme("edit-delete", QIcon(":/icons/delete.png")))
        self.del_btn.setToolTip("Delete selected row(s) from the database (Del)")
        self.del_btn.clicked.connect(self._delete_rows)
        data_btn_layout.addWidget(self.del_btn)

        # Clear New Rows button
        self.clear_btn = QPushButton('Clear New Rows')
        self.clear_btn.setIcon(QIcon.fromTheme("edit-clear", QIcon(":/icons/clear.png")))
        self.clear_btn.setToolTip("Clear newly added rows that haven't been saved yet.")
        self.clear_btn.clicked.connect(self._clear_pending)
        data_btn_layout.addWidget(self.clear_btn)

        # Create a group for save/discard buttons (right side)
        save_btn_layout = QHBoxLayout()
        save_btn_layout.setSpacing(8)

        # Discard Changes button
        self.discard_btn = QPushButton('Discard Changes')
        self.discard_btn.setIcon(QIcon.fromTheme("document-revert", QIcon(":/icons/revert.png")))
        self.discard_btn.setToolTip("Discard all unsaved additions and modifications")
        self.discard_btn.setEnabled(False)
        self.discard_btn.clicked.connect(self._discard_changes)
        save_btn_layout.addWidget(self.discard_btn)

        # Save Changes button
        self.save_btn = QPushButton('Save Changes')
        self.save_btn.setIcon(QIcon.fromTheme("document-save", QIcon(":/icons/save.png")))
        self.save_btn.setToolTip("Save all pending additions and modifications (Ctrl+S)")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._save_changes)
        save_shortcut = QShortcut(QKeySequence.StandardKey.Save, self)
        save_shortcut.activated.connect(self._save_changes)
        save_btn_layout.addWidget(self.save_btn)

        # Add both groups to the main button layout
        btn_layout.addLayout(data_btn_layout)
        btn_layout.addStretch(1)
        btn_layout.addLayout(save_btn_layout)
        root.addLayout(btn_layout)
        # --- End Action Buttons ---

        # --- Table Widget ---
        frame = QFrame()
        tblbox = QVBoxLayout(frame)
        tblbox.setContentsMargins(0,0,0,0)

        self.tbl = QTableWidget(0, len(self.COLS))
        self.tbl.setHorizontalHeaderLabels(DISPLAY_TITLES)

        # Set column widths based on configuration
        for col_idx, col_field in enumerate(self.COLS):
            col_config = get_column_config(col_field)
            if col_config and col_config.width_percent > 0:
                # Set fixed width based on percentage of table width
                # We'll update these widths when the table is resized
                self.tbl.horizontalHeader().setSectionResizeMode(col_idx, QHeaderView.ResizeMode.Interactive)
            else:
                # Use stretch mode for columns without specific width
                self.tbl.horizontalHeader().setSectionResizeMode(col_idx, QHeaderView.ResizeMode.Stretch)
        # Set edit triggers - include SingleClicked to make dropdowns open with a single click
        self.tbl.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked |
                               QAbstractItemView.EditTrigger.EditKeyPressed |
                               QAbstractItemView.EditTrigger.SelectedClicked)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.tbl.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        # Pass the main window instance (self) to the delegate
        self.tbl.setItemDelegate(SpreadsheetDelegate(self))
        self.tbl.cellChanged.connect(self._cell_edited)
        self.tbl.itemSelectionChanged.connect(self._capture_selection)
        self.tbl.installEventFilter(self)

        copy_shortcut = QShortcut(QKeySequence.StandardKey.Copy, self.tbl, self._copy_selection)
        paste_shortcut = QShortcut(QKeySequence.StandardKey.Paste, self.tbl, self._paste)
        delete_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Delete), self.tbl)
        delete_shortcut.activated.connect(self._delete_rows)

        undo_shortcut = QShortcut(QKeySequence.StandardKey.Undo, self, self.undo_stack.undo)
        redo_shortcut = QShortcut(QKeySequence.StandardKey.Redo, self, self.undo_stack.redo)

        tblbox.addWidget(self.tbl)
        root.addWidget(frame, stretch=1)
        # --- End Table Widget ---

        # --- FAB Button ---
        self.fab = QPushButton('+', self, toolTip='Add blank row')
        self.fab.setObjectName("fab")
        self.fab.raise_()
        self.fab.setFixedSize(56, 56)
        self.fab.clicked.connect(self._add_blank_row)
        QTimer.singleShot(0, self._place_fab)
        # --- End FAB Button ---

        # --- Message Label ---
        self._message = QLabel('')
        self._message.setStyleSheet('color:#ffb300; font-weight:bold; padding:4px;')
        self.centralWidget().layout().addWidget(self._message)
        # --- End Message Label ---

        # Connect resize event to update column widths
        self.tbl.horizontalHeader().sectionResized.connect(self._update_column_widths)

    def _open_default_values(self):
        """Open dialog to manage defaults, then reapply them to the form."""
        # Pass the dictionary of form widgets
        result = show_default_values_dialog(self, self.form_widgets)
        if result == QDialog.DialogCode.Accepted:
            # Re-apply defaults to the form immediately after saving them
            default_values.apply_to_form(self.form_widgets)
            self._show_message("Default values updated.", error=False)

    def _open_description_dialog(self):
        """Open dialog for editing multi-line description in the form."""
        current_text = self.desc_in.text()
        new_text = show_description_dialog(self, current_text)

        if new_text is not None:  # None means dialog was canceled
            self.desc_in.setText(new_text)
            self._show_message("Description updated.", error=False)

    def _open_description_dialog_for_cell(self, row, col, current_text):
        """Open dialog for editing multi-line description in a table cell."""
        new_text = show_description_dialog(self, current_text)

        if new_text is not None:  # None means dialog was canceled
            # Update the cell text
            item = self.tbl.item(row, col)
            if item:
                # Update the display text (no longer adding [...] indicator)
                item.setText(new_text if new_text else "")

                # Update the underlying data
                if row < len(self.transactions):
                    # Update existing transaction
                    self.transactions[row]['transaction_description'] = new_text
                    self.dirty.add(row)
                    if row not in self.dirty_fields:
                        self.dirty_fields[row] = set()
                    self.dirty_fields[row].add('transaction_description')
                elif row - len(self.transactions) < len(self.pending):
                    # Update pending transaction
                    pending_idx = row - len(self.transactions)
                    self.pending[pending_idx]['transaction_description'] = new_text

                self._update_button_states()
                self._show_message("Description updated.", error=False)

    def _edit_selected_transaction(self):
        """Open dialog for editing the selected transaction."""
        if not self.selected_rows or len(self.selected_rows) != 1:
            self._show_message("Please select a single transaction to edit.", error=True)
            return

        # Get the selected row
        row = list(self.selected_rows)[0]

        # Call the transaction details dialog
        self._open_transaction_details_dialog(row)

    def _open_transaction_details_dialog(self, row):
        """Open dialog for editing all transaction details."""
        # Get the transaction data
        transaction_data = None
        if row < len(self.transactions):
            transaction_data = self.transactions[row]
        elif row - len(self.transactions) < len(self.pending):
            pending_idx = row - len(self.transactions)
            transaction_data = self.pending[pending_idx]

        if not transaction_data:
            self._show_message("No transaction data found.", error=True)
            return

        # Make a deep copy of the original data for comparison
        import copy
        original_data = copy.deepcopy(transaction_data)

        # Show the transaction details dialog
        updated_data = show_transaction_details_dialog(
            self,
            transaction_data,
            self._accounts_data,
            self._categories_data,
            self._subcategories_data
        )

        if updated_data:  # None means dialog was canceled
            # Update the transaction data
            if row < len(self.transactions):
                # Debug print the original and updated data
                debug_print('TRANSACTION_EDIT', f"Original data: {original_data}")
                debug_print('TRANSACTION_EDIT', f"Updated data: {updated_data}")

                # Get the rowid for this transaction
                rowid = updated_data.get('rowid')

                if rowid is not None:
                    # DIRECT SAVE: Save changes immediately to the database
                    debug_print('TRANSACTION_EDIT', f"Directly saving changes for rowid {rowid} to database")

                    try:
                        # Prepare the update query
                        self.db.conn.execute('''
                            UPDATE transactions
                            SET transaction_name=?,
                                transaction_value=?,
                                account_id=?,
                                transaction_type=?,
                                transaction_category=?,
                                transaction_sub_category=?,
                                transaction_description=?,
                                transaction_date=?
                            WHERE rowid=?
                        ''', (
                            updated_data['transaction_name'],
                            float(updated_data['transaction_value']),
                            updated_data['account_id'],
                            updated_data['transaction_type'],
                            updated_data['transaction_category'],
                            updated_data['transaction_sub_category'],
                            updated_data['transaction_description'],
                            updated_data['transaction_date'],
                            rowid
                        ))

                        # Commit the changes
                        self.db.conn.commit()

                        # Update the transaction data in memory
                        self.transactions[row] = updated_data

                        # Update the original data cache with the new data
                        self._original_data_cache[rowid] = copy.deepcopy(updated_data)

                        # Refresh the display
                        self._refresh()
                        self._update_button_states()
                        self._show_message("Transaction updated and saved to database.", error=False)

                    except Exception as e:
                        # If there's an error, show it and don't update the UI
                        debug_print('TRANSACTION_EDIT', f"Error saving transaction: {e}")
                        self._show_message(f"Error saving transaction: {e}", error=True)

                        # Roll back any changes
                        if self.db.conn.in_transaction:
                            self.db.conn.rollback()

            elif row - len(self.transactions) < len(self.pending):
                # For pending transactions, just update the data in memory
                # These will be saved when the user clicks "Save Changes"
                pending_idx = row - len(self.transactions)
                self.pending[pending_idx] = updated_data

                # Refresh the display
                self._refresh()
                self._update_button_states()
                self._show_message("New transaction updated. Don't forget to save changes!", error=False)

    def _ensure_uncategorized_subcategories(self):
        """Ensure every category has an UNCATEGORIZED subcategory."""
        for category in self._categories_data:
            # Check if this category already has an UNCATEGORIZED subcategory
            has_uncategorized = False
            for subcat in self._subcategories_data:
                if subcat['category_id'] == category['id'] and subcat['name'] == 'UNCATEGORIZED':
                    has_uncategorized = True
                    break

            # If not, create one
            if not has_uncategorized:
                print(f"Creating UNCATEGORIZED subcategory for category {category['name']} (ID: {category['id']})")
                subcategory_id = self.db.ensure_subcategory('UNCATEGORIZED', category['id'])
                if subcategory_id:
                    # Add to our local data
                    self._subcategories_data.append({
                        'id': subcategory_id,
                        'name': 'UNCATEGORIZED',
                        'category_id': category['id']
                    })
                else:
                    print(f"Failed to create UNCATEGORIZED subcategory for category {category['name']}")

    def _load_dropdown_data(self):
        """Load data needed for dropdowns (accounts, categories, etc.)."""
        # Clear existing data
        self._accounts_data = []
        self._categories_data = []
        self._subcategories_data = []

        # CRITICAL FIX: Create a mapping of ID conflicts
        # This ensures that category ID 1 is always treated as UNCATEGORIZED, not Bank of America
        self._id_conflict_mapping = {
            'category': {
                1: 'UNCATEGORIZED'  # Force category ID 1 to always be UNCATEGORIZED
            },
            'sub_category': {}  # Will be populated as subcategories are loaded
        }

        # Create a set to track IDs that have been seen to detect conflicts
        self._seen_ids = {
            'category': set(),
            'sub_category': set()
        }

        try:
            cur = self.db.conn.cursor()
            cur.execute("SELECT id, account FROM bank_accounts ORDER BY account")
            self._accounts_data = [{'id': row[0], 'name': row[1]} for row in cur.fetchall()]

            # Load categories with ID conflict detection
            cur.execute("SELECT id, category, type FROM categories ORDER BY type, category")
            for row in cur.fetchall():
                category_id = row[0]
                category_name = row[1]
                category_type = row[2]

                # Check for ID conflicts
                if category_id in self._seen_ids['category']:
                    debug_print('CATEGORY', f"WARNING: Detected duplicate category ID: {category_id} for '{category_name}'")
                    # Add to conflict mapping if not already there
                    if category_id not in self._id_conflict_mapping['category']:
                        self._id_conflict_mapping['category'][category_id] = category_name
                        debug_print('CATEGORY', f"Added conflict mapping for category ID {category_id}: '{category_name}'")
                else:
                    # Mark this ID as seen
                    self._seen_ids['category'].add(category_id)

                # Special case for ID 1 - always force to UNCATEGORIZED
                if category_id == 1 and category_name != 'UNCATEGORIZED':
                    debug_print('CATEGORY', f"WARNING: Category ID 1 is '{category_name}', forcing to 'UNCATEGORIZED'")
                    # Keep the original name in the data structure but ensure it displays as UNCATEGORIZED

                self._categories_data.append({
                    'id': category_id,
                    'name': category_name,
                    'type': category_type
                })

            # Load subcategories with ID conflict detection
            cur.execute("SELECT id, sub_category, category_id FROM sub_categories ORDER BY category_id, sub_category")
            for row in cur.fetchall():
                subcategory_id = row[0]
                subcategory_name = row[1]
                category_id = row[2]

                # Check for ID conflicts
                if subcategory_id in self._seen_ids['sub_category']:
                    debug_print('SUBCATEGORY', f"WARNING: Detected duplicate subcategory ID: {subcategory_id} for '{subcategory_name}'")
                    # Add to conflict mapping if not already there
                    if subcategory_id not in self._id_conflict_mapping['sub_category']:
                        self._id_conflict_mapping['sub_category'][subcategory_id] = subcategory_name
                        debug_print('SUBCATEGORY', f"Added conflict mapping for subcategory ID {subcategory_id}: '{subcategory_name}'")
                else:
                    # Mark this ID as seen
                    self._seen_ids['sub_category'].add(subcategory_id)

                self._subcategories_data.append({
                    'id': subcategory_id,
                    'name': subcategory_name,
                    'category_id': category_id
                })

            # Ensure every category has an UNCATEGORIZED subcategory
            self._ensure_uncategorized_subcategories()
        except Exception as e:
            print(f"Error loading dropdown data: {e}")
            # Initialize with empty lists if there's an error
            self._accounts_data = []
            self._categories_data = []
            self._subcategories_data = []

        # Ensure the delegate's data sources are updated after any changes
        if hasattr(self.tbl, 'itemDelegate'):
            delegate = self.tbl.itemDelegate()
            if isinstance(delegate, SpreadsheetDelegate):
                delegate.setEditorDataSources(
                    self._accounts_data,
                    self._categories_data,
                    self._subcategories_data
                )

    def _populate_initial_form_dropdowns(self):
        """Populate form dropdowns initially after data is loaded."""
        # Populate accounts
        self.account_in.clear()
        debug_print('DROPDOWN', "--- Populating Accounts Dropdown ---")
        for i, acc in enumerate(self._accounts_data):
            # Debug Print for dropdown population
            debug_print('DROPDOWN', f"Adding item {i}: Name='{acc['name']}', ID={acc['id']} (Type: {type(acc['id'])})")
            self.account_in.addItem(acc['name'], userData=acc['id']) # Store ID in userData
            # Verification Print
            added_data = self.account_in.itemData(i)
            debug_print('DROPDOWN', f"  > Verified itemData({i}): {added_data} (Type: {type(added_data)})")
        debug_print('DROPDOWN', "--- Accounts Populated ---")

        if not self._accounts_data:
            self.account_in.setPlaceholderText('Select Account')

        self.type_in.setCurrentText('Expense')
        self._filter_categories_for_form()
        self._filter_subcategories_for_form()

        self.type_in.currentIndexChanged.connect(self._filter_categories_for_form)
        self.cat_in.currentIndexChanged.connect(self._filter_subcategories_for_form)

    def _filter_categories_for_form(self):
        """Filters the category dropdown based on the selected transaction type."""
        selected_type = self.type_in.currentText()
        current_category_id = self.cat_in.currentData() # Get previously stored ID if any

        debug_print('DROPDOWN', f"--- Filtering Categories for Type: {selected_type} ---")
        self.cat_in.blockSignals(True)
        self.cat_in.clear()
        found_current = False
        default_index = -1
        for i, cat in enumerate(self._categories_data):
            if cat['type'] == selected_type:
                # Check if this category ID has a conflict mapping
                display_name = cat['name']
                if cat['id'] in self._id_conflict_mapping.get('category', {}):
                    display_name = self._id_conflict_mapping['category'][cat['id']]
                    debug_print('DROPDOWN', f"  Using conflict mapping for category ID {cat['id']}: '{display_name}' instead of '{cat['name']}'")

                # Debug Print for category dropdown
                debug_print('DROPDOWN', f"  Adding Cat item {self.cat_in.count()}: Name='{display_name}', ID={cat['id']} (Type: {type(cat['id'])})")
                self.cat_in.addItem(display_name, userData=cat['id'])
                # Verification Print
                added_data = self.cat_in.itemData(self.cat_in.count() - 1)
                debug_print('DROPDOWN', f"    > Verified itemData({self.cat_in.count() - 1}): {added_data} (Type: {type(added_data)})")

                if cat['id'] == current_category_id:
                    found_current = True
                if cat['name'] == 'UNCATEGORIZED':
                    default_index = self.cat_in.count() - 1

        # Restore selection or set default
        restored_idx = -1
        if found_current and current_category_id is not None:
            restored_idx = self.cat_in.findData(current_category_id)
            self.cat_in.setCurrentIndex(restored_idx)
        elif default_index != -1:
            restored_idx = default_index
            self.cat_in.setCurrentIndex(default_index)
        elif self.cat_in.count() > 0:
            restored_idx = 0
            self.cat_in.setCurrentIndex(0)
        else:
            self.cat_in.setPlaceholderText(f"No {selected_type} Categories")
        debug_print('DROPDOWN', f"--- Categories Filtered. Selected index: {restored_idx} ---")

        self.cat_in.blockSignals(False)
        # Must trigger subcategory filter AFTER potentially changing category index
        self._filter_subcategories_for_form() # Trigger subcategory filtering

    def _filter_subcategories_for_form(self):
        """Filters the subcategory dropdown based on the selected category."""
        selected_category_id = self.cat_in.currentData() # Get ID from category dropdown
        current_subcategory_id = self.subcat_in.currentData() # Get previously stored ID if any

        debug_print('DROPDOWN', f"--- Filtering SubCats for Category ID: {selected_category_id} ---")
        self.subcat_in.blockSignals(True)
        self.subcat_in.clear()
        found_current = False
        default_index = -1

        if selected_category_id is not None:
            for i, subcat in enumerate(self._subcategories_data):
                if subcat['category_id'] == selected_category_id:
                    # Check if this subcategory ID has a conflict mapping
                    display_name = subcat['name']
                    if subcat['id'] in self._id_conflict_mapping.get('sub_category', {}):
                        display_name = self._id_conflict_mapping['sub_category'][subcat['id']]
                        debug_print('DROPDOWN', f"  Using conflict mapping for subcategory ID {subcat['id']}: '{display_name}' instead of '{subcat['name']}'")

                    # Debug Print for subcategory dropdown
                    debug_print('DROPDOWN', f"  Adding SubCat item {self.subcat_in.count()}: Name='{display_name}', ID={subcat['id']} (Type: {type(subcat['id'])})")
                    self.subcat_in.addItem(display_name, userData=subcat['id'])
                    # Verification Print
                    added_data = self.subcat_in.itemData(self.subcat_in.count() - 1)
                    debug_print('DROPDOWN', f"    > Verified itemData({self.subcat_in.count() - 1}): {added_data} (Type: {type(added_data)})")

                    if subcat['id'] == current_subcategory_id:
                        found_current = True
                    if subcat['name'] == 'UNCATEGORIZED':
                         default_index = self.subcat_in.count() - 1

        # Restore selection or set default
        restored_idx = -1
        if found_current and current_subcategory_id is not None:
            restored_idx = self.subcat_in.findData(current_subcategory_id)
            self.subcat_in.setCurrentIndex(restored_idx)
        elif default_index != -1:
            restored_idx = default_index
            self.subcat_in.setCurrentIndex(default_index)
        elif self.subcat_in.count() > 0:
            restored_idx = 0
            self.subcat_in.setCurrentIndex(0)
        else:
            self.subcat_in.setPlaceholderText("No Subcategories")
        debug_print('DROPDOWN', f"--- Subcategories Filtered. Selected index: {restored_idx} ---")

        self.subcat_in.blockSignals(False)

    def _get_category_id(self, category_name):
        for cat in self._categories_data:
            if cat['name'] == category_name:
                return cat['id']
        return None

    def _load_transactions(self, refresh_ui=True):
        """Load transactions from the database and update internal state."""
        cur=self.db.conn.cursor()
        try:
             # Fetch data using JOINs to get names instead of IDs
             cur.execute("""
                SELECT
                    t.id,                       -- 0: Transaction rowid (for internal tracking)
                    COALESCE(t.transaction_name, ''), -- 1: Transaction Name
                    t.transaction_value,        -- 2: Amount
                    ba.account,                 -- 3: Bank Account Name
                    t.transaction_type,         -- 4: Type ('Income'/'Expense') - now displayed in the table
                    c.category,                 -- 5: Category Name
                    sc.sub_category,            -- 6: Sub Category Name
                    COALESCE(t.transaction_description, ''), -- 7: Description
                    t.transaction_date,         -- 8: Date
                    t.account_id,               -- 9: Account ID
                    t.transaction_category,     -- 10: Category ID (Reverted name)
                    t.transaction_sub_category  -- 11: SubCategory ID (Reverted name)
                FROM transactions t
                LEFT JOIN bank_accounts ba ON t.account_id = ba.id
                LEFT JOIN categories c ON t.transaction_category = c.id
                LEFT JOIN sub_categories sc ON t.transaction_sub_category = sc.id
                ORDER BY t.transaction_date DESC, t.id DESC
            """)
        except sqlite3.Error as e:
             # Handle potential errors more gracefully
             print(f"Database error loading transactions: {e}")
             QMessageBox.critical(self, "Database Error", f"Could not load transactions: {e}")
             self.transactions = [] # Clear data on error
             # Fallback? Maybe try simpler query or exit?


        self.transactions = [] # Renamed from self.expenses
        self._original_data_cache = {} # Clear cache
        # Define the keys corresponding to the SELECT statement order
        # Reverted to original column names
        data_keys = ['rowid', 'transaction_name', 'transaction_value', 'account', 'transaction_type', 'category', 'sub_category', 'transaction_description', 'transaction_date', 'account_id', 'transaction_category', 'transaction_sub_category']

        fetched_data = cur.fetchall() if cur else []

        for r in fetched_data:
            rowid = r[0] # Use the first column (t.id) as the rowid
            # Map fetched data using data_keys
            data = dict(zip(data_keys, r))

            # Convert transaction_value to Decimal for proper formatting
            if 'transaction_value' in data and data['transaction_value'] is not None:
                data['transaction_value'] = Decimal(str(data['transaction_value']))

            # Ensure account_id is available for currency display
            if 'account' in data and isinstance(data['account'], str):
                # Make sure account_id is an integer
                if 'account_id' in data and data['account_id'] is not None:
                    try:
                        data['account_id'] = int(data['account_id'])
                        debug_print('ACCOUNT_CONVERSION', f"Converted account_id to int: {data['account_id']} for account {data['account']}")
                    except (ValueError, TypeError):
                        # If account_id is not a valid integer, try to find it from account name
                        data['account_id'] = None

                # If account_id is still None or not set, try to find it from account name
                if not data.get('account_id'):
                    for acc in self._accounts_data:
                        if acc['name'] == data['account']:
                            data['account_id'] = acc['id']
                            break

            # Ensure rowid is stored explicitly if needed elsewhere (though data['id'] covers it)
            # data['rowid'] = rowid # Reverted - 'rowid' is now the first key in data_keys
            self.transactions.append(data)
            self._original_data_cache[rowid] = data.copy()

        self.pending.clear()
        self.dirty.clear()
        self.dirty_fields.clear()
        self.errors.clear()
        if refresh_ui:
            self._refresh() # _refresh will need significant updates too

    def _add_form(self):
        """Handles adding a transaction from the form inputs."""
        # --- Get Raw Data from Form ---
        name = self.name_in.text().strip()
        value_str = self.value_in.text().strip().replace(self.locale.groupSeparator(),'').replace(self.locale.currencySymbol(),'').replace(self.locale.decimalPoint(),'.')
        type_str = self.type_in.currentText() # 'Income' or 'Expense'
        # Get selected index first to ensure an item is chosen
        account_idx = self.account_in.currentIndex()
        category_idx = self.cat_in.currentIndex()
        subcategory_idx = self.subcat_in.currentIndex()

        account_id = self.account_in.itemData(account_idx) if account_idx >= 0 else None
        category_id = self.cat_in.itemData(category_idx) if category_idx >= 0 else None
        subcategory_id = self.subcat_in.itemData(subcategory_idx) if subcategory_idx >= 0 else None

        # Get description from QLineEdit
        description = self.desc_in.text().strip()
        date_str = self.date_in.date().toString('yyyy-MM-dd')

        # --- Basic Validation --- (More robust validation in _validate_row for edits)
        if not value_str:
            self._show_message('Amount is required', error=True); return
        if not type_str:
            self._show_message('Transaction Type is required', error=True); return
        if account_id is None or account_idx < 0:
            self._show_message('A valid Bank Account must be selected', error=True); return
        if category_id is None or category_idx < 0:
            self._show_message('A valid Category must be selected', error=True); return

        # Ensure UNCATEGORIZED subcategory if none selected
        if subcategory_id is None or subcategory_idx < 0:
             if category_id is not None:
                 print(f"Attempting to ensure UNCATEGORIZED subcategory for category ID {category_id}")
                 subcategory_id = self.db.ensure_subcategory('UNCATEGORIZED', category_id)
                 if subcategory_id:
                     print(f"Using ensured UNCATEGORIZED subcategory ID: {subcategory_id}")
                     # Reload dropdown data & repopulate subcat dropdown
                     QTimer.singleShot(0, self._load_dropdown_data)
                     QTimer.singleShot(10, self._filter_subcategories_for_form) # Delay slightly
                 else:
                     self._show_message('Could not select/ensure UNCATEGORIZED subcategory.', error=True); return
             else:
                 self._show_message('Sub Category is required (and category is missing)', error=True); return

        try:
            # Convert value string to Decimal
            cleaned_value_str = value_str.replace(self.locale.groupSeparator(),'').replace(self.locale.currencySymbol(),'')
            value_decimal = Decimal(cleaned_value_str)
        except InvalidOperation:
            self._show_message('Invalid amount format', error=True); return

        # --- Add to Database via Database class method ---
        # Debug print is still here, should show valid IDs now
        print(f"--- DEBUG: Calling db.add_transaction ---")
        print(f"Account ID: {account_id} (Type: {type(account_id)})")
        print(f"Category ID: {category_id} (Type: {type(category_id)})")
        print(f"SubCategory ID: {subcategory_id} (Type: {type(subcategory_id)})")
        print(f"-----------------------------------------")

        # Corrected call with named arguments and Decimal value
        new_rowid = self.db.add_transaction(
            name=name,
            description=description,
            account_id=account_id,
            value=float(value_decimal), # Convert Decimal to float for DB (REAL type)
            type=type_str,
            category_id=category_id,
            sub_category_id=subcategory_id,
            date_str=date_str
        )

        if new_rowid is not None:
            # Instead of clearing, apply the defaults to reset the form
            default_values.apply_to_form(self.form_widgets)
            self._load_transactions();
            # _load_categories() is called via timer in _ensure_category if needed
            self._show_message('Transaction added!', error=False)

            self.last_saved_undo_index = self.undo_stack.index()
        else:
            self._show_message('Failed to add transaction.', error=True)

    def _cell_edited(self, row, col):
        # This signal is emitted *after* the data in the model has changed.
        # The Undo/Redo command system now handles updating the *underlying* data structures
        # (self.transactions, self.pending) and the dirty/error state based on the command's redo/undo.

        # Check if the account column was edited (col 2)
        if col == 2:  # Account column
            # Update the currency display for the transaction value
            self._update_currency_display_for_row(row)

        # Check if the category column was edited (col 4)
        if col == 4:  # Category column
            # Get the current row data
            row_data = None
            if row < len(self.transactions):
                row_data = self.transactions[row]
            elif row - len(self.transactions) < len(self.pending):
                row_data = self.pending[row - len(self.transactions)]

            # SPECIAL CASE: Handle the Bank of America vs UNCATEGORIZED conflict
            if row_data and row_data.get('category_id') == 1:
                # Force the display to show UNCATEGORIZED
                item = self.tbl.item(row, col)
                if item and item.text() != 'UNCATEGORIZED':
                    debug_print('CATEGORY', f"_cell_edited: Forcing display of UNCATEGORIZED for category_id=1 in row {row}")
                    item.setText('UNCATEGORIZED')
                    row_data['category'] = 'UNCATEGORIZED'

        # We need to ensure recoloring and button states are updated.
        self._recolor_row(row)
        self._update_button_states()

        # Print the current table state to the terminal
        self._debug_print_table()

        # Validation for pending/dirty rows now happens primarily in _save_changes

    def _update_currency_display_for_row(self, row):
        """Update the currency display for a specific row when the account changes."""
        # Get the account name from the table
        account_item = self.tbl.item(row, 2)  # Column 2 is Account
        if not account_item or not account_item.text():
            return

        account_text = account_item.text()

        # Check if the account text is an ID instead of a name
        try:
            # If the text is a number, it might be an ID
            account_id = int(account_text)
            # Find the account name for this ID
            account_name = None
            for acc in self._accounts_data:
                if acc['id'] == account_id:
                    account_name = acc['name']
                    # Update the account cell with the name instead of ID
                    account_item.setText(account_name)
                    break

            if not account_name:
                return
        except (ValueError, TypeError):
            # If it's not a number, assume it's already the account name
            account_name = account_text
            # Find the account_id for this account name
            account_id = None
            for acc in self._accounts_data:
                if acc['name'] == account_name:
                    account_id = acc['id']
                    break

        if not account_id:
            return

        # Get the currency for this account
        currency_info = self.db.get_account_currency(account_id)
        if not currency_info or 'currency_symbol' not in currency_info:
            return

        # Get the current value from the table
        value_item = self.tbl.item(row, 1)  # Column 1 is Value
        if not value_item:
            return

        # Get the current value as a Decimal
        try:
            # Try to extract just the numeric part from the display text
            display_text = value_item.text()
            # Remove any currency symbols or non-numeric characters except decimal point
            numeric_text = ''.join(c for c in display_text if c.isdigit() or c == '.' or c == '-')
            if not numeric_text:
                numeric_text = "0.00"
            value = Decimal(numeric_text)
        except (InvalidOperation, ValueError):
            value = Decimal("0.00")

        # Format with the currency symbol
        formatted_value = self.locale.toString(float(value), 'f', 2)
        display_text = f"{currency_info['currency_symbol']} {formatted_value}"

        # Update the table cell
        value_item.setText(display_text)

        # Also update the underlying data
        num_transactions = len(self.transactions)
        if row < num_transactions:
            self.transactions[row]['account'] = account_name
            self.transactions[row]['account_id'] = account_id
        else:
            pending_idx = row - num_transactions
            if pending_idx < len(self.pending):
                self.pending[pending_idx]['account'] = account_name
                self.pending[pending_idx]['account_id'] = account_id

    def _add_blank_row(self, focus_col=0):
        # --- Initialize Base Structure --- #
        # Start with a completely blank structure matching DB fields
        new_row_data = {
            'transaction_name': '',
            'transaction_value': Decimal('0.00'),
            'transaction_type': 'Expense', # A sensible baseline
            'account_id': None,
            'category_id': None,
            'sub_category_id': None,
            'transaction_description': '',
            'transaction_date': datetime.now().strftime('%Y-%m-%d'),
            # Name fields will be populated after applying defaults or from DB lookups
            'account': '',
            'category': '',
            'sub_category': ''
        }

        # --- Apply Defaults ---
        new_row_data = default_values.apply_to_new_row(new_row_data)

        # --- Populate Names based on IDs (after defaults applied) ---
        # Account Name
        if new_row_data.get('account_id') is not None:
            for acc in self._accounts_data:
                if acc['id'] == new_row_data['account_id']:
                    new_row_data['account'] = acc['name']
                    break
        elif self._accounts_data: # If no default ID, use first account as fallback?
             new_row_data['account_id'] = self._accounts_data[0]['id']
             new_row_data['account'] = self._accounts_data[0]['name']

        # Category Name (depends on Type)
        current_type = new_row_data.get('transaction_type', 'Expense')
        if new_row_data.get('category_id') is not None:
            # SPECIAL CASE: Handle the Bank of America vs UNCATEGORIZED conflict
            # If category_id is 1, ALWAYS set the category name to UNCATEGORIZED
            if new_row_data['category_id'] == 1:
                new_row_data['category'] = 'UNCATEGORIZED'
                debug_print('CATEGORY', f"_add_blank_row: Forcing category name to UNCATEGORIZED for category_id=1")
            else:
                for cat in self._categories_data:
                    if cat['id'] == new_row_data['category_id'] and cat['type'] == current_type:
                        new_row_data['category'] = cat['name']
                        break
            # If ID is invalid for type, try finding UNCATEGORIZED for the type
            if not new_row_data.get('category'):
                 for cat in self._categories_data:
                      if cat['name'] == 'UNCATEGORIZED' and cat['type'] == current_type:
                           new_row_data['category_id'] = cat['id']
                           new_row_data['category'] = cat['name']
                           break

        # Subcategory Name (depends on Category)
        current_cat_id = new_row_data.get('category_id')
        if current_cat_id is not None and new_row_data.get('sub_category_id') is not None:
            for subcat in self._subcategories_data:
                if subcat['id'] == new_row_data['sub_category_id'] and subcat['category_id'] == current_cat_id:
                    new_row_data['sub_category'] = subcat['name']
                    break
            # If ID is invalid for category, try finding UNCATEGORIZED for the category
            if not new_row_data['sub_category']:
                 for subcat in self._subcategories_data:
                      if subcat['name'] == 'UNCATEGORIZED' and subcat['category_id'] == current_cat_id:
                           new_row_data['sub_category_id'] = subcat['id']
                           new_row_data['sub_category'] = subcat['name']
                           break

        # --- Final Checks & Add to Pending ---
        # Ensure essential fields have fallbacks if defaults didn't provide them
        if new_row_data.get('account_id') is None:
             if self._accounts_data:
                 new_row_data['account_id'] = self._accounts_data[0]['id']
                 new_row_data['account'] = self._accounts_data[0]['name']
             else:
                 self._show_message("Cannot add row: No accounts available.", error=True); return

        if new_row_data.get('category_id') is None:
             # Find or create UNCATEGORIZED for the current type
             cat_type = new_row_data.get('transaction_type', 'Expense')
             uncat_id = self.db.ensure_category('UNCATEGORIZED', cat_type)
             if uncat_id:
                 new_row_data['category_id'] = uncat_id
                 new_row_data['category'] = 'UNCATEGORIZED'
                 QTimer.singleShot(0, self._load_dropdown_data) # Reload if created
             else:
                 self._show_message("Cannot add row: Failed to set default category.", error=True); return

        if new_row_data.get('sub_category_id') is None and new_row_data.get('category_id') is not None:
             # Find or create UNCATEGORIZED for the current category
             cat_id = new_row_data['category_id']
             subcat_id = self.db.ensure_subcategory('UNCATEGORIZED', cat_id)
             if subcat_id:
                 new_row_data['sub_category_id'] = subcat_id
                 new_row_data['sub_category'] = 'UNCATEGORIZED'
                 QTimer.singleShot(0, self._load_dropdown_data) # Reload if created
             else:
                 # Don't fail row add, validation will catch it if required
                 pass


        self.pending.append(new_row_data)
        self._refresh()

        new_row_index = len(self.transactions) + len(self.pending) - 1
        if new_row_index >= 0 and focus_col >= 0: # Only focus if focus_col is valid
            # Ensure the new row is visible and selected
            self.tbl.scrollToItem(self.tbl.item(new_row_index, 0), QAbstractItemView.ScrollHint.EnsureVisible)
            self.tbl.setCurrentCell(new_row_index, focus_col)

        # Print the table contents to the terminal
        self._debug_print_table()

    def _recolor_row(self, row):
        if row < 0 or row >= self.tbl.rowCount(): return # Added bounds check
        self.tbl.blockSignals(True) # Prevent cellChanged from firing during recoloring

        color_text = QColor('#f3f3f3')
        color_base_even = QColor('#23272e'); color_base_odd = QColor('#262b33')
        color_pending = QColor('#2a3949'); color_dirty = QColor('#4a4a3a')
        color_error = QColor('#a94442')
        color_row_error_soft = QColor('#3c2224') # Darker red background
        color_row_dirty_soft = QColor('#3a3a2c') # Darker yellow/brown background for dirty rows
        color_row_pending_soft = QColor('#263038') # Darker blue background for pending rows
        color_plus_row = QColor('#23272e')

        num_transactions = len(self.transactions)
        num_pending = len(self.pending)
        empty_row_index = num_transactions + num_pending

        row_has_error = row in self.errors and bool(self.errors[row])
        row_is_dirty_or_pending = False
        rowid = None
        base_bg = color_base_even if row % 2 == 0 else color_base_odd
        row_base_color = base_bg

        if row < num_transactions: # Existing transaction row
            rowid = self.transactions[row].get('rowid')
            if rowid in self.dirty: row_is_dirty_or_pending = True
            if row_has_error: row_base_color = color_row_error_soft
            elif row_is_dirty_or_pending: row_base_color = color_row_dirty_soft
            else: row_base_color = base_bg
        elif row < empty_row_index: # Pending row
            rowid = None # Pending rows don't have a rowid yet
            row_is_dirty_or_pending = True # Pending rows are always considered "changed"
            if row_has_error: row_base_color = color_row_error_soft
            else: row_base_color = color_row_pending_soft
        elif row == empty_row_index: # '+' row
             row_base_color = color_plus_row
        else:
            self.tbl.blockSignals(False); return # Should not happen if rowCount is correct

        field_errors = self.errors.get(row, {})
        dirty_fields_set = self.dirty_fields.get(rowid, set()) if rowid else set()

        for c, key in enumerate(self.COLS):
            item = self.tbl.item(row, c)
            if item:
                cell_bg = row_base_color
                # Apply error color only if the specific cell has an error
                if key in field_errors: cell_bg = color_error
                # Apply dirty color only if the specific cell is marked as dirty AND the row isn't errored
                elif rowid and key in dirty_fields_set and not row_has_error: cell_bg = color_dirty

                item.setBackground(cell_bg)
                # Ensure foreground color is consistent across cells in the row
                item.setForeground(color_text)
                # Item flags are set during _refresh

        self.tbl.blockSignals(False) # Re-enable signals

    def _ensure_category(self, category):
        if not category: return False
        category = category.strip() # Ensure no leading/trailing whitespace
        if not category: return False # Check again after stripping

        try:
            cur = self.db.conn.cursor()
            cur.execute('SELECT id FROM categories WHERE category=?', (category,))
            if not cur.fetchone():
                cur.execute('INSERT INTO categories (category) VALUES (?)', (category,))
                self.db.conn.commit()
                self._show_message(f"Category '{category}' added.", error=False)
                # Reload categories in the background to update the combobox options
                QTimer.singleShot(0, self._load_categories)
            return True
        except sqlite3.Error as e:
            # Avoid flooding messages for the same error
            if not str(self._message.text()).startswith(f"DB Error ensuring category"):
                 self._show_message(f"DB Error ensuring category '{category}': {e}", error=True)
            self.db.conn.rollback()
            return False

    def _get_category_id(self, category):
        if not category: return None
        try:
            cur = self.db.conn.cursor()
            cur.execute('SELECT id FROM categories WHERE category=?', (category,))
            result = cur.fetchone()
            return result[0] if result else None
        except sqlite3.Error as e:
             if not str(self._message.text()).startswith(f"DB Error getting category ID"):
                 self._show_message(f"DB Error getting category ID for '{category}': {e}", error=True)
             return None

    def _validate_row(self, row_data, row_index_visual):
        """Validate data for a single row (pending or existing). Returns cleaned data dict or None if invalid."""
        # print(f"--- DEBUG: Validating Row {row_index_visual} ---")
        # print(f"  Incoming data: {row_data}")
        errors = {}
        cleaned_data = {k: v for k, v in row_data.items()}

        # --- Get Type First (needed for category validation) ---
        trans_type = str(cleaned_data.get('transaction_type', '')).strip()
        if not trans_type or trans_type not in ('Income', 'Expense'):
            # Set a default or raise error immediately? Let's mark error for now.
            errors['transaction_type'] = 'Type must be Income or Expense.'
            # Set trans_type to None or a default to prevent further dependent errors? Defaulting for now.
            trans_type = 'Expense' # Default to allow category check to proceed somewhat
        else:
            cleaned_data['transaction_type'] = trans_type # Store cleaned type

        # --- Amount Validation ---
        amount_val = cleaned_data.get('transaction_value', '')
        amount_str = str(amount_val).strip()
        if not amount_str:
            errors['transaction_value'] = 'Amount is required.'
        else:
            try:
                # Convert to Decimal, cleaning up locale chars first
                cleaned_amount_str = amount_str.replace(self.locale.groupSeparator(),'').replace(self.locale.currencySymbol(),'')
                amount_decimal = Decimal(cleaned_amount_str)
                # Optional: Round to 2 decimal places upon validation if desired
                # amount_decimal = amount_decimal.quantize(Decimal("0.01"))
                cleaned_data['transaction_value'] = amount_decimal # Store Decimal
            except InvalidOperation:
                 errors['transaction_value'] = 'Invalid amount format.'

        # --- Account Validation ---
        account_id = cleaned_data.get('account_id')
        account_name = str(cleaned_data.get('account','')).strip()
        valid_account_id = None
        if account_id is not None:
            if any(acc['id'] == account_id for acc in self._accounts_data):
                valid_account_id = account_id
                # Update name if needed
                for acc in self._accounts_data:
                    if acc['id'] == account_id:
                        cleaned_data['account'] = acc['name']
                        break
            else:
                errors['account'] = f'Invalid Account ID: {account_id}'
        elif account_name:
            found = False
            for acc in self._accounts_data:
                if acc['name'] == account_name:
                    valid_account_id = acc['id']
                    cleaned_data['account_id'] = valid_account_id
                    found = True
                    break
            if not found:
                errors['account'] = f'Account Name not found: {account_name}'
        else:
            errors['account'] = 'Account is required.'
        # Always set transaction_account if valid
        if valid_account_id is not None:
            cleaned_data['transaction_account'] = valid_account_id
        # print(f"    > Account Result: ID={valid_account_id}, Error: {errors.get('account')}")

        # --- Category Validation ---
        category_id = cleaned_data.get('category_id')
        category_name = str(cleaned_data.get('category','')).strip()
        valid_category_id = None # Reset for category check
        if 'transaction_type' not in errors:
            if category_id is not None:
                category_valid_for_type = False
                for cat in self._categories_data:
                    if cat['id'] == category_id and cat['type'] == trans_type:
                        valid_category_id = category_id
                        category_valid_for_type = True
                        if category_name and cat['name'] != category_name:
                            print(f"    Warning: Category name '{category_name}' mismatch for ID {category_id}. Updating name.")
                            cleaned_data['category'] = cat['name']
                        break
                if not category_valid_for_type:
                    errors['category'] = f'Invalid Category ID {category_id} for type {trans_type}.'
            elif category_name:
                found = False
                for cat in self._categories_data:
                    if cat['name'] == category_name and cat['type'] == trans_type:
                        valid_category_id = cat['id']
                        cleaned_data['category_id'] = valid_category_id
                        found = True
                        break
                if not found:
                    errors['category'] = f'Category Name \'{category_name}\' not found for type {trans_type}.'
            else:
                errors['category'] = 'Category is required.'
            # Always set transaction_category if valid
            if valid_category_id is not None:
                cleaned_data['transaction_category'] = valid_category_id
        else:
            errors['category'] = 'Category cannot be validated (Type error).'
        # print(f"    > Category Result: ID={valid_category_id}, Error: {errors.get('category')}")

        # --- Subcategory Validation (Refined Logic) ---
        subcategory_id = cleaned_data.get('sub_category_id')
        subcategory_name = str(cleaned_data.get('sub_category','')).strip()
        valid_subcategory_id = None # Reset for subcategory check
        parent_category_error = 'category' in errors

        if not parent_category_error and valid_category_id is not None:
            if subcategory_id is not None:
                # If ID provided, validate it against parent category ID
                subcategory_valid = False
                for subcat in self._subcategories_data:
                    if subcat['id'] == subcategory_id and subcat['category_id'] == valid_category_id:
                        valid_subcategory_id = subcategory_id
                        subcategory_valid = True
                        if subcategory_name and subcat['name'] != subcategory_name:
                             print(f"    Warning: SubCat name '{subcategory_name}' mismatch for ID {subcategory_id}. Updating name.")
                             cleaned_data['sub_category'] = subcat['name']
                        break
                if not subcategory_valid:
                    errors['sub_category'] = f'Invalid SubCat ID {subcategory_id} for Category ID {valid_category_id}.'
            elif subcategory_name and subcategory_name != "No Subcategories (Select Cat)": # ADDED Check for placeholder
                # If name provided (and not placeholder), find ID based on name and valid parent category ID
                found = False
                for subcat in self._subcategories_data:
                     if subcat['name'] == subcategory_name and subcat['category_id'] == valid_category_id:
                         valid_subcategory_id = subcat['id']
                         cleaned_data['sub_category_id'] = valid_subcategory_id
                         found = True; break
                # Special case: if name provided is exactly 'UNCATEGORIZED', ensure it exists
                if not found and subcategory_name == 'UNCATEGORIZED':
                     ensured_id = self.db.ensure_subcategory('UNCATEGORIZED', valid_category_id)
                     if ensured_id:
                          valid_subcategory_id = ensured_id
                          cleaned_data['sub_category_id'] = valid_subcategory_id
                          found = True
                          QTimer.singleShot(0, self._load_dropdown_data)
                     else:
                          errors['sub_category'] = 'Could not find/create UNCATEGORIZED SubCat.'
                elif not found:
                     # Name provided doesn't match any existing subcategory for this parent category
                     errors['sub_category'] = f'SubCat Name \'{subcategory_name}\' not found for Category ID {valid_category_id}.'
            else: # subcategory_id is None AND (subcategory_name is empty OR is placeholder)
                # Check if the parent category allows defaulting (i.e., is itself UNCATEGORIZED)
                parent_cat_is_uncategorized = False
                for cat in self._categories_data:
                    if cat['id'] == valid_category_id and cat['name'] == 'UNCATEGORIZED':
                        parent_cat_is_uncategorized = True; break

                if parent_cat_is_uncategorized:
                     # If parent is UNCATEGORIZED, default subcategory to UNCATEGORIZED
                     ensured_id = self.db.ensure_subcategory('UNCATEGORIZED', valid_category_id)
                     if ensured_id:
                         valid_subcategory_id = ensured_id
                         cleaned_data['sub_category_id'] = valid_subcategory_id
                         cleaned_data['sub_category'] = 'UNCATEGORIZED' # Set name too
                         QTimer.singleShot(0, self._load_dropdown_data)
                     else:
                         errors['sub_category'] = 'Could not default to UNCATEGORIZED subcategory.'
                else:
                    # Check if this category has any subcategories at all
                    has_subcategories = False
                    for subcat in self._subcategories_data:
                        if subcat['category_id'] == valid_category_id:
                            has_subcategories = True
                            break

                    if has_subcategories:
                        # Only require subcategory if the category has subcategories
                        errors['sub_category'] = 'Subcategory is required for this category.'
                    else:
                        # If category has no subcategories, create an UNCATEGORIZED one
                        print(f"Category {valid_category_id} has no subcategories, creating UNCATEGORIZED")
                        ensured_id = self.db.ensure_subcategory('UNCATEGORIZED', valid_category_id)
                        if ensured_id:
                            valid_subcategory_id = ensured_id
                            cleaned_data['sub_category_id'] = valid_subcategory_id
                            cleaned_data['sub_category'] = 'UNCATEGORIZED'
                            QTimer.singleShot(0, self._load_dropdown_data)
                        else:
                            errors['sub_category'] = 'Could not create UNCATEGORIZED subcategory.'

        elif not parent_category_error and valid_category_id is None:
             # This case should not happen if category validation logic is correct
             errors['sub_category'] = 'Subcategory cannot be validated (Category missing/invalid).'
        elif parent_category_error:
             # Parent category had an error, so subcategory is also invalid
             errors['sub_category'] = 'Subcategory invalid (due to Category error).'
        # print(f"    > SubCategory Result: ID={valid_subcategory_id}, Error: {errors.get('sub_category')}")

        # --- Date Validation ---
        date_str = str(cleaned_data.get('transaction_date', '')).strip()
        if not date_str:
            errors['transaction_date'] = 'Date is required.'
        else:
            # Check if the date is in the correct ISO format (YYYY-MM-DD)
            try:
                # First, try to parse as ISO format
                if len(date_str) == 10 and date_str.count('-') == 2:
                    year, month, day = date_str.split('-')
                    if len(year) == 4 and len(month) == 2 and len(day) == 2:
                        # Validate as a proper date
                        datetime.strptime(date_str, '%Y-%m-%d')
                        # If we get here, the date is valid ISO format
                        cleaned_data['transaction_date'] = date_str
                    else:
                        raise ValueError("Date parts have incorrect lengths")
                else:
                    # Try to parse other common formats
                    date_formats = [
                        ('%d %b %Y', r'\d{1,2} [A-Za-z]{3} \d{4}'),  # "20 May 2025"
                        ('%m/%d/%Y', r'\d{1,2}/\d{1,2}/\d{4}'),      # "05/20/2025"
                        ('%d/%m/%Y', r'\d{1,2}/\d{1,2}/\d{4}')       # "20/05/2025"
                    ]

                    parsed_date = None
                    for fmt, pattern in date_formats:
                        if re.match(pattern, date_str):
                            try:
                                parsed_date = datetime.strptime(date_str, fmt)
                                break
                            except ValueError:
                                continue

                    if parsed_date:
                        # Convert to ISO format
                        cleaned_data['transaction_date'] = parsed_date.strftime('%Y-%m-%d')
                    else:
                        # If all formats fail, use current date
                        errors['transaction_date'] = f'Invalid date format: {date_str}. Using current date.'
                        cleaned_data['transaction_date'] = datetime.now().strftime('%Y-%m-%d')
            except ValueError as e:
                # If date parsing fails, use current date
                errors['transaction_date'] = f'Invalid date: {e}. Using current date.'
                cleaned_data['transaction_date'] = datetime.now().strftime('%Y-%m-%d')

        # --- Name and Description Cleaning ---
        # Clean transaction name and description (just strip whitespace)
        name = str(cleaned_data.get('transaction_name', '')).strip()
        description = str(cleaned_data.get('transaction_description', '')).strip()
        cleaned_data['transaction_name'] = name
        cleaned_data['transaction_description'] = description

        # --- Set transaction_sub_category if valid_subcategory_id is set ---
        if valid_subcategory_id is not None:
            cleaned_data['transaction_sub_category'] = valid_subcategory_id

        # --- Update error state --- #
        if errors:
            self.errors[row_index_visual] = errors
            # print(f"  Validation Errors for row {row_index_visual}: {errors}")
            return None
        else:
            if row_index_visual in self.errors:
                del self.errors[row_index_visual]
            # print(f"  Validation Success for row {row_index_visual}. Cleaned data: {cleaned_data}")
            return cleaned_data


    def _save_changes(self):
        rows_with_errors_indices = set()
        error_details_for_msgbox = []
        db_error_occurred = False
        commit_successful = False

        inserts_to_execute = []
        pending_rows_that_passed_validation_indices = set()
        pending_rows_that_failed_validation_indices = [] # Store original indices
        failed_pending_errors = {} # Store errors for failed pending rows (key: original pending index)

        updates_to_execute = []
        dirty_rowids_that_passed_validation = set()
        dirty_rowids_that_failed_validation = set()
        dirty_fields_that_failed_validation = {}
        failed_existing_errors = {} # Store errors for failed existing rows (key: rowid)

        db_error_state_to_restore = {} # Initialize

        try:
            # --- Phase 1: Validate all pending and dirty rows ---
            original_num_transactions_before_save = len(self.transactions)
            original_pending_copy = self.pending[:] # Copy for safe iteration

            # Validate Pending Rows
            for i, p_row in enumerate(original_pending_copy):
                row_idx_visual = original_num_transactions_before_save + i
                valid_data = self._validate_row(p_row, row_idx_visual)
                if valid_data:
                    # Ensure transaction_category is present after validation
                    if 'transaction_category' not in valid_data:
                         self.errors[row_idx_visual] = self.errors.get(row_idx_visual, {})
                         self.errors[row_idx_visual]['transaction_category'] = "Category ID missing after validation."
                         valid_data = None # Mark as invalid

                if valid_data:
                    # Make sure all required fields are present
                    if ('transaction_type' not in valid_data or
                        'account_id' not in valid_data or
                        'transaction_sub_category' not in valid_data):
                        debug_print('FOREIGN_KEYS', f"Missing required fields for row {row_idx_visual}:")
                        debug_print('FOREIGN_KEYS', f"  transaction_type: {valid_data.get('transaction_type')}")
                        debug_print('FOREIGN_KEYS', f"  account_id: {valid_data.get('account_id')}")
                        debug_print('FOREIGN_KEYS', f"  transaction_sub_category: {valid_data.get('transaction_sub_category')}")
                        self.errors[row_idx_visual] = self.errors.get(row_idx_visual, {})
                        if 'transaction_type' not in valid_data:
                            self.errors[row_idx_visual]['transaction_type'] = "Transaction type is missing"
                        if 'account_id' not in valid_data:
                            self.errors[row_idx_visual]['account'] = "Account ID is missing"
                        if 'transaction_sub_category' not in valid_data:
                            self.errors[row_idx_visual]['sub_category'] = "Sub-category ID is missing"
                        valid_data = None
                    else:
                        inserts_to_execute.append((
                            valid_data['transaction_name'],
                            float(valid_data['transaction_value']),
                            valid_data['account_id'],
                            valid_data['transaction_type'],
                            valid_data['transaction_category'],
                            valid_data['transaction_sub_category'],
                            valid_data['transaction_description'],
                            valid_data['transaction_date']
                        ))
                        pending_rows_that_passed_validation_indices.add(i)
                else:
                    pending_rows_that_failed_validation_indices.append(i)
                    failed_pending_errors[i] = self.errors.get(row_idx_visual, {})
                    rows_with_errors_indices.add(row_idx_visual)
                    err_msg = "; ".join(f"{k.capitalize()}: {v}" for k, v in self.errors.get(row_idx_visual, {}).items())
                    error_details_for_msgbox.append(f"New Row {i+1}: {err_msg}")

            # Validate Dirty Existing Rows
            original_transactions_copy = self.transactions[:] # Copy for safe iteration
            for i, e_row in enumerate(original_transactions_copy):
                rowid = e_row.get('rowid')
                if rowid in self.dirty:
                    row_idx_visual = i
                    valid_data = self._validate_row(e_row, row_idx_visual)
                    if valid_data:
                        # Ensure transaction_category is present after validation
                        if 'transaction_category' not in valid_data:
                            self.errors[row_idx_visual] = self.errors.get(row_idx_visual, {})
                            self.errors[row_idx_visual]['transaction_category'] = "Category ID missing after validation."
                            valid_data = None # Mark as invalid

                    if valid_data:
                        updates_to_execute.append((
                            valid_data['transaction_name'],
                            float(valid_data['transaction_value']),
                            valid_data['account_id'],  # Include account_id for updates
                            valid_data['transaction_type'],  # Include transaction_type for updates
                            valid_data['transaction_category'],
                            valid_data['transaction_sub_category'],  # Include sub_category for updates
                            valid_data['transaction_description'],
                            valid_data['transaction_date'],
                            rowid # rowid for WHERE clause
                        ))
                        dirty_rowids_that_passed_validation.add(rowid)
                    else:
                        dirty_rowids_that_failed_validation.add(rowid)
                        dirty_fields_that_failed_validation[rowid] = self.dirty_fields.get(rowid, set())
                        failed_existing_errors[rowid] = self.errors.get(row_idx_visual, {})
                        rows_with_errors_indices.add(row_idx_visual)
                        err_msg = "; ".join(f"{k.capitalize()}: {v}" for k, v in self.errors.get(row_idx_visual, {}).items())
                        error_details_for_msgbox.append(f"Existing Row {i+1} (ID {rowid}): {err_msg}")

            # Clear self.errors *after* validation phase, before commit attempt
            # Store the validation errors before clearing self.errors
            validation_errors = self.errors.copy()
            self.errors.clear() # Clear global errors before potential commit

            # --- Phase 2: Attempt to commit valid changes ---
            if inserts_to_execute or updates_to_execute:
                 self.db.conn.execute('BEGIN')
                 if inserts_to_execute:
                     self.db.conn.executemany('''
                         INSERT INTO transactions(
                             transaction_name, transaction_value, account_id,
                             transaction_type, transaction_category,
                             transaction_sub_category, transaction_description, transaction_date
                         )
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                     ''', inserts_to_execute) # Updated to include all required columns

                 if updates_to_execute:
                     self.db.conn.executemany('''
                         UPDATE transactions
                            SET transaction_name=?, transaction_value=?, account_id=?, transaction_type=?,
                                transaction_category=?, transaction_sub_category=?, transaction_description=?, transaction_date=?
                          WHERE rowid=?
                     ''', updates_to_execute) # Updated to include all columns

                 self.db.conn.commit()
                 commit_successful = True
                 self.last_saved_undo_index = self.undo_stack.index()
                 self.undo_stack.setClean() # Mark stack as clean after successful save

        except sqlite3.Error as e:
            db_error_occurred = True
            commit_successful = False
            if self.db.conn.in_transaction:
                 self.db.conn.rollback()

            # Combine validation errors with the DB error message
            db_error_state_to_restore = validation_errors.copy()
            db_error_msg = f" DB Error: {e}"

            # Add DB error message to all rows involved in the failed transaction
            involved_visual_indices = set(rows_with_errors_indices) # Start with validation errors
            # Add pending rows that passed validation but failed commit
            for i in pending_rows_that_passed_validation_indices:
                involved_visual_indices.add(original_num_transactions_before_save + i)
            # Add existing rows that passed validation but failed commit
            for rowid in dirty_rowids_that_passed_validation:
                 for idx, exp in enumerate(original_transactions_copy): # Use copy
                     if exp.get('rowid') == rowid:
                         involved_visual_indices.add(idx)
                         break

            for idx in involved_visual_indices:
                if idx not in db_error_state_to_restore: db_error_state_to_restore[idx] = {}
                db_error_state_to_restore[idx]['database'] = db_error_state_to_restore[idx].get('database','') + db_error_msg


            self._show_message(f'Database error during save: {e}. No changes saved.', error=True)
            QMessageBox.critical(self, 'Database Save Error', f"A database error occurred: {e}\n\nNo changes were saved in this attempt. Rows involved may be marked with errors.")
            rows_with_errors_indices.update(involved_visual_indices) # Ensure all affected rows are marked


        finally:
             db_error_actually_occurred = db_error_occurred

             # --- Decide action based on outcome ---
             partial_save_occurred = commit_successful and bool(rows_with_errors_indices)
             failed_save_no_commit = not commit_successful and bool(rows_with_errors_indices) and not db_error_actually_occurred
             full_success = commit_successful and not bool(rows_with_errors_indices)

             if db_error_actually_occurred:
                 # --- DB Error during commit phase ---
                 self.errors = db_error_state_to_restore # Restore combined errors
                 # Keep the state that led to the error (pending/dirty) for user to fix
                 # Don't reload, refresh UI with current data + errors
                 self._refresh()

             elif partial_save_occurred:
                 # --- Partial Save: Some rows saved, some failed validation ---
                 # 1. Store failed state (use original_pending_copy)
                 failed_pending_rows = [original_pending_copy[i] for i in pending_rows_that_failed_validation_indices]
                 failed_dirty_rowids = dirty_rowids_that_failed_validation
                 failed_dirty_fields = dirty_fields_that_failed_validation

                 # 2. Reload from DB (includes successfully saved rows) without refreshing UI yet
                 self._load_transactions(refresh_ui=False)

                 # 3. Re-apply the failed state to the reloaded data
                 self.pending = failed_pending_rows # Add failed pending rows back
                 self.dirty = failed_dirty_rowids   # Mark failed existing rows as dirty again
                 self.dirty_fields = failed_dirty_fields

                 # 4. Restore errors for the rows that failed validation
                 self.errors.clear() # Start fresh error dict
                 current_num_transactions = len(self.transactions) # After reload
                 # Restore errors for failed EXISTING rows (that are still dirty)
                 for new_idx, transaction_data in enumerate(self.transactions):
                     rowid = transaction_data.get('rowid')
                     if rowid in failed_existing_errors: # Check original failure list
                         self.errors[new_idx] = failed_existing_errors[rowid]

                 # Restore errors for failed PENDING rows (now at the end)
                 for i, _ in enumerate(self.pending): # Iterate over the kept pending rows
                     original_pending_index = pending_rows_that_failed_validation_indices[i]
                     error_detail = failed_pending_errors.get(original_pending_index)
                     if error_detail:
                         new_visual_index = current_num_transactions + i
                         self.errors[new_visual_index] = error_detail

                 # 5. Refresh the UI *once* with the combined state
                 self._refresh()

                 # 6. Show message
                 self._show_message(f'{len(rows_with_errors_indices)} row(s) had validation errors and were not saved.', error=True)
                 if error_details_for_msgbox:
                      detailed_error_str = "Could not save all rows due to validation errors:\n\n" + "\n".join(error_details_for_msgbox)
                      detailed_error_str = detailed_error_str.replace('\\n', '\n')
                      QMessageBox.warning(self, 'Partial Save - Validation Errors', detailed_error_str)

             elif failed_save_no_commit:
                 # --- Failed Save: Validation errors, NO commit happened ---
                 # Keep only failed pending rows (use original_pending_copy)
                 self.pending = [original_pending_copy[i] for i in pending_rows_that_failed_validation_indices]
                 # Keep only failed dirty rows/fields
                 self.dirty = dirty_rowids_that_failed_validation
                 self.dirty_fields = dirty_fields_that_failed_validation

                 # Restore errors from the validation phase
                 self.errors = validation_errors.copy()

                 # Refresh UI directly (no reload needed as DB wasn't touched)
                 self._refresh()

                 # Show message
                 self._show_message(f'{len(rows_with_errors_indices)} row(s) had validation errors and were not saved.', error=True)
                 if error_details_for_msgbox:
                      detailed_error_str = "Could not save due to validation errors:\n\n" + "\n".join(error_details_for_msgbox)
                      detailed_error_str = detailed_error_str.replace('\\n', '\n')
                      QMessageBox.warning(self, 'Save Failed - Validation Errors', detailed_error_str)

             elif full_success:
                 # --- Full Success ---
                 # Clear all transient state BEFORE reloading
                 self.pending.clear()
                 self.dirty.clear()
                 self.dirty_fields.clear()
                 self.errors.clear() # Should be empty already
                 self._show_message('All changes saved!', error=False)
                 # Reload from DB to get fresh data (including new rowids)
                 self._load_transactions() # Calls _refresh()

             else: # No changes to save, or commit not attempted (no inserts/updates)
                 # Clear any residual validation errors if nothing was attempted
                 self.errors.clear()
                 self._refresh() # Refresh to clear any potential error highlighting
                 pass


    def _discard_changes(self):
        if not self.pending and not self.dirty:
            self._show_message("No changes to discard.", error=False); return

        reply = QMessageBox.question(self, 'Discard Changes',
                                     'Are you sure you want to discard all unsaved changes?\n(This cannot be undone)',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.pending.clear(); self.dirty.clear(); self.dirty_fields.clear(); self.errors.clear()
            # Reload from the database to revert any changes in self.transactions
            self._load_transactions()
            # No need to reload categories on discard
            self._show_message("Changes discarded.", error=False)
            # Clear the undo stack completely after discarding changes
            self.undo_stack.clear()
            self.last_saved_undo_index = 0 # Reset saved index

    def _capture_selection(self):
        # Store just the row indices of selected items
        selected_rows_indices = {idx.row() for idx in self.tbl.selectedIndexes()}
        self.selected_rows = selected_rows_indices
        self._update_button_states() # Update delete button state based on selection

    def _delete_rows(self):
        if not self.selected_rows:
            self._show_message("No rows selected to delete.", error=True)
            return

        num_transactions = len(self.transactions)
        num_pending = len(self.pending)
        empty_row_idx = num_transactions + num_pending

        # Filter out the empty '+' row index if it's selected
        rows_to_delete_indices = {r for r in self.selected_rows if r < empty_row_idx}

        if not rows_to_delete_indices:
             self._show_message("No valid data rows selected for deletion.", error=False)
             return

        num_selected_valid = len(rows_to_delete_indices)
        confirm_msg = f'Permanently delete {num_selected_valid} selected row(s)?\n(Includes pending and saved rows. This cannot be undone easily.)'

        if QMessageBox.question(self, 'Delete Rows', confirm_msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return

        # Separate indices into pending and saved
        # Process pending indices carefully due to list shifting
        pending_indices_to_delete_visual = sorted([r for r in rows_to_delete_indices if r >= num_transactions], reverse=True)
        saved_rowids_to_delete = [self.transactions[r]['rowid'] for r in rows_to_delete_indices
                                 if r < num_transactions and 'rowid' in self.transactions[r]]

        pending_rows_deleted_count = 0
        # Delete pending rows from the list (reversing ensures indices remain valid)
        for visual_row_index in pending_indices_to_delete_visual:
            pending_index = visual_row_index - num_transactions
            if 0 <= pending_index < len(self.pending):
                # Remove associated errors as well
                if visual_row_index in self.errors:
                     del self.errors[visual_row_index]
                del self.pending[pending_index]
                pending_rows_deleted_count += 1

        saved_rows_deleted_count = 0
        # Delete saved rows from the database
        if saved_rowids_to_delete:
            try:
                self.db.conn.execute('BEGIN')
                placeholders = ','.join('?' * len(saved_rowids_to_delete))
                cursor = self.db.conn.execute(f'DELETE FROM transactions WHERE rowid IN ({placeholders})', saved_rowids_to_delete)
                saved_rows_deleted_count = cursor.rowcount
                self.db.conn.commit()

                # Update dirty/cache tracking immediately
                self.dirty.difference_update(saved_rowids_to_delete)
                for rowid in saved_rowids_to_delete:
                    self.dirty_fields.pop(rowid, None)
                    self._original_data_cache.pop(rowid, None)
                    # Remove errors associated with deleted saved rows
                    for visual_idx, exp_data in enumerate(self.transactions):
                        if exp_data.get('rowid') == rowid:
                            if visual_idx in self.errors:
                                del self.errors[visual_idx]
                            break # Found the row

                # Reload transactions and refresh the table completely
                self._load_transactions() # This implicitly handles refresh
                self._show_message(f"Deleted {pending_rows_deleted_count} pending and {saved_rows_deleted_count} saved row(s).", error=False)
                # Clear undo stack after destructive action not managed by commands
                self.undo_stack.clear()
                self.last_saved_undo_index = 0
                return # Exit as _load_transactions already refreshed

            except sqlite3.Error as e:
                self.db.conn.rollback()
                self._show_message(f"DB Error deleting saved rows: {e}", error=True)
                # Don't reload if DB delete failed, just refresh current state
                self._refresh()

        # If only pending rows were deleted (or DB delete failed), refresh
        elif pending_rows_deleted_count > 0:
             self._refresh()
             self._show_message(f"Deleted {pending_rows_deleted_count} pending row(s).", error=False)


        self.selected_rows.clear() # Clear selection after deletion attempt
        self._update_button_states() # Update button states


    def _clear_pending(self):
        if not self.pending:
            self._show_message("No new (pending) rows to clear", error=False)
            return

        reply = QMessageBox.question(self, 'Clear New Rows',
                                     'Are you sure you want to clear all newly added (unsaved) rows?',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Clear errors associated with pending rows
        num_transactions = len(self.transactions)
        pending_visual_indices = range(num_transactions, num_transactions + len(self.pending))
        for idx in pending_visual_indices:
             if idx in self.errors:
                 del self.errors[idx]

        self.pending.clear()
        self._refresh()
        self._show_message("Cleared new (pending) rows", error=False)
        # Clearing pending rows might affect undo stack if they were result of commands
        # Consider clearing undo stack or managing it more carefully if needed


    def resizeEvent(self,e):
        super().resizeEvent(e)
        QTimer.singleShot(0, self._place_fab)
        QTimer.singleShot(0, self._update_column_widths)

    def _update_column_widths(self, logical_index=None, old_size=None, new_size=None):
        """Update column widths based on configuration percentages."""
        # This method is called when the table is resized or when a column is manually resized

        # If this was triggered by a manual column resize, we don't want to override it
        if logical_index is not None and old_size is not None and new_size is not None:
            return

        # Get the total width of the table
        total_width = self.tbl.viewport().width()
        if total_width <= 0:
            return  # Table not visible yet

        # Calculate and set widths based on configuration
        for col_idx, col_field in enumerate(self.COLS):
            col_config = get_column_config(col_field)
            if col_config and col_config.width_percent > 0:
                # Calculate width based on percentage
                width = int(total_width * col_config.width_percent / 100)
                self.tbl.setColumnWidth(col_idx, width)

    def _place_fab(self):
        # Adjust FAB position relative to the table viewport
        if hasattr(self.tbl, 'viewport') and self.tbl.viewport().width() > 0 and self.tbl.viewport().height() > 0 and self.tbl.isVisible():
            try:
                viewport_rect = self.tbl.viewport().geometry()
                # Map viewport's bottom right corner to main window coordinates
                # Map to parent (table) first, then map table coordinate to main window
                table_relative_point = self.tbl.viewport().mapToParent(viewport_rect.bottomRight())
                main_window_point = self.tbl.mapTo(self, table_relative_point)

                fab_x = main_window_point.x() - self.fab.width() - 15
                fab_y = main_window_point.y() - self.fab.height() - 15

                # Ensure FAB stays within the main window bounds
                fab_x = max(10, min(fab_x, self.width() - self.fab.width() - 10)) # Add padding
                fab_y = max(10, min(fab_y, self.height() - self.fab.height() - 10)) # Add padding
                self.fab.move(fab_x, fab_y)
            except Exception as e:
                debug_print('CLICK_DETECTION', f"Error placing FAB: {e}") # Catch potential errors during mapping


    def _copy_selection(self):
        selection = self.tbl.selectedRanges()
        if not selection: return

        # Determine the overall bounding box of the selection
        min_row, max_row = self.tbl.rowCount(), -1
        min_col, max_col = self.tbl.columnCount(), -1

        for r in selection:
            min_row = min(min_row, r.topRow())
            max_row = max(max_row, r.bottomRow())
            min_col = min(min_col, r.leftColumn())
            max_col = max(max_col, r.rightColumn())

        if min_row > max_row or min_col > max_col: return

        empty_row_index = len(self.transactions) + len(self.pending)
        # Exclude the '+' row from copy
        max_row = min(max_row, empty_row_index - 1)
        if min_row > max_row: return # If only '+' row was selected or selection invalid

        output = []
        for r in range(min_row, max_row + 1):
            row_data = []
            for c in range(min_col, max_col + 1):
                # Check if this specific cell is within any of the selected ranges
                cell_is_selected = any(
                    sel_range.topRow() <= r <= sel_range.bottomRow() and
                    sel_range.leftColumn() <= c <= sel_range.rightColumn()
                    for sel_range in selection
                )

                if cell_is_selected:
                    item = self.tbl.item(r, c)
                    # Get the display text for copied data (what user sees)
                    display_text = item.text() if item else ""
                    # Replace newline characters to prevent breaking TSV structure
                    display_text = display_text.replace('\n', ' ').replace('\t', ' ')
                    row_data.append(display_text)
                else:
                     # For cells within the bounding box but not explicitly selected, add empty string
                     row_data.append("")
            output.append("\t".join(row_data))

        if output:
             QGuiApplication.clipboard().setText("\n".join(output))
             rows_copied = max_row - min_row + 1
             self._show_message(f"Copied {rows_copied} row(s) to clipboard.", error=False)

    def _paste(self):
        clip_text = QGuiApplication.clipboard().text()
        if not clip_text:
             self._show_message("Clipboard is empty.", error=False) # Not really an error
             return

        lines = clip_text.splitlines()
        if not lines: return # No lines after split

        current_index = self.tbl.currentIndex()
        if not current_index.isValid():
             self._show_message("Please select a starting cell for paste.", error=True)
             return

        start_row = current_index.row()
        start_col = current_index.column()
        num_clip_rows = len(lines)
        num_clip_cols = max(len(line.split('\t')) for line in lines) if lines else 0

        empty_row_idx = len(self.transactions) + len(self.pending)
        max_target_row = start_row + num_clip_rows - 1

        # --- Handle pasting into/past the '+' row ---
        num_new_rows_needed = 0
        if max_target_row >= empty_row_idx:
            num_new_rows_needed = max_target_row - empty_row_idx + 1

        if num_new_rows_needed > 0:
             reply = QMessageBox.question(self, 'Paste - Add Rows',
                                     f'Pasting requires adding {num_new_rows_needed} new row(s).\nContinue?',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.Yes)
             if reply != QMessageBox.StandardButton.Yes:
                 return

             # Add blank rows first
             for _ in range(num_new_rows_needed):
                 # Don't focus during bulk add
                 self._add_blank_row(focus_col=-1) # _add_blank_row calls _refresh

             # Recalculate empty_row_idx after adding rows
             empty_row_idx = len(self.transactions) + len(self.pending)

        # --- Perform Paste Operation ---
        self.tbl.blockSignals(True)
        affected_rows_cols = set()
        commands_to_push = []

        try:
            for r_offset, line in enumerate(lines):
                target_row = start_row + r_offset
                if target_row >= empty_row_idx: # Should not exceed if new rows were added
                    print(f"Warning: Paste target row {target_row} exceeds available rows {empty_row_idx}")
                    break # Safety break

                fields = line.split('\t')
                for c_offset, value_str in enumerate(fields):
                    target_col = start_col + c_offset
                    if target_col < len(self.COLS): # Ensure target column is valid
                        col_key = self.COLS[target_col]

                        # --- Get OLD value ---
                        old_value = None
                        num_transactions = len(self.transactions) # Recalculate in case rows were added
                        is_pending = target_row >= num_transactions

                        if is_pending:
                            pending_index = target_row - num_transactions
                            if 0 <= pending_index < len(self.pending):
                                old_value = self.pending[pending_index].get(col_key, "")
                        else:
                            if 0 <= target_row < num_transactions:
                                old_value = self.transactions[target_row].get(col_key, "")
                        old_value_str = str(old_value) if old_value is not None else ""

                        # --- Determine NEW value (basic type conversion attempt) ---
                        new_value = value_str.strip() # Start with the string value
                        try:
                            if col_key == 'transaction_value':
                                # Clean up the value string by removing currency symbols and formatting
                                cleaned_value = new_value

                                # Remove currency symbols and codes ($ MXN, $ USD, etc.)
                                currency_patterns = [r'\$ [A-Z]{3}', r'\$[A-Z]{3}', r'\$']
                                for pattern in currency_patterns:
                                    cleaned_value = re.sub(pattern, '', cleaned_value)

                                # Remove commas used as thousand separators
                                cleaned_value = cleaned_value.replace(',', '')

                                # Strip any remaining whitespace
                                cleaned_value = cleaned_value.strip()

                                debug_print('FOREIGN_KEYS', f"PASTE: Transaction value '{new_value}' cleaned to '{cleaned_value}'")

                                # Try to convert to float
                                amount_val, ok = self.locale.toFloat(cleaned_value)
                                if ok:
                                    new_value = amount_val
                                    debug_print('FOREIGN_KEYS', f"PASTE: Converted transaction value '{cleaned_value}' to {amount_val}")
                                else:
                                    debug_print('FOREIGN_KEYS', f"PASTE: Failed to convert transaction value '{cleaned_value}' to float")
                                    new_value = old_value # Revert if invalid amount format
                            # Handle account column - convert account name to account_id
                            elif col_key == 'account':
                                # Check if the pasted value is an account name
                                account_id = None
                                for acc in self._accounts_data:
                                    if acc['name'] == new_value:
                                        account_id = acc['id']
                                        break

                                if account_id is not None:
                                    # Use the account ID instead of the name
                                    new_value = account_id
                                    debug_print('FOREIGN_KEYS', f"PASTE: Converted account name '{value_str}' to ID {account_id}")
                                else:
                                    # If account name not found, keep original value
                                    new_value = old_value
                                    debug_print('FOREIGN_KEYS', f"PASTE: Account name '{value_str}' not found, keeping original value")
                            # Handle category column - convert category name to category_id
                            elif col_key == 'category':
                                # Get the transaction type for context
                                transaction_type = None
                                if is_pending:
                                    pending_index = target_row - num_transactions
                                    if 0 <= pending_index < len(self.pending):
                                        transaction_type = self.pending[pending_index].get('transaction_type', 'Expense')
                                else:
                                    if 0 <= target_row < num_transactions:
                                        transaction_type = self.transactions[target_row].get('transaction_type', 'Expense')

                                if not transaction_type:
                                    transaction_type = 'Expense'  # Default

                                # Find category ID for the given name and transaction type
                                category_id = None
                                for cat in self._categories_data:
                                    if cat['name'] == new_value and cat['type'] == transaction_type:
                                        category_id = cat['id']
                                        break

                                if category_id is not None:
                                    # Use the category ID instead of the name
                                    new_value = category_id
                                    debug_print('FOREIGN_KEYS', f"PASTE: Converted category name '{value_str}' to ID {category_id}")
                                else:
                                    # If category name not found, keep original value
                                    new_value = old_value
                                    debug_print('FOREIGN_KEYS', f"PASTE: Category name '{value_str}' not found for type {transaction_type}, keeping original value")
                            # Handle subcategory column - convert subcategory name to subcategory_id
                            elif col_key == 'sub_category':
                                # Get the category ID for context
                                category_id = None
                                if is_pending:
                                    pending_index = target_row - num_transactions
                                    if 0 <= pending_index < len(self.pending):
                                        category_id = self.pending[pending_index].get('category_id')
                                else:
                                    if 0 <= target_row < num_transactions:
                                        category_id = self.transactions[target_row].get('category_id')

                                if category_id is not None:
                                    # Find subcategory ID for the given name and category ID
                                    subcategory_id = None
                                    for subcat in self._subcategories_data:
                                        if subcat['name'] == new_value and subcat['category_id'] == category_id:
                                            subcategory_id = subcat['id']
                                            break

                                    if subcategory_id is not None:
                                        # Use the subcategory ID instead of the name
                                        new_value = subcategory_id
                                        debug_print('FOREIGN_KEYS', f"PASTE: Converted subcategory name '{value_str}' to ID {subcategory_id}")
                                    else:
                                        # If subcategory name not found, keep original value
                                        new_value = old_value
                                        debug_print('FOREIGN_KEYS', f"PASTE: Subcategory name '{value_str}' not found for category ID {category_id}, keeping original value")
                                else:
                                    # If no category ID context, keep original value
                                    new_value = old_value
                                    debug_print('FOREIGN_KEYS', f"PASTE: No category ID context for subcategory '{value_str}', keeping original value")
                            # No specific conversion needed for other columns,
                            # rely on validation during save. Keep as string.
                        except Exception as e:
                            debug_print('FOREIGN_KEYS', f"PASTE: Error converting value: {e}")
                            new_value = old_value # Revert on any conversion error

                        new_value_str = str(new_value)

                        # --- Create Command if value changed ---
                        if new_value is not None and new_value_str != old_value_str:
                            command = CellEditCommand(self, target_row, target_col, old_value, new_value)
                            commands_to_push.append(command)
                            affected_rows_cols.add((target_row, target_col))

        finally:
            self.tbl.blockSignals(False)

        # --- Push Commands and Update UI ---
        if commands_to_push:
            self.undo_stack.beginMacro(f"Paste {len(commands_to_push)} cell(s)")
            for cmd in commands_to_push:
                self.undo_stack.push(cmd) # Pushing runs redo(), which updates data and UI
            self.undo_stack.endMacro()

            # Update currency display for any rows where account was changed
            account_col_index = self.COLS.index('account') if 'account' in self.COLS else -1
            if account_col_index >= 0:
                for row, col in affected_rows_cols:
                    if col == account_col_index:
                        debug_print('CURRENCY', f"PASTE: Updating currency display for row {row} after account change")
                        self._update_currency_display_for_row(row)

            # Explicitly refresh the UI to ensure pasted data is visible
            self._refresh()

            self._show_message(f"Pasted data into {len(affected_rows_cols)} cell(s).", error=False)
        else:
             self._show_message("Paste operation did not change any cell values.", error=False)


    def _show_message(self, msg, error=False):
        color = '#ff5252' if error else '#81d4fa' # Red for error, blue for info
        self._message.setText(msg)
        self._message.setStyleSheet(f'color:{color}; font-weight:bold; padding:4px;')
        # Clear the message after 5 seconds
        QTimer.singleShot(5000, lambda: self._message.setText(''))

    def _refresh(self):
        """Refreshes the table display based on self.transactions and self.pending."""
        self.tbl.blockSignals(True)
        current_selection = self.tbl.selectedRanges() # Preserve selection if possible
        current_v_scroll = self.tbl.verticalScrollBar().value() # Preserve scroll
        current_h_scroll = self.tbl.horizontalScrollBar().value()

        num_transactions = len(self.transactions)
        num_pending = len(self.pending)
        total_rows_required = num_transactions + num_pending + 1 # +1 for '+' row

        # Adjust row count if necessary
        if total_rows_required != self.tbl.rowCount():
             self.tbl.setRowCount(total_rows_required)

        font = QFont('Segoe UI', 11)
        delegate = self.tbl.itemDelegate() # Get delegate for formatting

        # Define colors directly (stylesheet might override parts)
        color_text = QColor('#f3f3f3')
        color_base_even = QColor('#23272e'); color_base_odd = QColor('#262b33')
        color_error = QColor('#a94442')
        color_dirty = QColor('#4a4a3a')
        color_row_error_soft = QColor('#3c2224')
        color_row_dirty_soft = QColor('#3a3a2c')
        color_row_pending_soft = QColor('#263038')
        color_plus_row = QColor('#23272e')

        # --- Populate Rows ---
        all_data = self.transactions + self.pending # Use self.transactions
        for r, row_data in enumerate(all_data):
            rowid = row_data.get('rowid') if r < num_transactions else None
            is_pending = r >= num_transactions
            row_has_error = r in self.errors and bool(self.errors[r])
            row_is_dirty = rowid in self.dirty if rowid else False

            # Ensure account_id is properly set for each row
            if 'account' in row_data and isinstance(row_data['account'], str):
                # Make sure account_id is an integer
                if 'account_id' in row_data and row_data['account_id'] is not None:
                    try:
                        row_data['account_id'] = int(row_data['account_id'])
                    except (ValueError, TypeError):
                        # If account_id is not a valid integer, try to find it from account name
                        row_data['account_id'] = None

                # If account_id is still None or not set, try to find it from account name
                if not row_data.get('account_id'):
                    for acc in self._accounts_data:
                        if acc['name'] == row_data['account']:
                            row_data['account_id'] = acc['id']
                            break

            # Determine base row color
            base_bg = color_base_even if r % 2 == 0 else color_base_odd
            if row_has_error: row_base_color = color_row_error_soft
            elif is_pending: row_base_color = color_row_pending_soft
            elif row_is_dirty: row_base_color = color_row_dirty_soft
            else: row_base_color = base_bg

            field_errors = self.errors.get(r, {}) # Errors are keyed by visual row index
            dirty_fields_set = self.dirty_fields.get(rowid, set()) if rowid else set()

            # Use self.COLS for display columns
            for c, key in enumerate(self.COLS):
                # Get the value from row_data based on the key defined in self.COLS
                # Handle potential missing keys gracefully, although _load_transactions should provide them
                value = row_data.get(key, '')

                # Special handling for account, category, and sub_category to ensure we display names, not IDs
                if key == 'account' and isinstance(value, int):
                    # If we have an account ID instead of a name, look up the name
                    for acc in self._accounts_data:
                        if acc['id'] == value:
                            value = acc['name']
                            break
                elif key == 'category':
                    # CRITICAL FIX: Handle ID conflicts using the mapping
                    if row_data.get('category_id') in self._id_conflict_mapping.get('category', {}):
                        forced_name = self._id_conflict_mapping['category'][row_data['category_id']]
                        value = forced_name
                        # Also update the underlying data to ensure consistency
                        row_data['category'] = forced_name
                        debug_print('CATEGORY', f"REFRESH FIX: Forcing display of {forced_name} for category_id={row_data['category_id']} in row {r} (is_pending={is_pending})")
                    # If we have a category ID instead of a name, look up the name
                    elif isinstance(value, int):
                        for cat in self._categories_data:
                            if cat['id'] == value:
                                value = cat['name']
                                # Update the underlying data to ensure consistency
                                row_data['category'] = cat['name']
                                break
                    # If the value is a string but matches an account name, it's likely a mistake
                    # This fixes the issue where bank account names appear in the category column
                    elif isinstance(value, str):
                        is_account_name = False
                        for acc in self._accounts_data:
                            if acc['name'] == value:
                                is_account_name = True
                                break

                        # If it's an account name or if it's not a valid category name, set to UNCATEGORIZED
                        if is_account_name or value not in [cat['name'] for cat in self._categories_data]:
                            # Find UNCATEGORIZED category for the current transaction type
                            transaction_type = row_data.get('transaction_type', 'Expense')
                            uncategorized_cat = None
                            for cat in self._categories_data:
                                if cat['name'] == 'UNCATEGORIZED' and cat['type'] == transaction_type:
                                    uncategorized_cat = cat
                                    break

                            if uncategorized_cat:
                                value = 'UNCATEGORIZED'
                                # Update the underlying data to fix the issue
                                row_data['category'] = 'UNCATEGORIZED'
                                row_data['category_id'] = uncategorized_cat['id']

                                # Find or create UNCATEGORIZED subcategory for this category
                                uncategorized_subcat = None
                                for subcat in self._subcategories_data:
                                    if subcat['category_id'] == uncategorized_cat['id'] and subcat['name'] == 'UNCATEGORIZED':
                                        uncategorized_subcat = subcat
                                        break

                                if uncategorized_subcat:
                                    row_data['sub_category'] = 'UNCATEGORIZED'
                                    row_data['sub_category_id'] = uncategorized_subcat['id']
                                else:
                                    # Create UNCATEGORIZED subcategory if it doesn't exist
                                    uncategorized_id = self.db.ensure_subcategory('UNCATEGORIZED', uncategorized_cat['id'])
                                    if uncategorized_id:
                                        row_data['sub_category'] = 'UNCATEGORIZED'
                                        row_data['sub_category_id'] = uncategorized_id
                                        # Reload dropdown data in the background
                                        QTimer.singleShot(0, self._load_dropdown_data)
                elif key == 'sub_category':
                    # If we have a subcategory ID instead of a name, look up the name
                    if isinstance(value, int):
                        for subcat in self._subcategories_data:
                            if subcat['id'] == value:
                                value = subcat['name']
                                break
                    # If the subcategory is empty or invalid but we have a category, set to UNCATEGORIZED
                    elif row_data.get('category_id') is not None:
                        # Check if the current subcategory is valid for this category
                        is_valid = False
                        if value:
                            for subcat in self._subcategories_data:
                                if subcat['category_id'] == row_data.get('category_id') and subcat['name'] == value:
                                    is_valid = True
                                    row_data['sub_category_id'] = subcat['id']
                                    break

                        # If not valid or if category is UNCATEGORIZED, set subcategory to UNCATEGORIZED
                        category_is_uncategorized = False
                        for cat in self._categories_data:
                            if cat['id'] == row_data.get('category_id') and cat['name'] == 'UNCATEGORIZED':
                                category_is_uncategorized = True
                                break

                        if not is_valid or category_is_uncategorized:
                            # Find or create UNCATEGORIZED subcategory for this category
                            category_id = row_data.get('category_id')
                            if category_id:
                                uncategorized_found = False
                                for subcat in self._subcategories_data:
                                    if subcat['category_id'] == category_id and subcat['name'] == 'UNCATEGORIZED':
                                        value = 'UNCATEGORIZED'
                                        row_data['sub_category'] = 'UNCATEGORIZED'
                                        row_data['sub_category_id'] = subcat['id']
                                        uncategorized_found = True
                                        debug_print('SUBCATEGORY', f"Fixed: Set subcategory to UNCATEGORIZED (ID: {subcat['id']})")
                                        break

                                # If not found, create it
                                if not uncategorized_found and self.db:
                                    debug_print('SUBCATEGORY', f"Creating UNCATEGORIZED subcategory for category ID {category_id}")
                                    uncategorized_id = self.db.ensure_subcategory('UNCATEGORIZED', category_id)
                                    if uncategorized_id:
                                        value = 'UNCATEGORIZED'
                                        row_data['sub_category'] = 'UNCATEGORIZED'
                                        row_data['sub_category_id'] = uncategorized_id
                                        debug_print('SUBCATEGORY', f"Created and set subcategory to UNCATEGORIZED (ID: {uncategorized_id})")
                                        # Add to our local data
                                        self._subcategories_data.append({
                                            'id': uncategorized_id,
                                            'name': 'UNCATEGORIZED',
                                            'category_id': category_id
                                        })
                                        # Reload dropdown data in the background
                                        QTimer.singleShot(0, self._load_dropdown_data)

                item = self.tbl.item(r, c)
                if item is None:
                    item = QTableWidgetItem()
                    self.tbl.setItem(r, c, item)

                # Special handling for transaction_value to ensure correct currency
                if key == 'transaction_value' and isinstance(value, Decimal):
                    # Format with the correct currency based on the account
                    account_name = row_data.get('account')
                    account_id = row_data.get('account_id')

                    # If we have an account name but no ID, try to find the ID
                    if account_name and not account_id:
                        for acc in self._accounts_data:
                            if acc['name'] == account_name:
                                account_id = acc['id']
                                row_data['account_id'] = account_id
                                break

                    # Get the currency for this account
                    if account_id:
                        currency_info = self.db.get_account_currency(account_id)
                        if currency_info and 'currency_symbol' in currency_info:
                            # Format with the currency symbol
                            formatted_value = self.locale.toString(float(value), 'f', 2)
                            display_text = f"{currency_info['currency_symbol']} {formatted_value}"
                        else:
                            # Use delegate's displayText as fallback
                            display_text = delegate.displayText(value, self.locale)
                    else:
                        # Use delegate's displayText as fallback
                        display_text = delegate.displayText(value, self.locale)
                else:
                    # Use delegate's displayText for formatting (especially for numbers/dates)
                    # The delegate itself will need updating later for new types like account/category
                    display_text = delegate.displayText(value, self.locale) # Pass locale

                # Special handling for category display
                if key == 'category':
                    # SPECIAL CASE: Direct fix for the Bank of America vs UNCATEGORIZED conflict
                    # If display_text is "Bank of America" but we're trying to set UNCATEGORIZED
                    if display_text == "Bank of America" and (value == "UNCATEGORIZED" or row_data.get('category') == "UNCATEGORIZED"):
                        debug_print('CATEGORY', f"DIRECT FIX: Found 'Bank of America' in category field when it should be 'UNCATEGORIZED' for row {r}")

                        # Force it to be UNCATEGORIZED
                        display_text = 'UNCATEGORIZED'
                        row_data['category'] = 'UNCATEGORIZED'

                        # Find the correct UNCATEGORIZED category ID
                        transaction_type = row_data.get('transaction_type', 'Expense')
                        for cat in self._categories_data:
                            if cat['name'] == 'UNCATEGORIZED' and cat['type'] == transaction_type:
                                row_data['category_id'] = cat['id']
                                break

                        # Force immediate update of the display text for this cell
                        item.setText('UNCATEGORIZED')

                        # Also update the subcategory cell if it exists
                        subcat_item = self.tbl.item(r, 5)  # Column 5 is subcategory
                        if subcat_item:
                            subcat_item.setText('UNCATEGORIZED')

                    # First, check if the current display text is an account name (which would be wrong)
                    # Do this check first before any other processing
                    is_account_name = False
                    for acc in self._accounts_data:
                        if acc['name'] == display_text or acc['name'] == value:
                            is_account_name = True
                            debug_print('CATEGORY', f"Found account name '{display_text}' in category field for row {r}")
                            break

                    # If it's an account name, fix it immediately by setting to UNCATEGORIZED
                    if is_account_name:
                        transaction_type = row_data.get('transaction_type', 'Expense')
                        for cat in self._categories_data:
                            if cat['name'] == 'UNCATEGORIZED' and cat['type'] == transaction_type:
                                display_text = 'UNCATEGORIZED'
                                row_data['category'] = 'UNCATEGORIZED'
                                row_data['category_id'] = cat['id']
                                debug_print('CATEGORY', f"Fixed account name in category field to UNCATEGORIZED (ID: {cat['id']})")

                                # Also update subcategory to match
                                for subcat in self._subcategories_data:
                                    if subcat['category_id'] == cat['id'] and subcat['name'] == 'UNCATEGORIZED':
                                        row_data['sub_category'] = 'UNCATEGORIZED'
                                        row_data['sub_category_id'] = subcat['id']
                                        break

                                # Force immediate update of the display text for this cell
                                item.setText('UNCATEGORIZED')

                                # Also update the subcategory cell if it exists
                                subcat_item = self.tbl.item(r, 5)  # Column 5 is subcategory
                                if subcat_item:
                                    subcat_item.setText('UNCATEGORIZED')
                                break
                    # If not an account name, proceed with normal category handling
                    else:
                        # Check if we have a valid category_id
                        if row_data.get('category_id'):
                            # SPECIAL CASE: If category_id is 1, ALWAYS display as UNCATEGORIZED
                            # This handles the specific ID conflict between Bank of America (ID 1) and UNCATEGORIZED (ID 1)
                            if row_data.get('category_id') == 1:
                                # Make sure we're displaying UNCATEGORIZED, not Bank of America
                                display_text = 'UNCATEGORIZED'
                                # Force immediate update of the display text for this cell
                                item.setText('UNCATEGORIZED')
                                # Also ensure the underlying data is consistent
                                row_data['category'] = 'UNCATEGORIZED'
                                debug_print('CATEGORY', f"CRITICAL FIX: Forced display of UNCATEGORIZED for category_id=1 in row {r}")

                            # Check if the category_id matches an account_id (which would be wrong)
                            is_account_id = False
                            for acc in self._accounts_data:
                                if acc['id'] == row_data.get('category_id'):
                                    is_account_id = True
                                    debug_print('CATEGORY', f"Found account ID {acc['id']} in category_id field for row {r}")
                                    break

                            # If it's an account ID, fix it by setting to UNCATEGORIZED
                            if is_account_id:
                                transaction_type = row_data.get('transaction_type', 'Expense')
                                for cat in self._categories_data:
                                    if cat['name'] == 'UNCATEGORIZED' and cat['type'] == transaction_type:
                                        display_text = 'UNCATEGORIZED'
                                        row_data['category'] = 'UNCATEGORIZED'
                                        row_data['category_id'] = cat['id']
                                        debug_print('CATEGORY', f"Fixed account ID in category_id field to UNCATEGORIZED (ID: {cat['id']})")

                                        # Also update subcategory to match
                                        for subcat in self._subcategories_data:
                                            if subcat['category_id'] == cat['id'] and subcat['name'] == 'UNCATEGORIZED':
                                                row_data['sub_category'] = 'UNCATEGORIZED'
                                                row_data['sub_category_id'] = subcat['id']
                                                break

                                        # Force immediate update of the display text for this cell
                                        item.setText('UNCATEGORIZED')

                                        # Also update the subcategory cell if it exists
                                        subcat_item = self.tbl.item(r, 5)  # Column 5 is subcategory
                                        if subcat_item:
                                            subcat_item.setText('UNCATEGORIZED')
                                        break
                            # If not an account ID, ensure we display the correct category name
                            else:
                                category_found = False
                                for cat in self._categories_data:
                                    if cat['id'] == row_data.get('category_id'):
                                        display_text = cat['name']
                                        category_found = True
                                        # Also update the underlying data to ensure consistency
                                        row_data['category'] = cat['name']
                                        break

                                # If category ID doesn't match any known category, set to UNCATEGORIZED
                                if not category_found:
                                    transaction_type = row_data.get('transaction_type', 'Expense')
                                    for cat in self._categories_data:
                                        if cat['name'] == 'UNCATEGORIZED' and cat['type'] == transaction_type:
                                            display_text = 'UNCATEGORIZED'
                                            row_data['category'] = 'UNCATEGORIZED'
                                            row_data['category_id'] = cat['id']
                                            debug_print('CATEGORY', f"Fixed invalid category ID {row_data.get('category_id')} to UNCATEGORIZED (ID: {cat['id']})")

                                            # Force immediate update of the display text for this cell
                                            item.setText('UNCATEGORIZED')

                                            # Also update subcategory to match
                                            for subcat in self._subcategories_data:
                                                if subcat['category_id'] == cat['id'] and subcat['name'] == 'UNCATEGORIZED':
                                                    row_data['sub_category'] = 'UNCATEGORIZED'
                                                    row_data['sub_category_id'] = subcat['id']

                                                    # Update the subcategory cell if it exists
                                                    subcat_item = self.tbl.item(r, 5)  # Column 5 is subcategory
                                                    if subcat_item:
                                                        subcat_item.setText('UNCATEGORIZED')
                                                    break
                                            break

                # Special handling for subcategory display
                if key == 'sub_category':
                    # Debug print to see what's happening with subcategory values
                    debug_print('SUBCATEGORY', f"Row {r}, ID={row_data.get('sub_category_id')}, Value='{value}', Display='{display_text}'")

                    # Ensure we display the correct subcategory name based on the ID
                    if row_data.get('sub_category_id'):
                        found = False
                        for subcat in self._subcategories_data:
                            if subcat['id'] == row_data.get('sub_category_id'):
                                # Verify this subcategory belongs to the current category
                                if subcat['category_id'] == row_data.get('category_id'):
                                    display_text = subcat['name']
                                    found = True

                                    break
                                else:
                                    debug_print('SUBCATEGORY', f"WARNING: Subcategory ID {subcat['id']} belongs to category {subcat['category_id']}, not {row_data.get('category_id')}")

                        if not found:
                            # If we couldn't find the subcategory or it doesn't belong to the current category, force it to UNCATEGORIZED
                            debug_print('SUBCATEGORY', f"WARNING: Valid subcategory ID {row_data.get('sub_category_id')} not found for category ID {row_data.get('category_id')}")
                            # Find the correct UNCATEGORIZED subcategory for this category
                            category_id = row_data.get('category_id')
                            if category_id:
                                uncategorized_found = False
                                for subcat in self._subcategories_data:
                                    if subcat['category_id'] == category_id and subcat['name'] == 'UNCATEGORIZED':
                                        display_text = 'UNCATEGORIZED'
                                        row_data['sub_category'] = 'UNCATEGORIZED'
                                        row_data['sub_category_id'] = subcat['id']
                                        uncategorized_found = True
                                        debug_print('SUBCATEGORY', f"Fixed: Set subcategory to UNCATEGORIZED (ID: {subcat['id']})")
                                        break

                                # If we couldn't find an UNCATEGORIZED subcategory, create one
                                if not uncategorized_found and self.db:
                                    debug_print('SUBCATEGORY', f"Creating UNCATEGORIZED subcategory for category ID {category_id}")
                                    uncategorized_id = self.db.ensure_subcategory('UNCATEGORIZED', category_id)
                                    if uncategorized_id:
                                        display_text = 'UNCATEGORIZED'
                                        row_data['sub_category'] = 'UNCATEGORIZED'
                                        row_data['sub_category_id'] = uncategorized_id
                                        debug_print('SUBCATEGORY', f"Created and set subcategory to UNCATEGORIZED (ID: {uncategorized_id})")
                                        # Add to our local data
                                        self._subcategories_data.append({
                                            'id': uncategorized_id,
                                            'name': 'UNCATEGORIZED',
                                            'category_id': category_id
                                        })
                                        # Reload dropdown data in the background
                                        QTimer.singleShot(0, self._load_dropdown_data)

                item.setText(display_text)

                # Apply special styling for description field - smaller, grayer text
                if key == 'transaction_description':
                    description_font = QFont('Segoe UI', 10)  # Smaller font
                    description_font.setItalic(True)  # Italic for less prominence
                    item.setFont(description_font)
                    item.setForeground(QColor('#a0a0a0'))  # Lighter gray color

                    # No longer adding the [...] indicator since we have the Edit button
                else:
                    item.setFont(font)
                    item.setForeground(color_text)

                # Determine cell background color
                cell_bg = row_base_color # Start with row base
                # Highlight specific cells with errors
                if key in field_errors: cell_bg = color_error
                # Highlight specific dirty cells (only if no error on the cell)
                elif rowid and key in dirty_fields_set and key not in field_errors: cell_bg = color_dirty

                item.setBackground(cell_bg)
                # Set flags (editable depends on column type - delegate will handle this better later)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable)

        # --- Populate '+' Row ---
        r_empty = num_transactions + num_pending
        for c in range(len(self.COLS)):
             item = self.tbl.item(r_empty, c)
             if item is None:
                 item = QTableWidgetItem()
                 self.tbl.setItem(r_empty, c, item)
             # Display '+' in the first column only (index 0)
             item.setText('+' if c == 0 else '')
             item.setFont(font)
             item.setForeground(color_text)
             item.setBackground(color_plus_row)
             # Make '+' row selectable but not editable
             item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)

        # --- Restore UI State ---
        self.tbl.blockSignals(False)
        self.tbl.verticalScrollBar().setValue(current_v_scroll)
        self.tbl.horizontalScrollBar().setValue(current_h_scroll)
        # Restore selection (might be imperfect if rows were added/deleted)
        self.tbl.clearSelection()
        for sel_range in current_selection:
             # Adjust range if it extends beyond new row count
             top_row = sel_range.topRow()
             bottom_row = min(sel_range.bottomRow(), total_rows_required - 1)
             if bottom_row >= top_row:
                 # Create a new selection range instead of modifying the existing one
                 new_range = QTableWidgetSelectionRange(
                     top_row,
                     sel_range.leftColumn(),
                     bottom_row,
                     sel_range.rightColumn()
                 )
                 self.tbl.setRangeSelected(new_range, True)

        self._update_button_states() # Update button states based on pending/dirty

        # Print the table contents to the terminal
        self._debug_print_table()

    def _debug_print_table(self):
        """Debug function to print the table contents to the terminal."""
        # Only print table contents if TABLE_DISPLAY debug category is enabled
        if debug_config.is_enabled('TABLE_DISPLAY'):
            print("\n===== TABLE CONTENTS =====")
            print(f"{'Row':<4} | {'Status':<12} | {'Transaction Name':<20} | {'Value':<15} | {'Account':<20} | {'Type':<10} | {'Category':<20} | {'Sub Category':<20}")
            print("-" * 140)

            num_transactions = len(self.transactions)
            all_data = self.transactions + self.pending

            for row in range(self.tbl.rowCount() - 1):  # Skip the '+' row
                row_data = []
                for col in range(self.tbl.columnCount()):
                    item = self.tbl.item(row, col)
                    text = item.text() if item else ""

                    # Check if we need to convert an ID to a name for display
                    if row < len(all_data) and col < len(self.COLS):
                        col_key = self.COLS[col]
                        # If the text looks like a numeric ID for category or subcategory
                        if text.isdigit() and col_key in ['category', 'sub_category']:
                            # For category, convert ID to name
                            if col_key == 'category':
                                category_id = int(text)
                                for cat in self._categories_data:
                                    if cat['id'] == category_id:
                                        text = cat['name']
                                        break

                            # For subcategory, convert ID to name
                            elif col_key == 'sub_category':
                                subcategory_id = int(text)
                                for subcat in self._subcategories_data:
                                    if subcat['id'] == subcategory_id:
                                        text = subcat['name']
                                        break

                    row_data.append(text)

                # Determine row status with color indicators
                status = ""
                status_color = ""
                if row < num_transactions:
                    # This is a saved transaction
                    transaction = self.transactions[row]
                    rowid = transaction.get('rowid')

                    # Check if this row is in the dirty set
                    is_dirty = False
                    if rowid in self.dirty:
                        is_dirty = True
                    # Also check if any field in the row is different from the original
                    elif rowid in self._original_data_cache:
                        original = self._original_data_cache.get(rowid, {})
                        for key, value in transaction.items():
                            if key.startswith('_') or key == 'rowid':
                                continue
                            if key in original and original[key] != value:
                                is_dirty = True
                                break

                    if is_dirty:
                        status = "[MODIFIED]"
                        status_color = "\033[33m"  # Yellow for modified
                    else:
                        status = "[SAVED]"
                        status_color = "\033[32m"  # Green for saved
                else:
                    # This is a pending (new) transaction
                    status = "[NEW]"
                    status_color = "\033[36m"  # Cyan for new

                    # Check if it has validation errors
                    pending_idx = row - num_transactions
                    if pending_idx < len(self.pending):
                        if self.pending[pending_idx].get('_has_error'):
                            status = "[NEW/ERROR]"
                            status_color = "\033[31m"  # Red for errors

                # Add reset color code
                status_with_color = f"{status_color}{status}\033[0m"

                # Highlight modified fields in the table display
                modified_fields = []
                if row < num_transactions and self.transactions[row].get('rowid') in self.dirty:
                    rowid = self.transactions[row].get('rowid')
                    original = self._original_data_cache.get(rowid, {})
                    # Check which fields are modified
                    if original.get('transaction_name') != self.transactions[row].get('transaction_name'):
                        modified_fields.append(0)  # Transaction Name column
                    if original.get('transaction_value') != self.transactions[row].get('transaction_value'):
                        modified_fields.append(1)  # Value column
                    if original.get('account') != self.transactions[row].get('account'):
                        modified_fields.append(2)  # Account column
                    if original.get('transaction_type') != self.transactions[row].get('transaction_type'):
                        modified_fields.append(3)  # Type column
                    if original.get('category') != self.transactions[row].get('category'):
                        modified_fields.append(4)  # Category column
                    if original.get('sub_category') != self.transactions[row].get('sub_category'):
                        modified_fields.append(5)  # Sub Category column

                # Format the row data with status and highlight modified fields
                field_values = []
                for i, value in enumerate(row_data[:6]):  # Only process the first 6 columns
                    if i in modified_fields:
                        # Highlight modified fields with asterisks
                        field_values.append(f"*{value[:18]}*" if i == 0 else f"*{value}*")
                    else:
                        field_values.append(value[:20] if i == 0 else value)

                print(f"{row:<4} | {status_with_color:<12} | {field_values[0]:<20} | {field_values[1]:<15} | {field_values[2]:<20} | {field_values[3]:<10} | {field_values[4]:<20} | {field_values[5]:<20}")

            print("========================\n")

        # Only print underlying data if UNDERLYING_DATA debug category is enabled
        if debug_config.is_enabled('UNDERLYING_DATA'):
            print("===== UNDERLYING DATA =====")
            num_transactions = len(self.transactions)
            all_data = self.transactions + self.pending
            for i, data in enumerate(all_data):
                # Determine row status for data display with color indicators
                status = ""
                status_color = ""
                if i < num_transactions:
                    rowid = data.get('rowid')

                    # Check if this row is in the dirty set
                    is_dirty = False
                    if rowid in self.dirty:
                        is_dirty = True
                    # Also check if any field in the row is different from the original
                    elif rowid in self._original_data_cache:
                        original = self._original_data_cache.get(rowid, {})
                        for key, value in data.items():
                            if key.startswith('_') or key == 'rowid':
                                continue
                            if key in original and original[key] != value:
                                is_dirty = True
                                break

                    if is_dirty:
                        status = "[MODIFIED]"
                        status_color = "\033[33m"  # Yellow for modified
                    else:
                        status = "[SAVED]"
                        status_color = "\033[32m"  # Green for saved
                else:
                    # This is a pending (new) transaction
                    status = "[NEW]"
                    status_color = "\033[36m"  # Cyan for new
                    if data.get('_has_error'):
                        status = "[NEW/ERROR]"
                        status_color = "\033[31m"  # Red for errors

                # Add reset color code
                status_with_color = f"{status_color}{status}\033[0m"

                account_id = data.get('account_id')
                account_name = data.get('account')
                currency_info = None
                if account_id is not None:
                    try:
                        currency_info = self.db.get_account_currency(account_id)
                    except Exception as e:
                        print(f"Error getting currency for account {account_id}: {e}")

                # Get category and subcategory names for display
                category_id = data.get('category_id')
                category_name = data.get('category', '')
                # If category is a numeric ID, convert to name
                if isinstance(category_name, int) or (isinstance(category_name, str) and category_name.isdigit()):
                    for cat in self._categories_data:
                        if cat['id'] == (int(category_name) if isinstance(category_name, str) else category_name):
                            category_name = cat['name']
                            break

                subcategory_id = data.get('sub_category_id')
                subcategory_name = data.get('sub_category', '')
                # If subcategory is a numeric ID, convert to name
                if isinstance(subcategory_name, int) or (isinstance(subcategory_name, str) and subcategory_name.isdigit()):
                    for subcat in self._subcategories_data:
                        if subcat['id'] == (int(subcategory_name) if isinstance(subcategory_name, str) else subcategory_name):
                            subcategory_name = subcat['name']
                            break

                # Include transaction value and status in the output
                value = data.get('transaction_value', 'N/A')
                print(f"Row {i} {status_with_color}: Account={account_name}, Account ID={account_id}, Value={value}, Currency={currency_info}")

                # Add category and subcategory information
                print(f"    Category={category_name}, Category ID={category_id}, Sub Category={subcategory_name}, Sub Category ID={subcategory_id}")

                # If the row is dirty or has errors, show what fields are modified or have errors
                if is_dirty if i < num_transactions else False:
                    rowid = data.get('rowid')
                    original = self._original_data_cache.get(rowid, {})
                    changes = []
                    for key, value in data.items():
                        if key.startswith('_') or key == 'rowid':
                            continue
                        if key in original and original[key] != value:
                            changes.append(f"{key}: '{original[key]}' -> '{value}'")
                    if changes:
                        print(f"  Changes: {', '.join(changes)}")

                if data.get('_has_error'):
                    errors = data.get('_errors', {})
                    if errors:
                        print(f"  Errors: {errors}")

            print("========================\n")

    def _update_button_states(self):
        # Check for any changes in transactions or pending rows
        has_changes = bool(self.pending) or bool(self.dirty)

        # Debug output to help diagnose issues
        debug_print('TRANSACTION_EDIT', f"_update_button_states: pending={bool(self.pending)}, dirty={bool(self.dirty)}")
        debug_print('TRANSACTION_EDIT', f"_update_button_states: dirty rows={self.dirty}")

        # Enable save and discard buttons if there are changes
        self.save_btn.setEnabled(has_changes)
        self.discard_btn.setEnabled(has_changes)
        self.clear_btn.setEnabled(bool(self.pending))

        # Enable delete if any valid data row is selected (using self.selected_rows)
        num_transactions = len(self.transactions)
        num_pending = len(self.pending)
        empty_row_idx = num_transactions + num_pending
        can_delete = any(row_idx < empty_row_idx for row_idx in self.selected_rows)
        self.del_btn.setEnabled(can_delete)

        # Enable edit button if exactly one valid data row is selected
        can_edit = len(self.selected_rows) == 1 and list(self.selected_rows)[0] < empty_row_idx
        self.edit_btn.setEnabled(can_edit)

        # Update undo/redo actions (if connected to menu/toolbar)
        # undo_action.setEnabled(self.undo_stack.canUndo())
        # redo_action.setEnabled(self.undo_stack.canRedo())


    def _clear_selected_cells_content(self):
        selected_indexes = self.tbl.selectedIndexes()
        if not selected_indexes: return

        empty_row_index = len(self.transactions) + len(self.pending)
        valid_selected_indexes = [idx for idx in selected_indexes if idx.row() < empty_row_index]

        if not valid_selected_indexes:
             self._show_message("No valid data cells selected to clear.", error=False)
             return

        affected_rows_cols = set()
        commands_to_push = []

        self.tbl.blockSignals(True)
        try:
            for idx in valid_selected_indexes:
                row, col = idx.row(), idx.column()
                # Get the key corresponding to the *visual* column index from self.COLS
                if col >= len(self.COLS):
                     print(f"Warning: Column index {col} out of bounds for COLS.")
                     continue # Skip if column index is invalid
                col_key = self.COLS[col]

                # --- Get OLD value --- #
                old_value = None
                num_transactions = len(self.transactions)
                is_pending = row >= num_transactions

                current_data_source = None
                if is_pending:
                    pending_index = row - num_transactions
                    if 0 <= pending_index < len(self.pending):
                        current_data_source = self.pending[pending_index]
                        old_value = current_data_source.get(col_key, "")
                else:
                    if 0 <= row < num_transactions:
                        current_data_source = self.transactions[row]
                        old_value = current_data_source.get(col_key, "")
                old_value_str = str(old_value) if old_value is not None else ""

                # --- Determine NEW (default/empty) value based on column key --- #
                new_value = "" # Default empty string
                if col_key == 'transaction_value': new_value = 0.00
                elif col_key == 'transaction_date': new_value = datetime.now().strftime('%Y-%m-%d')
                # For linked fields (account, category, sub_category), clearing might be complex.
                # Setting to UNCATEGORIZED or a default account might be better than nulling IDs.
                # Let's set names to UNCATEGORIZED/first account for now, validation/save should handle IDs.
                elif col_key == 'account':
                    new_value = self._accounts_data[0]['name'] if self._accounts_data else ''
                elif col_key == 'category':
                    new_value = 'UNCATEGORIZED' # Assuming UNCATEGORIZED exists for the row's type
                elif col_key == 'sub_category':
                     new_value = 'UNCATEGORIZED' # Assuming it exists for the category
                # transaction_type probably shouldn't be clearable this way.
                # We need the actual IDs for category/subcategory defaults, requires more context
                # For now, we only set default *text* for display, CellEditCommand needs updating
                # to handle setting IDs based on text for these columns.

                new_value_str = str(new_value)

                # --- Create Command if value changes --- #
                if old_value_str != new_value_str:
                    # IMPORTANT: CellEditCommand needs updating to handle setting related IDs
                    # when a name (like category name) is set via this clear operation.
                    # Passing the *text* value here.
                    command = CellEditCommand(self, row, col, old_value, new_value)
                    commands_to_push.append(command)
                    affected_rows_cols.add((row, col))

        finally:
            self.tbl.blockSignals(False)

        # --- Push Commands ---
        if commands_to_push:
            self.undo_stack.beginMacro(f"Clear {len(commands_to_push)} cell(s)")
            for cmd in commands_to_push:
                self.undo_stack.push(cmd) # Runs redo()
            self.undo_stack.endMacro()

            self._show_message(f"Cleared content of {len(affected_rows_cols)} cell(s).", error=False)
        else:
             self._show_message("Selected cells were already empty or default.", error=False)


    def _replace_editor_content(self, char):
        """Replaces the content of the current editor with the given character."""
        current_index = self.tbl.currentIndex()
        if not current_index.isValid(): return

        # Use indexWidget() to get the editor created by the delegate
        editor = self.tbl.indexWidget(current_index)

        if editor is not None:
            if isinstance(editor, QLineEdit):
                editor.setText(char)
                # Optionally move cursor to end: editor.end(False)
            elif isinstance(editor, QComboBox) and editor.isEditable():
                editor.lineEdit().setText(char)
                # Optionally move cursor to end: editor.lineEdit().end(False)
            # Add other editor types if needed


    def eventFilter(self, obj, event):
        # Filter events on the table widget itself
        if obj == self.tbl:
            if event.type() == QEvent.Type.KeyPress:
                key = event.key()
                current_index = self.tbl.currentIndex()
                text = event.text()

                if not current_index.isValid():
                    return super().eventFilter(obj, event) # No cell selected

                row, col = current_index.row(), current_index.column()
                empty_row_index = len(self.transactions) + len(self.pending)
                is_empty_row = row == empty_row_index
                is_editing = self.tbl.state() == QAbstractItemView.State.EditingState

                # --- Enter Key ---
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    if is_editing:
                        # Let editor's filter handle commit
                        return False
                    elif is_empty_row and col == 0:
                        self._add_blank_row(focus_col=0)
                        return True # Handled
                    else:
                        self.tbl.edit(current_index) # Start editing
                        return True # Handled

                # --- Delete Key --- (Handled by shortcut QShortcut(Qt.Key.Key_Delete, self.tbl))
                # No specific handling needed here unless Backspace should clear cells

                # --- Printable Character ---
                # Check if it's a character intended for input (not modifier, navigation, etc.)
                if text and text.isprintable() and not event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier):
                    if is_empty_row:
                        target_col = col if current_index.isValid() else 0
                        self._add_blank_row(focus_col=target_col)
                        # Get index of the newly added row
                        new_row_index = len(self.transactions) + len(self.pending) - 1
                        if new_row_index >= 0:
                            new_index = self.tbl.model().index(new_row_index, target_col)
                            self.tbl.setCurrentIndex(new_index) # Ensure focus is correct
                            self.tbl.edit(new_index)
                            # Replace content in the new editor after it's created
                            QTimer.singleShot(0, lambda char=text: self._replace_editor_content(char))
                        return True # Handled
                    elif not is_editing:
                        self.tbl.edit(current_index)
                        # Replace content in the editor after it's created
                        QTimer.singleShot(0, lambda char=text: self._replace_editor_content(char))
                        return True # Handled
                    # else: Already editing, let editor handle the input

            # --- Mouse Click ---
            elif event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                pos = event.position().toPoint()
                idx = self.tbl.indexAt(pos)
                if idx.isValid():
                    row, col = idx.row(), idx.column()
                    empty_row_index = len(self.transactions) + len(self.pending)

                    # Check if this is a dropdown column or date column
                    if col < len(self.COLS):
                        col_key = self.COLS[col]
                        is_dropdown_column = col_key in ['transaction_type', 'category', 'sub_category', 'account']
                        is_date_column = col_key == 'transaction_date'

                        # Get the delegate to check if click is on arrow/icon
                        delegate = self.tbl.itemDelegate()
                        click_on_icon = False

                        if hasattr(delegate, 'arrow_rects') and (row, col) in delegate.arrow_rects:
                            # Convert pos to cell coordinates
                            cell_rect = self.tbl.visualRect(idx)
                            cell_pos = QPoint(pos.x() - cell_rect.left(), pos.y() - cell_rect.top())
                            arrow_rect = delegate.arrow_rects[(row, col)]

                            # Check if click is within the arrow/icon area - use relative coordinates
                            relative_x = cell_rect.right() - pos.x()

                            # For date fields, use a wider clickable area
                            if col_key == 'transaction_date':
                                # Make the date icon more clickable
                                if relative_x >= 0 and relative_x <= arrow_rect.width() and pos.y() >= cell_rect.top() and pos.y() <= cell_rect.bottom():
                                    click_on_icon = True
                                    debug_print('CLICK_DETECTION', f"Click on DATE icon detected for row {row}, col {col}, relative_x={relative_x}, arrow_width={arrow_rect.width()}")
                            else:
                                # Standard check for other dropdown fields
                                if relative_x >= 0 and relative_x <= arrow_rect.width() and pos.y() >= cell_rect.top() and pos.y() <= cell_rect.bottom():
                                    click_on_icon = True
                                    debug_print('CLICK_DETECTION', f"Click on icon detected for row {row}, col {col}, key {col_key}")

                        # If clicked directly on the arrow/icon, force immediate dropdown/calendar opening
                        if click_on_icon and row < empty_row_index:
                            # First select the cell
                            self.tbl.setCurrentCell(row, col)

                            # Then immediately start editing
                            editor = self.tbl.edit(idx)

                            # If it's a QComboBox, show the dropdown
                            if editor and isinstance(editor, QComboBox):
                                editor.showPopup()
                            # If it's a QDateEdit or ArrowDateEdit, show the calendar
                            elif editor and (isinstance(editor, QDateEdit) or isinstance(editor, ArrowDateEdit)):
                                # Make sure calendar popup is enabled
                                editor.setCalendarPopup(True)

                                # Force the calendar to show immediately
                                editor.calendarWidget().show()

                            return True  # Handled

                        # Edit button handling removed - now using dedicated button

                        # Description field [...] button handling removed - now using dedicated Edit button

                        # Otherwise, if it's a dropdown/date column and not the empty row, just start editing
                        elif (is_dropdown_column or is_date_column) and row < empty_row_index:
                            # Set current cell and start editing
                            self.tbl.setCurrentCell(row, col)
                            self.tbl.edit(idx)
                            return True  # Handled

            # --- Double-Click ---
            elif event.type() == QEvent.Type.MouseButtonDblClick:
                pos = event.position().toPoint()
                idx = self.tbl.indexAt(pos)
                if idx.isValid():
                    row, col = idx.row(), idx.column()
                    empty_row_index = len(self.transactions) + len(self.pending)
                    if row == empty_row_index and col == 0:
                        self._add_blank_row(focus_col=0)
                        # Focus is set in _add_blank_row, don't start edit automatically
                        return True # Handled
                # Default double-click behavior (start editing) will happen otherwise

        # Fallback to default behavior
        return super().eventFilter(obj, event)


    def closeEvent(self, event):
        # Check if there are unsaved changes using the undo stack's clean state
        # if not self.undo_stack.isClean(): # Alternative check
        if self.pending or self.dirty:
            reply = QMessageBox.question(self, 'Unsaved Changes',
                                         "You have unsaved changes. Save before closing?",
                                         QMessageBox.StandardButton.Save |
                                         QMessageBox.StandardButton.Discard |
                                         QMessageBox.StandardButton.Cancel,
                                         QMessageBox.StandardButton.Save) # Default to Save

            if reply == QMessageBox.StandardButton.Save:
                self._save_changes()
                # Check again if save failed or was incomplete
                if self.errors or self.pending or self.dirty:
                     self._show_message("Save failed or incomplete. Close cancelled.", error=True)
                     event.ignore(); return # Prevent closing
                else:
                     event.accept() # Save successful, allow closing
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept() # Discard changes, allow closing
            else: # Cancel
                event.ignore() # Prevent closing
        else:
            event.accept() # No unsaved changes, allow closing

        # Close DB connection if window is closing
        if event.isAccepted():
             debug_print('FOREIGN_KEYS', "Closing database connection...")
             self.db.close()
             debug_print('FOREIGN_KEYS', "Database connection closed.")


def show_debug_menu():
    """Show the debug configuration menu."""
    from financial_tracker_app.utils.debug_config import show_debug_menu
    show_debug_menu()

if __name__ == '__main__':
    app = QApplication(sys.argv)

    # Apply the custom style to the entire application
    custom_style = CustomProxyStyle()
    app.setStyle(custom_style)

    # Add debug menu option
    if len(sys.argv) > 1 and sys.argv[1] == '--debug':
        show_debug_menu()

    gui = ExpenseTrackerGUI()
    gui.show()
    sys.exit(app.exec())

# --- END OF FILE main_window.py ---