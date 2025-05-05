"""
Transaction table component for the financial tracker application.
This module contains the TransactionTable class which handles the display and interaction
with transaction data in a table format.
"""

from PyQt6.QtWidgets import (QTableWidget, QTableWidgetItem, QHeaderView,
                            QAbstractItemView, QShortcut)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QBrush, QColor, QGuiApplication

from financial_tracker_app.gui.delegates import SpreadsheetDelegate
from financial_tracker_app.data.column_config import DB_FIELDS, DISPLAY_TITLES, get_column_config
from financial_tracker_app.utils.debug_config import debug_print

class TransactionTable(QTableWidget):
    """
    A specialized table widget for displaying and editing financial transactions.

    This class extends QTableWidget to provide functionality specific to the
    financial tracker application, including custom cell rendering, editing,
    and data management.
    """

    # Define signals that will be emitted by this widget
    cellEditedSignal = pyqtSignal(int, int)  # row, column
    selectionChangedSignal = pyqtSignal()

    def __init__(self, parent=None):
        """Initialize the transaction table."""
        # Use the column configuration from column_config.py
        self.COLS = DB_FIELDS
        super().__init__(0, len(self.COLS), parent)

        # Set up the table
        self._setup_table()

        # Connect signals
        self.cellChanged.connect(self._on_cell_changed)
        self.itemSelectionChanged.connect(self._on_selection_changed)

    def _setup_table(self):
        """Set up the table with headers and configuration."""
        # Set column headers
        self.setHorizontalHeaderLabels(DISPLAY_TITLES)

        # Set column widths based on configuration
        for col_idx, col_field in enumerate(self.COLS):
            col_config = get_column_config(col_field)
            if col_config and col_config.width_percent > 0:
                # Set fixed width based on percentage of table width
                # We'll update these widths when the table is resized
                self.horizontalHeader().setSectionResizeMode(col_idx, QHeaderView.ResizeMode.Interactive)
            else:
                # Use stretch mode for columns without specific width
                self.horizontalHeader().setSectionResizeMode(col_idx, QHeaderView.ResizeMode.Stretch)

        # Set edit triggers - include SingleClicked to make dropdowns open with a single click
        self.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked |
                           QAbstractItemView.EditTrigger.EditKeyPressed |
                           QAbstractItemView.EditTrigger.SelectedClicked)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        # Set up shortcuts
        self._setup_shortcuts()

    def _setup_shortcuts(self):
        """Set up keyboard shortcuts for the table."""
        # Copy shortcut
        copy_shortcut = QShortcut(QKeySequence.StandardKey.Copy, self)
        copy_shortcut.activated.connect(self.copy_selection)

        # Paste shortcut
        paste_shortcut = QShortcut(QKeySequence.StandardKey.Paste, self)
        paste_shortcut.activated.connect(self.paste)

    def set_delegate(self, main_window):
        """Set the item delegate for the table."""
        delegate = SpreadsheetDelegate(main_window)
        self.setItemDelegate(delegate)
        return delegate

    def _on_cell_changed(self, row, column):
        """Handle cell changed event."""
        # Emit signal for parent to handle
        self.cellEditedSignal.emit(row, column)

    def _on_selection_changed(self):
        """Handle selection changed event."""
        # Emit signal for parent to handle
        self.selectionChangedSignal.emit()

    def copy_selection(self):
        """Copy selected cells to clipboard."""
        selection = self.selectedRanges()
        if not selection:
            return

        # Determine the overall bounding box of the selection
        min_row, max_row = self.rowCount(), -1
        min_col, max_col = self.columnCount(), -1

        for r in selection:
            min_row = min(min_row, r.topRow())
            max_row = max(max_row, r.bottomRow())
            min_col = min(min_col, r.leftColumn())
            max_col = max(max_col, r.rightColumn())

        if min_row > max_row or min_col > max_col:
            return

        # Get the number of rows (excluding the '+' row)
        empty_row_index = self.rowCount() - 1
        # Exclude the '+' row from copy
        max_row = min(max_row, empty_row_index - 1)
        if min_row > max_row:
            return # If only '+' row was selected or selection invalid

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
                    item = self.item(r, c)
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
             debug_print('TRANSACTION_TABLE', f"Copied {rows_copied} row(s) to clipboard.")
             return rows_copied

        return 0

    def paste(self):
        """Placeholder for paste functionality."""
        # This will be implemented later as it requires access to the data model
        # and other components that will be refactored
        debug_print('TRANSACTION_TABLE', "Paste functionality will be implemented later.")

    def update_column_widths(self):
        """Update column widths based on configuration percentages."""
        # Get the total width of the table
        total_width = self.viewport().width()
        if total_width <= 0:
            return  # Table not visible yet

        # Calculate and set widths based on configuration
        for col_idx, col_field in enumerate(self.COLS):
            col_config = get_column_config(col_field)
            if col_config and col_config.width_percent > 0:
                # Calculate width based on percentage
                width = int(total_width * col_config.width_percent / 100)
                self.setColumnWidth(col_idx, width)