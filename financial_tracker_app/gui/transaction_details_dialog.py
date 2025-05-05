"""
Dialog for viewing and editing transaction details
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, 
                            QLineEdit, QTextEdit, QComboBox, QDateEdit, 
                            QPushButton, QDialogButtonBox, QLabel, QWidget)
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QIcon, QFont

from financial_tracker_app.gui.custom_widgets import ArrowComboBox, ArrowDateEdit
from financial_tracker_app.utils.debug_config import debug_print
from decimal import Decimal, InvalidOperation

class TransactionDetailsDialog(QDialog):
    """Dialog for viewing and editing transaction details."""

    def __init__(self, parent, transaction_data, accounts_data, categories_data, subcategories_data):
        super().__init__(parent)
        self.setWindowTitle("Transaction Details")
        self.setWindowIcon(QIcon.fromTheme("document-properties", QIcon(":/icons/properties.png")))
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        self.transaction_data = transaction_data.copy()  # Make a copy to avoid modifying the original
        self.accounts_data = accounts_data
        self.categories_data = categories_data
        self.subcategories_data = subcategories_data
        
        self.input_widgets = {}  # To store widgets created in this dialog
        
        self._build_ui()
        self._populate_data()
        
    def _build_ui(self):
        """Build the dialog UI."""
        layout = QVBoxLayout(self)
        
        # Title with transaction name
        title_label = QLabel(f"Transaction: {self.transaction_data.get('transaction_name', 'New Transaction')}")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # Form layout for transaction details
        form_layout = QFormLayout()
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        
        # Transaction Name
        self.name_edit = QLineEdit()
        form_layout.addRow("Transaction Name:", self.name_edit)
        self.input_widgets['transaction_name'] = self.name_edit
        
        # Transaction Value
        self.value_edit = QLineEdit()
        form_layout.addRow("Value:", self.value_edit)
        self.input_widgets['transaction_value'] = self.value_edit
        
        # Transaction Type
        self.type_combo = ArrowComboBox()
        self.type_combo.addItems(['Expense', 'Income'])
        self.type_combo.currentTextChanged.connect(self._filter_categories)
        form_layout.addRow("Type:", self.type_combo)
        self.input_widgets['transaction_type'] = self.type_combo
        
        # Account
        self.account_combo = ArrowComboBox()
        form_layout.addRow("Account:", self.account_combo)
        self.input_widgets['account'] = self.account_combo
        
        # Category
        self.category_combo = ArrowComboBox()
        self.category_combo.currentIndexChanged.connect(self._filter_subcategories)
        form_layout.addRow("Category:", self.category_combo)
        self.input_widgets['category'] = self.category_combo
        
        # Subcategory
        self.subcategory_combo = ArrowComboBox()
        form_layout.addRow("Subcategory:", self.subcategory_combo)
        self.input_widgets['sub_category'] = self.subcategory_combo
        
        # Date
        self.date_edit = ArrowDateEdit()
        self.date_edit.setDisplayFormat("dd MMM yyyy")
        self.date_edit.setCalendarPopup(True)
        form_layout.addRow("Date:", self.date_edit)
        self.input_widgets['transaction_date'] = self.date_edit
        
        # Description (multi-line)
        self.desc_edit = QTextEdit()
        self.desc_edit.setMinimumHeight(100)
        self.desc_edit.setStyleSheet("""
            QTextEdit {
                background-color: #2d323b;
                color: #f3f3f3;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 6px;
            }
            QTextEdit:focus {
                border: 1.5px solid #4fc3f7;
            }
        """)
        form_layout.addRow("Description:", self.desc_edit)
        self.input_widgets['transaction_description'] = self.desc_edit
        
        layout.addLayout(form_layout)
        
        # Standard buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | 
                                     QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _populate_data(self):
        """Populate the dialog with transaction data."""
        # Populate accounts dropdown
        self.account_combo.clear()
        for acc in self.accounts_data:
            self.account_combo.addItem(acc['name'], userData=acc['id'])
        
        # Populate transaction type
        transaction_type = self.transaction_data.get('transaction_type', 'Expense')
        type_index = self.type_combo.findText(transaction_type)
        if type_index >= 0:
            self.type_combo.setCurrentIndex(type_index)
        
        # Populate categories based on transaction type
        self._filter_categories(transaction_type)
        
        # Set transaction name
        self.name_edit.setText(self.transaction_data.get('transaction_name', ''))
        
        # Set transaction value
        value = self.transaction_data.get('transaction_value', '')
        if isinstance(value, Decimal):
            self.value_edit.setText(str(value))
        else:
            self.value_edit.setText(str(value) if value else '')
        
        # Set account
        account_id = self.transaction_data.get('account_id')
        if account_id is not None:
            account_index = self.account_combo.findData(account_id)
            if account_index >= 0:
                self.account_combo.setCurrentIndex(account_index)
        
        # Set category
        category_id = self.transaction_data.get('category_id')
        if category_id is not None:
            category_index = self.category_combo.findData(category_id)
            if category_index >= 0:
                self.category_combo.setCurrentIndex(category_index)
        
        # Filter subcategories based on selected category
        self._filter_subcategories()
        
        # Set subcategory
        subcategory_id = self.transaction_data.get('sub_category_id')
        if subcategory_id is not None:
            subcategory_index = self.subcategory_combo.findData(subcategory_id)
            if subcategory_index >= 0:
                self.subcategory_combo.setCurrentIndex(subcategory_index)
        
        # Set date
        date_str = self.transaction_data.get('transaction_date')
        if date_str:
            date = QDate.fromString(date_str, "yyyy-MM-dd")
            if date.isValid():
                self.date_edit.setDate(date)
            else:
                self.date_edit.setDate(QDate.currentDate())
        else:
            self.date_edit.setDate(QDate.currentDate())
        
        # Set description
        description = self.transaction_data.get('transaction_description', '')
        self.desc_edit.setText(description)
    
    def _filter_categories(self, transaction_type=None):
        """Filter categories based on transaction type."""
        if transaction_type is None:
            transaction_type = self.type_combo.currentText()
        
        self.category_combo.clear()
        
        # Add categories for the selected transaction type
        for cat in self.categories_data:
            if cat.get('type') == transaction_type:
                # SPECIAL CASE: Handle the Bank of America vs UNCATEGORIZED conflict
                if cat['id'] == 1:
                    self.category_combo.addItem('UNCATEGORIZED', userData=cat['id'])
                else:
                    self.category_combo.addItem(cat['name'], userData=cat['id'])
        
        # Filter subcategories based on the selected category
        self._filter_subcategories()
    
    def _filter_subcategories(self):
        """Filter subcategories based on selected category."""
        self.subcategory_combo.clear()
        
        category_id = self.category_combo.currentData()
        if category_id is None:
            return
        
        # Add subcategories for the selected category
        for subcat in self.subcategories_data:
            if subcat.get('category_id') == category_id:
                self.subcategory_combo.addItem(subcat['name'], userData=subcat['id'])
    
    def get_updated_data(self):
        """Get the updated transaction data from the dialog."""
        updated_data = self.transaction_data.copy()
        
        # Get transaction name
        updated_data['transaction_name'] = self.name_edit.text().strip()
        
        # Get transaction value
        value_str = self.value_edit.text().strip()
        try:
            updated_data['transaction_value'] = Decimal(value_str) if value_str else Decimal('0')
        except InvalidOperation:
            # Handle invalid decimal format
            debug_print('TRANSACTION_DETAILS', f"Invalid decimal format: {value_str}")
            updated_data['transaction_value'] = self.transaction_data.get('transaction_value', Decimal('0'))
        
        # Get transaction type
        updated_data['transaction_type'] = self.type_combo.currentText()
        
        # Get account
        account_idx = self.account_combo.currentIndex()
        if account_idx >= 0:
            updated_data['account_id'] = self.account_combo.itemData(account_idx)
            updated_data['account'] = self.account_combo.currentText()
        
        # Get category
        category_idx = self.category_combo.currentIndex()
        if category_idx >= 0:
            updated_data['category_id'] = self.category_combo.itemData(category_idx)
            updated_data['category'] = self.category_combo.currentText()
            
            # SPECIAL CASE: Handle the Bank of America vs UNCATEGORIZED conflict
            if updated_data['category_id'] == 1:
                updated_data['category'] = 'UNCATEGORIZED'
        
        # Get subcategory
        subcategory_idx = self.subcategory_combo.currentIndex()
        if subcategory_idx >= 0:
            updated_data['sub_category_id'] = self.subcategory_combo.itemData(subcategory_idx)
            updated_data['sub_category'] = self.subcategory_combo.currentText()
        
        # Get date
        updated_data['transaction_date'] = self.date_edit.date().toString('yyyy-MM-dd')
        
        # Get description
        updated_data['transaction_description'] = self.desc_edit.toPlainText()
        
        return updated_data

def show_transaction_details_dialog(parent, transaction_data, accounts_data, categories_data, subcategories_data):
    """Show the transaction details dialog and return the updated data if accepted."""
    dialog = TransactionDetailsDialog(parent, transaction_data, accounts_data, categories_data, subcategories_data)
    result = dialog.exec()
    
    if result == QDialog.DialogCode.Accepted:
        return dialog.get_updated_data()
    return None  # Return None if canceled
