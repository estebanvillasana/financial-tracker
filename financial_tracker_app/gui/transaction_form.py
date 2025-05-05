"""
Transaction form component for the financial tracker application.
This module contains the TransactionForm class which handles the input form
for adding new transactions.
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                            QGroupBox, QLabel, QLineEdit, QPushButton)
from PyQt6.QtCore import pyqtSignal, QDate
from PyQt6.QtGui import QIcon

from financial_tracker_app.gui.custom_widgets import ArrowComboBox, ArrowDateEdit
from financial_tracker_app.gui.description_dialog import show_description_dialog
from financial_tracker_app.logic.default_values import default_values
from financial_tracker_app.utils.debug_config import debug_print

class TransactionForm(QWidget):
    """
    A form widget for adding new transactions.

    This class provides a form with fields for entering transaction details
    and buttons for adding transactions and managing default values.
    """

    # Define signals
    addTransactionSignal = pyqtSignal(dict)  # Emitted when a transaction is added
    openDefaultsDialogSignal = pyqtSignal()  # Emitted when the defaults button is clicked

    def __init__(self, parent=None):
        """Initialize the transaction form."""
        super().__init__(parent)

        # Create form widgets
        self._create_widgets()

        # Set up the layout
        self._setup_layout()

        # Connect signals
        self._connect_signals()

        # Dictionary to hold form widgets for default values
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

    def _create_widgets(self):
        """Create the form widgets."""
        # Input fields
        self.name_in = QLineEdit(placeholderText='Transaction Name')
        self.value_in = QLineEdit(placeholderText='Value (e.g., 12.34)')
        self.type_in = ArrowComboBox()
        self.type_in.addItems(['Expense', 'Income'])
        self.account_in = ArrowComboBox()
        self.cat_in = ArrowComboBox()
        self.subcat_in = ArrowComboBox()

        # Description field with button
        self.desc_in = QLineEdit(placeholderText='Description')
        self.desc_btn = QPushButton("...")
        self.desc_btn.setToolTip("Edit description in multi-line editor")
        self.desc_btn.setFixedWidth(30)

        # Date field
        self.date_in = ArrowDateEdit(parent=self)
        self.date_in.setDate(QDate.currentDate())
        self.date_in.setDisplayFormat("dd MMM yyyy")

        # Buttons
        self.add_btn = QPushButton('Add Transaction')
        self.add_btn.setIcon(QIcon.fromTheme("list-add", QIcon(":/icons/add.png")))

        self.defaults_btn = QPushButton('Defaults')
        self.defaults_btn.setIcon(QIcon.fromTheme("preferences-system", QIcon(":/icons/settings.png")))
        self.defaults_btn.setToolTip("Set default values for new transactions")

    def _setup_layout(self):
        """Set up the form layout."""
        # Main layout
        main_layout = QVBoxLayout(self)

        # Form group
        form_group = QGroupBox('Add Transaction')
        form_grid = QGridLayout()
        form_grid.setHorizontalSpacing(15)
        form_grid.setVerticalSpacing(10)
        form_group.setLayout(form_grid)

        # Add form fields to grid
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

        # Description field with button
        desc_layout = QHBoxLayout()
        desc_layout.setContentsMargins(0, 0, 0, 0)
        desc_layout.addWidget(self.desc_in, stretch=1)
        desc_layout.addWidget(self.desc_btn)

        desc_container = QWidget()
        desc_container.setLayout(desc_layout)
        form_grid.addWidget(desc_container, 3, 1, 1, 3)

        form_grid.addWidget(QLabel('Date:'), 4, 0)
        form_grid.addWidget(self.date_in, 4, 1)

        # Add buttons
        form_grid.addWidget(self.add_btn, 5, 0, 1, 2)  # Span 2 columns
        form_grid.addWidget(self.defaults_btn, 5, 2, 1, 2)  # Span 2 columns

        # Add form group to main layout
        main_layout.addWidget(form_group)

    def _connect_signals(self):
        """Connect widget signals to slots."""
        self.add_btn.clicked.connect(self._on_add_clicked)
        self.defaults_btn.clicked.connect(self._on_defaults_clicked)
        self.desc_btn.clicked.connect(self._on_desc_button_clicked)

        # Connect type change to category filter
        self.type_in.currentIndexChanged.connect(self._on_type_changed)

        # Connect category change to subcategory filter
        self.cat_in.currentIndexChanged.connect(self._on_category_changed)

    def _on_add_clicked(self):
        """Handle add button click."""
        # Gather form data
        transaction_data = {
            'transaction_name': self.name_in.text(),
            'transaction_value': self.value_in.text(),
            'transaction_type': self.type_in.currentText(),
            'account': self.account_in.currentText(),
            'category': self.cat_in.currentText(),
            'sub_category': self.subcat_in.currentText(),
            'transaction_description': self.desc_in.text(),
            'transaction_date': self.date_in.date().toString("yyyy-MM-dd")
        }

        # Emit signal with transaction data
        self.addTransactionSignal.emit(transaction_data)

        # Clear form or apply defaults (will be handled by main window)

    def _on_defaults_clicked(self):
        """Handle defaults button click."""
        self.openDefaultsDialogSignal.emit()

    def _on_desc_button_clicked(self):
        """Handle description button click."""
        current_text = self.desc_in.text()
        new_text = show_description_dialog(self.parent(), current_text)

        if new_text is not None:  # None means dialog was canceled
            self.desc_in.setText(new_text)
            debug_print('TRANSACTION_FORM', "Description updated.")

    def _on_type_changed(self, index):
        """Handle transaction type change."""
        # This will be implemented to filter categories based on type
        transaction_type = self.type_in.currentText()
        debug_print('TRANSACTION_FORM', f"Transaction type changed to {transaction_type}")
        # Will emit a signal or call a method to update categories

    def _on_category_changed(self, index):
        """Handle category change."""
        # This will be implemented to filter subcategories based on category
        category = self.cat_in.currentText()
        debug_print('TRANSACTION_FORM', f"Category changed to {category}")
        # Will emit a signal or call a method to update subcategories

    def populate_accounts(self, accounts):
        """Populate the accounts dropdown."""
        self.account_in.clear()
        for account in accounts:
            self.account_in.addItem(account['name'], account['id'])

    def populate_categories(self, categories, transaction_type=None):
        """Populate the categories dropdown, filtered by transaction type if provided."""
        self.cat_in.clear()

        # Filter categories by transaction type if provided
        filtered_categories = categories
        if transaction_type:
            filtered_categories = [c for c in categories if c['type'] == transaction_type]

        for category in filtered_categories:
            self.cat_in.addItem(category['name'], category['id'])

    def populate_subcategories(self, subcategories, category_id=None):
        """Populate the subcategories dropdown, filtered by category if provided."""
        self.subcat_in.clear()

        # Filter subcategories by category if provided
        filtered_subcategories = subcategories
        if category_id:
            filtered_subcategories = [s for s in subcategories if s['category_id'] == category_id]

        for subcategory in filtered_subcategories:
            self.subcat_in.addItem(subcategory['name'], subcategory['id'])

    def apply_defaults(self):
        """Apply default values to the form."""
        default_values.apply_to_form(self.form_widgets)

    def clear(self):
        """Clear all form fields."""
        self.name_in.clear()
        self.value_in.clear()
        self.desc_in.clear()
        self.date_in.setDate(QDate.currentDate())
        # Don't clear dropdowns, just reset to first item
        self.type_in.setCurrentIndex(0)
        if self.account_in.count() > 0:
            self.account_in.setCurrentIndex(0)
        if self.cat_in.count() > 0:
            self.cat_in.setCurrentIndex(0)
        if self.subcat_in.count() > 0:
            self.subcat_in.setCurrentIndex(0)