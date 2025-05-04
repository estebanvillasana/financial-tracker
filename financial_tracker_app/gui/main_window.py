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
                         QKeyEvent, QUndoStack, QGuiApplication, QBrush) # Add QBrush

# --- Updated Imports ---
from financial_tracker_app.data.database import Database
from financial_tracker_app.gui.delegates import SpreadsheetDelegate
from financial_tracker_app.logic.commands import CellEditCommand
from financial_tracker_app.data.column_config import TRANSACTION_COLUMNS, DB_FIELDS, DISPLAY_TITLES, get_column_config
from financial_tracker_app.gui.custom_widgets import ArrowComboBox, ArrowDateEdit
from financial_tracker_app.logic.default_values import default_values
from financial_tracker_app.gui.default_values_ui import show_default_values_dialog # Corrected path
from financial_tracker_app.utils.debug_config import debug_config, debug_print
from financial_tracker_app.utils.debug_control import show_debug_menu # For the menu action
# --- End Updated Imports ---

class ExpenseTrackerGUI(QMainWindow):
    # Define the columns for the *display* table (match the data we'll fetch)
    # Use the column configuration from column_config.py
    COLS = DB_FIELDS

    def __init__(self):
        super().__init__()
        self.db = Database()
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
        # Use the imported show_debug_menu directly
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
        self.desc_in = QLineEdit(placeholderText='Description')
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
        form_grid.addWidget(self.desc_in, 3, 1, 1, 3)
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
        self.save_btn = QPushButton('Save Changes')
        self.save_btn.setIcon(QIcon.fromTheme("document-save", QIcon(":/icons/save.png")))
        self.save_btn.setToolTip("Save all pending additions and modifications (Ctrl+S)")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._save_changes)
        save_shortcut = QShortcut(QKeySequence.StandardKey.Save, self)
        save_shortcut.activated.connect(self._save_changes)

        self.discard_btn = QPushButton('Discard Changes')
        self.discard_btn.setIcon(QIcon.fromTheme("document-revert", QIcon(":/icons/revert.png")))
        self.discard_btn.setToolTip("Discard all unsaved additions and modifications")
        self.discard_btn.setEnabled(False)
        self.discard_btn.clicked.connect(self._discard_changes)

        self.del_btn = QPushButton('Delete Selected')
        self.del_btn.setIcon(QIcon.fromTheme("edit-delete", QIcon(":/icons/delete.png")))
        self.del_btn.setToolTip("Delete selected row(s) from the database (Del)")
        self.del_btn.clicked.connect(self._delete_rows)

        self.clear_btn = QPushButton('Clear New Rows')
        self.clear_btn.setIcon(QIcon.fromTheme("edit-clear", QIcon(":/icons/clear.png")))
        self.clear_btn.setToolTip("Clear newly added rows that haven't been saved yet.")
        self.clear_btn.clicked.connect(self._clear_pending)

        btn_layout.addStretch(1)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addWidget(self.del_btn)
        btn_layout.addWidget(self.discard_btn)
        btn_layout.addWidget(self.save_btn)
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
        # Use the imported show_default_values_dialog directly
        result = show_default_values_dialog(self, self.form_widgets)
        if result == QDialog.DialogCode.Accepted:
            # Re-apply defaults to the form immediately after saving them
            default_values.apply_to_form(self.form_widgets)
            self._show_message("Default values updated.", error=False)

    def _load_dropdown_data(self):
        """Load data needed for dropdowns (accounts, categories, etc.)."""
        # Clear existing data
        self._accounts_data = []
        self._categories_data = []
        self._subcategories_data = []

        try:
            # Use the get_accounts method which returns the desired format
            self._accounts_data = self.db.get_accounts()
            print(f"DEBUG GUI: Loaded {len(self._accounts_data)} accounts.") # <<< Debug Print

            # Use the get_categories method
            self._categories_data = self.db.get_categories()
            print(f"DEBUG GUI: Loaded {len(self._categories_data)} categories.") # <<< Debug Print

            # Use the get_subcategories method
            self._subcategories_data = self.db.get_subcategories()
            print(f"DEBUG GUI: Loaded {len(self._subcategories_data)} subcategories.") # <<< Debug Print

            # Ensure every category has an UNCATEGORIZED subcategory
            self._ensure_uncategorized_subcategories()

            # Pass updated data sources to the delegate
            delegate = self.tbl.itemDelegate()
            if isinstance(delegate, SpreadsheetDelegate):
                delegate.setEditorDataSources(self._accounts_data, self._categories_data, self._subcategories_data)

        except Exception as e:
            print(f"Error loading dropdown data: {e}")
            # Initialize with empty lists if there's an error
            self._accounts_data = []
            self._categories_data = []
            self._subcategories_data = []

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

    def _load_transactions(self, refresh_ui=True):
        """Load transactions from the database and update internal state."""
        # Use the specific DB method designed for the GUI
        fetched_data = self.db.get_all_data_for_gui()
        print(f"DEBUG GUI: Received {len(fetched_data)} transactions from DB.") # <<< Debug Print
        if fetched_data:
             print(f"DEBUG GUI: First transaction data received: {fetched_data[0]}") # <<< Debug Print first row

        self.transactions = [] # Clear existing transactions
        self._original_data_cache = {} # Clear cache

        for data in fetched_data:
            rowid = data.get('rowid')
            if rowid is None:
                print(f"Warning: Skipping row with missing rowid: {data}")
                continue

            # Convert transaction_value to Decimal for proper formatting
            if 'transaction_value' in data and data['transaction_value'] is not None:
                try:
                    data['transaction_value'] = Decimal(str(data['transaction_value']))
                except InvalidOperation:
                    print(f"Warning: Could not convert transaction_value '{data['transaction_value']}' to Decimal for rowid {rowid}. Setting to 0.00.")
                    data['transaction_value'] = Decimal('0.00')

            # Ensure account_id is an integer if present
            if 'account_id' in data and data['account_id'] is not None:
                try:
                    data['account_id'] = int(data['account_id'])
                except (ValueError, TypeError):
                    print(f"Warning: Invalid account_id '{data['account_id']}' for rowid {rowid}. Setting to None.")
                    data['account_id'] = None

            # Ensure category_id is an integer if present (using the key returned by DB)
            if 'category_id' in data and data['category_id'] is not None:
                try:
                    data['category_id'] = int(data['category_id'])
                except (ValueError, TypeError):
                    print(f"Warning: Invalid category_id '{data['category_id']}' for rowid {rowid}. Setting to None.")
                    data['category_id'] = None
            elif 'category_id' not in data: # Ensure key exists even if null
                 data['category_id'] = None


            # Ensure sub_category_id is an integer if present (using the key returned by DB)
            if 'sub_category_id' in data and data['sub_category_id'] is not None:
                try:
                    data['sub_category_id'] = int(data['sub_category_id'])
                except (ValueError, TypeError):
                    print(f"Warning: Invalid sub_category_id '{data['sub_category_id']}' for rowid {rowid}. Setting to None.")
                    data['sub_category_id'] = None
            elif 'sub_category_id' not in data: # Ensure key exists even if null
                 data['sub_category_id'] = None

            # Append the processed data
            self.transactions.append(data)
            self._original_data_cache[rowid] = data.copy() # Cache original state

        # Clear transient states after loading
        self.pending.clear()
        self.dirty.clear()
        self.dirty_fields.clear()
        self.errors.clear()

        if refresh_ui:
            self._refresh() # Refresh the UI table display

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
                # Debug Print for category dropdown
                debug_print('DROPDOWN', f"  Adding Cat item {self.cat_in.count()}: Name='{cat['name']}', ID={cat['id']} (Type: {type(cat['id'])})")
                self.cat_in.addItem(cat['name'], userData=cat['id'])
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
                    # Debug Print for subcategory dropdown
                    debug_print('DROPDOWN', f"  Adding SubCat item {self.subcat_in.count()}: Name='{subcat['name']}', ID={subcat['id']} (Type: {type(subcat['id'])})")
                    self.subcat_in.addItem(subcat['name'], userData=subcat['id'])
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
        # <<< Debug Print before calling add_transaction >>>
        print(f"--- DEBUG GUI: Calling db.add_transaction ---")
        print(f"  Name: {name}")
        print(f"  Desc: {description}")
        print(f"  Acc ID: {account_id} (Type: {type(account_id)})")
        print(f"  Value (float): {float(value_decimal)}")
        print(f"  Type: {type_str}")
        print(f"  Cat ID: {category_id} (Type: {type(category_id)})")
        print(f"  SubCat ID: {subcategory_id} (Type: {type(subcategory_id)})")
        print(f"  Date: {date_str}")
        print(f"---------------------------------------------")

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

    def _discard_changes(self):
        """Discard all unsaved changes (pending additions and modifications)."""
        if not self.pending and not self.dirty:
            self._show_message("No unsaved changes to discard.", error=False)
            return

        reply = QMessageBox.question(self, 'Discard Changes',
                                     'Are you sure you want to discard all unsaved changes?\nThis cannot be undone.',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Clear all transient states (pending, dirty, errors)
        # _load_transactions handles clearing these and reloading data
        self._load_transactions(refresh_ui=True) # Reload original data and refresh UI

        # Clear the undo stack as changes are discarded
        self.undo_stack.clear()
        self.last_saved_undo_index = 0

        self._show_message("Unsaved changes discarded.", error=False)
        self._update_button_states() # Update buttons after discarding

    def _cell_edited(self, row, col):
        """Handles actions after a cell's data has been changed in the model."""
        # This signal is emitted *after* the data in the model has changed.
        # The Undo/Redo command system now handles updating the *underlying* data structures
        # (self.transactions, self.pending) and the dirty/error state based on the command's redo/undo.

        # Check if the account column was edited
        account_col_index = -1
        if 'account' in self.COLS:
            account_col_index = self.COLS.index('account')

        if col == account_col_index:
            # Update the currency display for the transaction value
            self._update_currency_display_for_row(row)

        # We need to ensure recoloring and button states are updated.
        self._recolor_row(row)
        self._update_button_states()

        # Print the current table state to the terminal
        self._debug_print_table()

        # Validation for pending/dirty rows now happens primarily in _save_changes

    def _update_currency_display_for_row(self, row):
        """Update the currency display for the transaction value cell based on the account's currency."""
        value_col_index = -1
        account_col_index = -1
        if 'transaction_value' in self.COLS:
            value_col_index = self.COLS.index('transaction_value')
        if 'account' in self.COLS:
            account_col_index = self.COLS.index('account')

        if value_col_index == -1 or account_col_index == -1:
            return # Required columns not found

        num_transactions = len(self.transactions)
        is_pending = row >= num_transactions
        data_source = None
        account_id = None

        if is_pending:
            pending_index = row - num_transactions
            if 0 <= pending_index < len(self.pending):
                data_source = self.pending[pending_index]
                account_id = data_source.get('account_id')
        else:
            if 0 <= row < num_transactions:
                data_source = self.transactions[row]
                account_id = data_source.get('account_id')

        if account_id is None:
            debug_print('CURRENCY', f"No account ID found for row {row}, cannot update currency display.")
            # Optionally reset to default locale format if no account is set
            value_item = self.tbl.item(row, value_col_index)
            if value_item and data_source:
                 current_value = data_source.get('transaction_value', Decimal('0.00'))
                 value_item.setText(self.locale.toCurrencyString(float(current_value))) # Use default locale
            return

        try:
            currency_code = self.db.get_account_currency(account_id)
            if currency_code:
                temp_locale = QLocale(QLocale.Language.English, QLocale.Country.UnitedStates) # Base locale
                temp_locale.setCurrencySymbol(f"{currency_code} ") # Set the code as symbol

                value_item = self.tbl.item(row, value_col_index)
                if value_item and data_source:
                    current_value = data_source.get('transaction_value', Decimal('0.00'))
                    # Format using the temporary locale with the specific currency code
                    formatted_value = temp_locale.toCurrencyString(float(current_value))
                    value_item.setText(formatted_value)
                    debug_print('CURRENCY', f"Updated row {row} value display to {formatted_value}")

            else:
                 # Fallback to default locale if currency code not found
                 value_item = self.tbl.item(row, value_col_index)
                 if value_item and data_source:
                      current_value = data_source.get('transaction_value', Decimal('0.00'))
                      value_item.setText(self.locale.toCurrencyString(float(current_value)))
                      debug_print('CURRENCY', f"Currency code not found for account {account_id}, using default locale for row {row}")

        except Exception as e:
            print(f"Error updating currency display for row {row}: {e}")

    def _add_blank_row(self, focus_col=0):
        """Adds a new blank row to the pending list and refreshes the table."""
        # --- Initialize Base Structure --- #
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
            for cat in self._categories_data:
                if cat['id'] == new_row_data['category_id'] and cat['type'] == current_type:
                    new_row_data['category'] = cat['name']
                    break
            # If ID is invalid for type, try finding UNCATEGORIZED for the type
            if not new_row_data['category']:
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
             uncategorized_id = None
             for cat in self._categories_data:
                 if cat['name'] == 'UNCATEGORIZED' and cat['type'] == cat_type:
                     uncategorized_id = cat['id']
                     break
             if uncategorized_id:
                 new_row_data['category_id'] = uncategorized_id
                 new_row_data['category'] = 'UNCATEGORIZED'
             else:
                 # This case should ideally be handled by ensuring UNCATEGORIZED exists on load
                 self._show_message(f"Cannot add row: UNCATEGORIZED category for type '{cat_type}' not found.", error=True); return

        if new_row_data.get('sub_category_id') is None:
             # Find or create UNCATEGORIZED subcategory for the selected category
             cat_id = new_row_data.get('category_id')
             if cat_id is not None:
                 uncategorized_sub_id = self.db.ensure_subcategory('UNCATEGORIZED', cat_id)
                 if uncategorized_sub_id:
                     new_row_data['sub_category_id'] = uncategorized_sub_id
                     new_row_data['sub_category'] = 'UNCATEGORIZED'
                     # Reload dropdown data if a new subcategory was created
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
        """Recolors a specific row based on its state (pending, dirty, error)."""
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

        # Determine base background color (alternating)
        base_color = color_base_even if row % 2 == 0 else color_base_odd

        # Determine row state
        is_pending = row >= num_transactions and row < empty_row_index
        is_dirty = False
        has_error = row in self.errors
        is_empty_row = row == empty_row_index

        if not is_pending and not is_empty_row and row < num_transactions:
            rowid = self.transactions[row].get('rowid')
            if rowid in self.dirty:
                is_dirty = True

        # Determine final background color
        final_bg_color = base_color
        if is_empty_row:
            final_bg_color = color_plus_row
        elif has_error:
            final_bg_color = color_row_error_soft
        elif is_pending:
            final_bg_color = color_row_pending_soft
        elif is_dirty:
            final_bg_color = color_row_dirty_soft

        # Apply colors to all cells in the row
        for col in range(self.tbl.columnCount()):
            item = self.tbl.item(row, col)
            if item:
                item.setBackground(final_bg_color)
                item.setForeground(color_text) # Ensure text color is consistent

                # Specific cell highlighting for errors/dirty fields
                if has_error and col < len(self.COLS):
                    col_key = self.COLS[col]
                    if col_key in self.errors.get(row, {}):
                        item.setBackground(color_error) # Bright red for specific error cell
                elif is_dirty and col < len(self.COLS):
                     rowid = self.transactions[row].get('rowid')
                     col_key = self.COLS[col]
                     if rowid in self.dirty_fields and col_key in self.dirty_fields[rowid]:
                          item.setBackground(color_dirty) # Bright yellow for specific dirty cell

        self.tbl.blockSignals(False)

    def _show_message(self, message, error=False, duration=5000):
        """Display a status message."""
        if error:
            self._message.setStyleSheet('color:#ff5252; font-weight:bold; padding:4px;') # Red for errors
        else:
            self._message.setStyleSheet('color:#4fc3f7; font-weight:bold; padding:4px;') # Blue for info
        self._message.setText(message)
        # Clear message after duration
        QTimer.singleShot(duration, lambda: self._message.setText(''))

    def _place_fab(self):
        """Place the Floating Action Button."""
        if hasattr(self, 'fab'):
            margin = 16
            self.fab.move(self.width() - self.fab.width() - margin, 
                         self.height() - self.fab.height() - margin)

    def _update_column_widths(self, logicalIndex=None, oldSize=None, newSize=None):
        """Adjust column widths based on percentages defined in column_config."""
        total_width = self.tbl.viewport().width()
        fixed_width_total = 0
        stretch_cols = []

        # First pass: set fixed widths and identify stretch columns
        for col_idx, col_field in enumerate(self.COLS):
            col_config = get_column_config(col_field)
            if col_config and col_config.width_percent > 0:
                width = int(total_width * (col_config.width_percent / 100.0))
                self.tbl.setColumnWidth(col_idx, width)
                fixed_width_total += width
            else:
                stretch_cols.append(col_idx)

        # Second pass: distribute remaining width among stretch columns
        remaining_width = total_width - fixed_width_total
        if stretch_cols and remaining_width > 0:
            width_per_stretch_col = max(50, remaining_width // len(stretch_cols)) # Ensure a minimum width
            for col_idx in stretch_cols:
                self.tbl.setColumnWidth(col_idx, width_per_stretch_col)
        elif stretch_cols: # If remaining width is zero or negative, give a minimum
            for col_idx in stretch_cols:
                self.tbl.setColumnWidth(col_idx, 50) # Minimum width

    def _refresh(self):
        """Refresh the table display with current data."""
        self.tbl.blockSignals(True)
        self.tbl.setRowCount(0) # Clear table

        num_transactions = len(self.transactions)
        num_pending = len(self.pending)
        total_rows = num_transactions + num_pending + 1 # +1 for the empty row

        self.tbl.setRowCount(total_rows)

        # Populate existing transactions
        for row, data in enumerate(self.transactions):
            for col, field in enumerate(self.COLS):
                value = data.get(field)
                item = QTableWidgetItem()
                item.setData(Qt.ItemDataRole.EditRole, value) # Store raw data
                # Set display text using delegate's logic for formatting
                display_text = self.tbl.itemDelegate().displayText(value, self.locale)
                item.setText(display_text)
                self.tbl.setItem(row, col, item)
            self._recolor_row(row) # Recolor based on state (dirty, error)
            # Update currency display specifically after setting items
            if 'transaction_value' in self.COLS and 'account' in self.COLS:
                self._update_currency_display_for_row(row)

        # Populate pending transactions
        for i, data in enumerate(self.pending):
            row = num_transactions + i
            for col, field in enumerate(self.COLS):
                value = data.get(field)
                item = QTableWidgetItem()
                item.setData(Qt.ItemDataRole.EditRole, value) # Store raw data
                display_text = self.tbl.itemDelegate().displayText(value, self.locale)
                item.setText(display_text)
                self.tbl.setItem(row, col, item)
            self._recolor_row(row) # Recolor as pending
            # Update currency display specifically after setting items
            if 'transaction_value' in self.COLS and 'account' in self.COLS:
                self._update_currency_display_for_row(row)

        # Add the empty '+' row at the bottom
        empty_row_index = total_rows - 1
        plus_item = QTableWidgetItem("+")
        plus_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        plus_item.setFlags(Qt.ItemFlag.ItemIsEnabled) # Not editable, just clickable
        self.tbl.setItem(empty_row_index, 0, plus_item)
        self.tbl.setSpan(empty_row_index, 0, 1, len(self.COLS)) # Span across columns
        self._recolor_row(empty_row_index) # Style the '+' row

        self.tbl.blockSignals(False)
        self._update_button_states()
        # Ensure column widths are recalculated after refresh
        QTimer.singleShot(0, self._update_column_widths)

    def _update_button_states(self):
        """Enable/disable buttons based on current state."""
        has_pending = bool(self.pending)
        has_dirty = bool(self.dirty)
        has_selection = bool(self.selected_rows)

        self.save_btn.setEnabled(has_pending or has_dirty)
        self.discard_btn.setEnabled(has_pending or has_dirty)
        self.del_btn.setEnabled(has_selection)
        self.clear_btn.setEnabled(has_pending)

        # Indicate unsaved changes in window title
        title = "Expense Tracker"
        if has_pending or has_dirty:
            title += " *"
        self.setWindowTitle(title)

    def _capture_selection(self):
        """Update the set of selected row indices."""
        self.selected_rows.clear()
        selected_ranges = self.tbl.selectedRanges()
        num_transactions = len(self.transactions)
        num_pending = len(self.pending)
        empty_row_index = num_transactions + num_pending

        for sel_range in selected_ranges:
            for row in range(sel_range.topRow(), sel_range.bottomRow() + 1):
                if row < empty_row_index: # Exclude the '+' row
                    self.selected_rows.add(row)
        self._update_button_states() # Update delete button state

    def _copy_selection(self):
        """Copy selected cells to clipboard (TSV format)."""
        selected_ranges = self.tbl.selectedRanges()
        if not selected_ranges: return

        clipboard = QGuiApplication.clipboard()
        if not clipboard: return

        # Determine the bounds of the composite selection
        min_row = min(r.topRow() for r in selected_ranges)
        max_row = max(r.bottomRow() for r in selected_ranges)
        min_col = min(r.leftColumn() for r in selected_ranges)
        max_col = max(r.rightColumn() for r in selected_ranges)

        num_transactions = len(self.transactions)
        num_pending = len(self.pending)
        empty_row_index = num_transactions + num_pending

        # Adjust max_row to exclude the empty row if selected
        max_row = min(max_row, empty_row_index - 1)
        if max_row < min_row: return # Nothing valid selected

        tsv_data = []
        for r in range(min_row, max_row + 1):
            row_data = []
            for c in range(min_col, max_col + 1):
                item = self.tbl.item(r, c)
                # Check if the specific cell (r, c) is actually selected
                is_cell_selected = any(
                    r >= sel_range.topRow() and r <= sel_range.bottomRow() and
                    c >= sel_range.leftColumn() and c <= sel_range.rightColumn()
                    for sel_range in selected_ranges
                )
                if item and is_cell_selected:
                    # Get raw data for consistency, handle None
                    raw_value = item.data(Qt.ItemDataRole.EditRole)
                    cell_text = str(raw_value) if raw_value is not None else ""
                    # Replace tabs and newlines within cell text
                    cell_text = cell_text.replace('\t', ' ').replace('\n', ' ').replace('\r', '')
                    row_data.append(cell_text)
                elif is_cell_selected: # Cell is selected but no item (shouldn't happen?)
                    row_data.append("")
                else: # Cell is within bounds but not selected
                    row_data.append("") # Append empty string to maintain structure
            tsv_data.append("\t".join(row_data))

        clipboard.setText("\n".join(tsv_data))
        self._show_message(f"Copied {len(tsv_data)} row(s).", error=False)

    def _paste(self):
        """Paste data from clipboard (TSV format) into the table."""
        clipboard = QGuiApplication.clipboard()
        if not clipboard: return
        tsv_data = clipboard.text()
        if not tsv_data: return

        start_index = self.tbl.currentIndex()
        if not start_index.isValid():
            self._show_message("Select a starting cell to paste.", error=True)
            return

        start_row, start_col = start_index.row(), start_index.column()
        lines = tsv_data.strip('\n').split('\n')

        self.undo_stack.beginMacro("Paste Data")

        num_transactions = len(self.transactions)
        num_pending = len(self.pending)
        empty_row_index = num_transactions + num_pending

        for r_offset, line in enumerate(lines):
            row_to_paste = start_row + r_offset
            if row_to_paste >= empty_row_index:
                # If pasting would go into the empty row or beyond,
                # try adding new rows first.
                num_new_rows_needed = (row_to_paste - empty_row_index) + 1
                for _ in range(num_new_rows_needed):
                    if len(self.transactions) + len(self.pending) < self.tbl.rowCount() -1 : # Check if already added
                        self._add_blank_row()
                    else:
                        # Cannot add more rows (e.g., if _add_blank_row failed)
                        self._show_message("Cannot add new rows to accommodate paste.", error=True)
                        self.undo_stack.endMacro() # Close macro even on failure
                        return
                # Recalculate empty_row_index after adding rows
                empty_row_index = len(self.transactions) + len(self.pending)
                if row_to_paste >= empty_row_index: # Still out of bounds? Should not happen.
                    print(f"Warning: Row index {row_to_paste} still out of bounds after adding rows.")
                    continue

            values = line.split('\t')
            for c_offset, value_str in enumerate(values):
                col_to_paste = start_col + c_offset
                if col_to_paste >= self.tbl.columnCount(): continue # Skip columns outside table bounds

                target_index = self.tbl.model().index(row_to_paste, col_to_paste)
                if not target_index.isValid(): continue # Should be valid now

                col_key = self.COLS[col_to_paste]
                current_item = self.tbl.item(row_to_paste, col_to_paste)
                old_value = current_item.data(Qt.ItemDataRole.EditRole) if current_item else None

                # --- Convert pasted string value to appropriate type ---
                new_value = None
                try:
                    if col_key == 'transaction_value':
                        # Clean currency symbols, group separators etc. before converting
                        cleaned_value = value_str
                        for symbol in ['$', '€', '£', '¥', '₹', '₽', '₩', '₴', '₦', '₱', '฿', '₫', '₲', '₪', '₡', '₢', '₣', '₤', '₥', '₧', '₨', '₩', '₭', '₮', '₯', '₰', '₱', '₲', '₳', '₴', '₵', '₶', '₷', '₸', '₹', '₺', '₻', '₼', '₽', '₾', '₿']:
                            cleaned_value = cleaned_value.replace(symbol, '')
                        cleaned_value = re.sub(r'\s[A-Z]{3}$', '', cleaned_value).strip() # Remove trailing currency codes
                        cleaned_value = cleaned_value.replace(self.locale.groupSeparator(), '')
                        cleaned_value = cleaned_value.replace(self.locale.decimalPoint(), '.')
                        new_value = Decimal(cleaned_value) if cleaned_value else Decimal('0.00')
                    elif col_key == 'transaction_date':
                        # Try parsing common date formats
                        parsed_date = None
                        formats_to_try = ["yyyy-MM-dd", "dd MMM yyyy", "MM/dd/yyyy", "dd.MM.yyyy", "yyyy/MM/dd"]
                        for fmt in formats_to_try:
                            qdate = QDate.fromString(value_str, fmt)
                            if qdate.isValid():
                                parsed_date = qdate.toString("yyyy-MM-dd")
                                break
                        if parsed_date:
                            new_value = parsed_date
                        else:
                            raise ValueError("Invalid date format") # Treat as error if no format matches
                    elif col_key in ['account', 'category', 'sub_category']:
                        # Try to find ID based on pasted name
                        target_id = None
                        if col_key == 'account':
                            target_id = next((acc['id'] for acc in self._accounts_data if acc['name'] == value_str), None)
                        elif col_key == 'category':
                            # Need context of transaction type for categories
                            type_col_idx = self.COLS.index('transaction_type')
                            type_item = self.tbl.item(row_to_paste, type_col_idx)
                            current_type = type_item.data(Qt.ItemDataRole.EditRole) if type_item else 'Expense'
                            target_id = next((cat['id'] for cat in self._categories_data if cat['name'] == value_str and cat['type'] == current_type), None)
                        elif col_key == 'sub_category':
                            # Need context of category for subcategories
                            cat_col_idx = self.COLS.index('category')
                            cat_item = self.tbl.item(row_to_paste, cat_col_idx)
                            current_cat_id = cat_item.data(Qt.ItemDataRole.EditRole) if cat_item else None
                            if current_cat_id is not None:
                                target_id = next((scat['id'] for scat in self._subcategories_data if scat['name'] == value_str and scat['category_id'] == current_cat_id), None)
                        if target_id is not None:
                            new_value = target_id
                        else:
                            # If name doesn't match, keep old value
                            new_value = old_value # Revert to old value if lookup fails
                    elif col_key == 'transaction_type':
                        if value_str in ['Income', 'Expense']:
                            new_value = value_str
                        else:
                            new_value = old_value # Revert if invalid type
                    else: # For text fields like name, description
                        new_value = value_str

                except (InvalidOperation, ValueError) as e:
                    print(f"Warning: Could not convert pasted value '{value_str}' for column {col_key}. Error: {e}")
                    new_value = old_value # Keep old value on conversion error

                # --- Apply Change via Undo Command ---
                if str(new_value) != str(old_value):
                    command = CellEditCommand(self, row_to_paste, col_to_paste, old_value, new_value)
                    self.undo_stack.push(command) # This will trigger _cell_edited via model update

        self.undo_stack.endMacro()
        self._refresh() # Refresh to show pasted data and recoloring
        self._show_message(f"Pasted data for {len(lines)} row(s).", error=False)

    def _delete_rows(self):
        """Delete selected rows from the table and database."""
        if not self.selected_rows:
            self._show_message("No rows selected to delete.", error=True)
            return

        num_transactions = len(self.transactions)
        pending_indices_to_delete = sorted([idx - num_transactions for idx in self.selected_rows if idx >= num_transactions], reverse=True)
        saved_rowids_to_delete = [self.transactions[idx]['rowid'] for idx in self.selected_rows if idx < num_transactions and 'rowid' in self.transactions[idx]]

        pending_rows_deleted_count = 0
        saved_rows_deleted_count = 0

        # --- Delete Pending Rows ---
        if pending_indices_to_delete:
            for index in pending_indices_to_delete:
                if 0 <= index < len(self.pending):
                    del self.pending[index]
                    pending_rows_deleted_count += 1
            # Adjust error keys for remaining pending rows
            new_errors = {}
            for visual_idx, error_data in self.errors.items():
                if visual_idx < num_transactions: # Keep errors for saved rows
                    new_errors[visual_idx] = error_data
                else: # Adjust indices for pending rows
                    original_pending_idx = visual_idx - num_transactions
                    if original_pending_idx not in pending_indices_to_delete:
                        # Calculate new visual index after deletion
                        new_pending_idx = original_pending_idx - sum(1 for deleted_idx in pending_indices_to_delete if deleted_idx < original_pending_idx)
                        new_visual_idx = num_transactions + new_pending_idx
                        new_errors[new_visual_idx] = error_data
            self.errors = new_errors


        # --- Delete Saved Rows ---
        if saved_rowids_to_delete:
            reply = QMessageBox.question(self, 'Confirm Delete',
                                         f'Are you sure you want to permanently delete {len(saved_rowids_to_delete)} saved transaction(s)?\nThis cannot be undone.',
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                # If user cancels DB delete, still proceed with pending delete if any
                if pending_rows_deleted_count > 0:
                    self._refresh()
                    self._show_message(f"Deleted {pending_rows_deleted_count} pending row(s). Database delete cancelled.", error=False)
                else:
                    self._show_message("Delete operation cancelled.", error=False)
                self.selected_rows.clear()
                self._update_button_states()
                return

            try:
                # Use the Database class method for deletion
                success = self.db.delete_transactions(saved_rowids_to_delete)
                if success:
                    saved_rows_deleted_count = len(saved_rowids_to_delete) # Assume all were deleted if method returns True

                    # Update dirty/cache tracking immediately
                    self.dirty.difference_update(saved_rowids_to_delete)
                    for rowid in saved_rowids_to_delete:
                        self.dirty_fields.pop(rowid, None)
                        self._original_data_cache.pop(rowid, None)
                        # Remove errors associated with deleted saved rows
                        # Need to find the visual index before removing the transaction
                        visual_idx_to_remove = -1
                        for v_idx, trans_data in enumerate(self.transactions):
                            if trans_data.get('rowid') == rowid:
                                visual_idx_to_remove = v_idx
                                break
                        if visual_idx_to_remove != -1 and visual_idx_to_remove in self.errors:
                            del self.errors[visual_idx_to_remove]

                    # Reload transactions and refresh the table completely AFTER successful DB delete
                    self._load_transactions() # This implicitly handles refresh
                    self._show_message(f"Deleted {pending_rows_deleted_count} pending and {saved_rows_deleted_count} saved row(s).", error=False)
                    # Clear undo stack after destructive action not managed by commands
                    self.undo_stack.clear()
                    self.last_saved_undo_index = 0
                    return # Exit as _load_transactions already refreshed
                else:
                    self._show_message("Database error occurred during deletion. Some rows might not have been deleted.", error=True)
                    # Don't reload if DB delete failed, just refresh current state
                    self._refresh() # Refresh to show pending deletions if any

            except Exception as e: # Catch potential exceptions from DB method
                self._show_message(f"Error deleting saved rows: {e}", error=True)
                # Don't reload if DB delete failed, just refresh current state
                self._refresh()

        # If only pending rows were deleted (or DB delete failed), refresh
        elif pending_rows_deleted_count > 0:
             self._refresh()
             self._show_message(f"Deleted {pending_rows_deleted_count} pending row(s).", error=False)


        self.selected_rows.clear() # Clear selection after deletion attempt
        self._update_button_states() # Update button states

    def _clear_pending(self):
        """Clear all newly added (pending) rows."""
        if not self.pending:
            self._show_message("No new rows to clear.", error=False)
            return

        reply = QMessageBox.question(self, 'Clear New Rows',
                                     'Are you sure you want to clear all newly added rows?',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            num_cleared = len(self.pending)
            self.pending.clear()
            # Remove errors associated with pending rows
            num_transactions = len(self.transactions)
            self.errors = {idx: err for idx, err in self.errors.items() if idx < num_transactions}
            self._refresh()
            self._show_message(f"Cleared {num_cleared} new row(s).", error=False)

    def _validate_row(self, row_data, row_index_visual):
        """Validate data for a single row (pending or existing). Returns cleaned data dict or None if invalid."""
        errors = {}
        cleaned_data = row_data.copy() # Work on a copy

        # --- Field Validations ---
        # Name (Required)
        name = cleaned_data.get('transaction_name', '').strip()
        if not name: errors['transaction_name'] = "Name cannot be empty."
        else: cleaned_data['transaction_name'] = name

        # Value (Required, must be Decimal > 0)
        value = cleaned_data.get('transaction_value')
        if value is None:
            errors['transaction_value'] = "Value is required."
        elif not isinstance(value, Decimal):
             errors['transaction_value'] = "Value must be a number."
        elif value <= Decimal('0'):
             errors['transaction_value'] = "Value must be positive."
        # else: value is a valid positive Decimal

        # Type (Required)
        trans_type = cleaned_data.get('transaction_type')
        if not trans_type or trans_type not in ['Income', 'Expense']:
            errors['transaction_type'] = "Type must be 'Income' or 'Expense'."

        # Date (Required, valid format)
        date_str = cleaned_data.get('transaction_date')
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
        except (ValueError, TypeError):
            errors['transaction_date'] = "Invalid date format (YYYY-MM-DD)."

        # Account (Required ID)
        account_id = cleaned_data.get('account_id')
        if account_id is None:
            errors['account'] = "Account is required."
        elif not any(acc['id'] == account_id for acc in self._accounts_data):
            errors['account'] = "Selected account is invalid."

        # Category (Required ID, must match Type)
        category_id = cleaned_data.get('category_id')
        if category_id is None:
            errors['category'] = "Category is required."
        else:
            category_valid = False
            for cat in self._categories_data:
                if cat['id'] == category_id and cat['type'] == trans_type:
                    category_valid = True
                    break
            if not category_valid:
                errors['category'] = f"Category invalid for type '{trans_type}'."

        # SubCategory (Required ID, must match Category)
        sub_category_id = cleaned_data.get('sub_category_id')
        if sub_category_id is None:
            errors['sub_category'] = "Subcategory is required."
        else:
            subcategory_valid = False
            for subcat in self._subcategories_data:
                if subcat['id'] == sub_category_id and subcat['category_id'] == category_id:
                    subcategory_valid = True
                    break
            if not subcategory_valid:
                errors['sub_category'] = "Subcategory invalid for selected category."


        # --- Update Global Errors ---
        if errors:
            self.errors[row_index_visual] = errors
            return None # Indicate validation failure
        else:
            # Clear errors for this row if it passes
            if row_index_visual in self.errors:
                del self.errors[row_index_visual]
            # Return the *original* data dict if valid (save logic will use this)
            # We return the original dict because the save logic needs the rowid if present
            return row_data

    def _save_changes(self):
        """Validate pending/dirty rows and save valid changes to the database."""
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
                    # Prepare data for insert (use keys expected by DB method)
                    insert_data = {
                        'name': valid_data.get('transaction_name'),
                        'value': valid_data.get('transaction_value'), # Keep as Decimal for now
                        'account_id': valid_data.get('account_id'),
                        'type': valid_data.get('transaction_type'),
                        'category_id': valid_data.get('category_id'),
                        'sub_category_id': valid_data.get('sub_category_id'),
                        'description': valid_data.get('transaction_description'),
                        'date_str': valid_data.get('transaction_date')
                    }
                    # Check for None values that are required by DB
                    if None in [insert_data['name'], insert_data['value'], insert_data['account_id'],
                                insert_data['type'], insert_data['category_id'], insert_data['sub_category_id'],
                                insert_data['date_str']]:
                         # This should ideally be caught by _validate_row, but double-check
                         self.errors[row_idx_visual] = self.errors.get(row_idx_visual, {})
                         self.errors[row_idx_visual]['save_error'] = "Missing required data for save."
                         failed_pending_errors[i] = self.errors.get(row_idx_visual, {})
                         rows_with_errors_indices.add(row_idx_visual)
                         error_details_for_msgbox.append(f"New Row {i+1}: Missing required data.")
                         pending_rows_that_failed_validation_indices.append(i)
                    else:
                        inserts_to_execute.append(insert_data)
                        pending_rows_that_passed_validation_indices.add(i)
                else:
                    pending_rows_that_failed_validation_indices.append(i)
                    failed_pending_errors[i] = self.errors.get(row_idx_visual, {})
                    rows_with_errors_indices.add(row_idx_visual)
                    err_msg = "; ".join(f"{k.replace('_', ' ').capitalize()}: {v}" for k, v in self.errors.get(row_idx_visual, {}).items())
                    error_details_for_msgbox.append(f"New Row {i+1}: {err_msg}")

            # Validate Dirty Existing Rows
            original_transactions_copy = self.transactions[:] # Copy for safe iteration
            for i, e_row in enumerate(original_transactions_copy):
                rowid = e_row.get('rowid')
                if rowid in self.dirty:
                    row_idx_visual = i
                    valid_data = self._validate_row(e_row, row_idx_visual)
                    if valid_data:
                        # Prepare data for update (use keys expected by DB method)
                        update_data = {
                            'transaction_name': valid_data.get('transaction_name'),
                            'transaction_value': valid_data.get('transaction_value'), # Keep as Decimal
                            'account_id': valid_data.get('account_id'),
                            'transaction_type': valid_data.get('transaction_type'),
                            'category_id': valid_data.get('category_id'),
                            'sub_category_id': valid_data.get('sub_category_id'),
                            'transaction_description': valid_data.get('transaction_description'),
                            'transaction_date': valid_data.get('transaction_date')
                        }
                        # Check for None values that are required by DB
                        if None in [update_data['transaction_name'], update_data['transaction_value'], update_data['account_id'],
                                    update_data['transaction_type'], update_data['category_id'], update_data['sub_category_id'],
                                    update_data['transaction_date']]:
                             self.errors[row_idx_visual] = self.errors.get(row_idx_visual, {})
                             self.errors[row_idx_visual]['save_error'] = "Missing required data for save."
                             failed_existing_errors[rowid] = self.errors.get(row_idx_visual, {})
                             rows_with_errors_indices.add(row_idx_visual)
                             error_details_for_msgbox.append(f"Existing Row {i+1} (ID {rowid}): Missing required data.")
                             dirty_rowids_that_failed_validation.add(rowid)
                             dirty_fields_that_failed_validation[rowid] = self.dirty_fields.get(rowid, set())
                        else:
                            updates_to_execute.append({'rowid': rowid, 'data': update_data})
                            dirty_rowids_that_passed_validation.add(rowid)
                    else:
                        dirty_rowids_that_failed_validation.add(rowid)
                        dirty_fields_that_failed_validation[rowid] = self.dirty_fields.get(rowid, set())
                        failed_existing_errors[rowid] = self.errors.get(row_idx_visual, {})
                        rows_with_errors_indices.add(row_idx_visual)
                        err_msg = "; ".join(f"{k.replace('_', ' ').capitalize()}: {v}" for k, v in self.errors.get(row_idx_visual, {}).items())
                        error_details_for_msgbox.append(f"Existing Row {i+1} (ID {rowid}): {err_msg}")

            # Store the validation errors before clearing self.errors for commit attempt
            validation_errors = self.errors.copy()
            self.errors.clear() # Clear global errors before potential commit

            # --- Phase 2: Attempt to commit valid changes ---
            if inserts_to_execute or updates_to_execute:
                # Use the Database class methods for adding/updating
                inserted_count = 0
                updated_count = 0
                db_error_occurred = False # Reset flag for this block

                try:
                    # --- Inserts ---
                    for insert_data in inserts_to_execute:
                        # Convert Decimal to float just before DB call
                        insert_data['value'] = float(insert_data['value'])
                        new_rowid = self.db.add_transaction(**insert_data)
                        if new_rowid is None:
                            db_error_occurred = True
                            # Try to identify which row failed? Difficult without more info from DB layer
                            print(f"Error inserting data: {insert_data}")
                            # Mark all pending rows involved in inserts as having a DB error
                            for idx in pending_rows_that_passed_validation_indices:
                                visual_row = original_num_transactions_before_save + idx
                                if visual_row not in db_error_state_to_restore: db_error_state_to_restore[visual_row] = {}
                                db_error_state_to_restore[visual_row]['database'] = "Insert failed"
                            break # Stop inserts on first failure
                        else:
                            inserted_count += 1

                    # --- Updates (only if inserts succeeded) ---
                    if not db_error_occurred:
                        for update_item in updates_to_execute:
                            rowid = update_item['rowid']
                            data_to_update = update_item['data']
                            # Convert Decimal to float just before DB call
                            data_to_update['transaction_value'] = float(data_to_update['transaction_value'])
                            success = self.db.update_transaction(rowid, data_to_update)
                            if not success:
                                db_error_occurred = True
                                print(f"Error updating rowid {rowid} with data: {data_to_update}")
                                # Mark this specific rowid as having a DB error
                                for visual_row, trans_data in enumerate(original_transactions_copy):
                                    if trans_data.get('rowid') == rowid:
                                        if visual_row not in db_error_state_to_restore: db_error_state_to_restore[visual_row] = {}
                                        db_error_state_to_restore[visual_row]['database'] = "Update failed"
                                        break
                                # Optionally break updates on first failure, or continue trying others
                                # break

                            else:
                                updated_count += 1

                    # --- Commit or Rollback ---
                    if not db_error_occurred:
                        # Commit is handled within db methods if successful
                        commit_successful = True
                        self.last_saved_undo_index = self.undo_stack.index()
                        self.undo_stack.setClean() # Mark stack as clean after successful save
                    else:
                        # Rollback should ideally be handled within the failed DB method
                        # We just mark commit as failed here
                        commit_successful = False
                        # Combine validation errors with DB errors
                        db_error_state_to_restore.update(validation_errors)


                except Exception as e: # Catch broader exceptions during DB operations
                    db_error_occurred = True
                    commit_successful = False
                    # Combine validation errors with the DB error message
                    db_error_state_to_restore = validation_errors.copy()
                    db_error_msg = f" DB Error: {e}"

                    # Add DB error message to all rows involved in the failed transaction
                    involved_visual_indices = set(rows_with_errors_indices) # Start with validation errors
                    # Add pending rows that passed validation but might have failed commit
                    for i in pending_rows_that_passed_validation_indices:
                        involved_visual_indices.add(original_num_transactions_before_save + i)
                    # Add existing rows that passed validation but might have failed commit
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
                 # Show message already handled in except block

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

    # ...existing code...

    def resizeEvent(self, event):
        """Handle window resize events."""
        super().resizeEvent(event)
        self._place_fab()
        # Trigger column width update on resize
        QTimer.singleShot(0, self._update_column_widths)

    def eventFilter(self, obj, event):
        """Filter events for the table widget."""
        if obj is self.tbl:
            # --- Keyboard Events ---
            if event.type() == QEvent.Type.KeyPress:
                key = event.key()
                modifiers = event.modifiers()
                current_index = self.tbl.currentIndex()
                is_editing = self.tbl.state() == QAbstractItemView.State.EditingState

                # Handle '+' row click simulation with Enter/Return
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not is_editing:
                    if current_index.isValid() and current_index.row() == self.tbl.rowCount() - 1:
                        self._add_blank_row()
                        return True # Event handled

                # Handle typing to start editing or replace content
                if key >= Qt.Key.Key_Space and key <= Qt.Key.Key_Z and not modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier):
                    text = event.text()
                    if text and current_index.isValid() and current_index.row() < self.tbl.rowCount() - 1: # Exclude '+' row
                        col_key = self.COLS[current_index.column()]
                        # Don't auto-replace for dropdowns/date, just open editor
                        if col_key in ['account', 'category', 'sub_category', 'transaction_type', 'transaction_date']:
                            if not is_editing:
                                self.tbl.edit(current_index) # Open editor, but don't replace
                            # Let the editor handle the key press
                            return False # Let editor handle it
                        elif is_editing:
                            # Let the existing editor handle the key press
                            return False
                        else: # For text/numeric fields, start editing and replace
                            self.tbl.edit(current_index)
                            # Replace content in the new editor after it's created
                            QTimer.singleShot(0, lambda char=text: self._replace_editor_content(char))
                            return True # Handled

            # --- Mouse Click ---
            elif event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                pos = event.position().toPoint()
                idx = self.tbl.indexAt(pos)
                if idx.isValid():
                    row, col = idx.row(), idx.column()
                    # Check if clicking the '+' row
                    if row == self.tbl.rowCount() - 1:
                        self._add_blank_row()
                        return True # Event handled

        return super().eventFilter(obj, event)

    def _replace_editor_content(self, char):
        """Replaces the content of the current editor widget."""
        editor = self.tbl.currentEditor()
        if isinstance(editor, QLineEdit):
            editor.setText(char)
            editor.deselect() # Move cursor to end
            editor.end(False)
        # Add handling for other editor types if needed

    def closeEvent(self, event):
        """Handle closing the application."""
        # Check for unsaved changes
        if self.pending or self.dirty:
            reply = QMessageBox.question(self, 'Unsaved Changes',
                                         "You have unsaved changes. Save before closing?",
                                         QMessageBox.StandardButton.Save |
                                         QMessageBox.StandardButton.Discard |
                                         QMessageBox.StandardButton.Cancel,
                                         QMessageBox.StandardButton.Save) # Default to Save

            if reply == QMessageBox.StandardButton.Save:
                self._save_changes()
                # Check again if save failed or was incomplete (errors remain or pending/dirty still exist)
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

    def _debug_print_table(self):
        """Prints the current state of the table and underlying data to the terminal."""
        if not debug_config.is_enabled('TABLE_DISPLAY') and not debug_config.is_enabled('UNDERLYING_DATA'):
            return

        print("\n--- DEBUG: Current Table State ---")
        num_transactions = len(self.transactions)
        num_pending = len(self.pending)
        total_rows = num_transactions + num_pending

        if debug_config.is_enabled('UNDERLYING_DATA'):
            print("--- Underlying self.transactions ---")
            for i, data in enumerate(self.transactions):
                state = []
                rowid = data.get('rowid')
                if rowid in self.dirty: state.append("DIRTY")
                if i in self.errors: state.append("ERROR")
                print(f"  Row {i} (RowID: {rowid}) [{', '.join(state)}]: {data}")
                if rowid in self.dirty_fields: print(f"    Dirty Fields: {self.dirty_fields[rowid]}")
                if i in self.errors: print(f"    Errors: {self.errors[i]}")

            print("--- Underlying self.pending ---")
            for i, data in enumerate(self.pending):
                visual_row = num_transactions + i
                state = ["PENDING"]
                if visual_row in self.errors: state.append("ERROR")
                print(f"  Pending Row {i} (Visual: {visual_row}) [{', '.join(state)}]: {data}")
                if visual_row in self.errors: print(f"    Errors: {self.errors[visual_row]}")

        if debug_config.is_enabled('TABLE_DISPLAY'):
            print("--- Table Display (First few columns) ---")
            headers = [self.tbl.horizontalHeaderItem(c).text() for c in range(min(5, self.tbl.columnCount()))]
            print(" | ".join(headers))
            print("-" * (sum(len(h) for h in headers) + (len(headers) - 1) * 3))

            for r in range(self.tbl.rowCount()):
                row_str = []
                for c in range(min(5, self.tbl.columnCount())):
                    item = self.tbl.item(r, c)
                    text = item.text() if item else "None"
                    row_str.append(text.ljust(len(headers[c])))
                state = []
                if r < num_transactions:
                    rowid = self.transactions[r].get('rowid')
                    if rowid in self.dirty: state.append("D")
                    if r in self.errors: state.append("E")
                elif r < total_rows:
                    state.append("P")
                    if r in self.errors: state.append("E")
                elif r == total_rows: # '+' row
                    state.append("+")

                print(" | ".join(row_str) + f"  [{''.join(state)}]")

        print("--- END DEBUG ---\n")

# ... rest of the file (main execution block) ...
# --- END OF FILE expense_tracker_gui.py ---
