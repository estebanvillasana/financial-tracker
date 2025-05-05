# --- START OF FILE delegates.py ---

import sys
from PyQt6.QtWidgets import (QStyledItemDelegate, QComboBox, QLineEdit, QDateEdit,
                             QStyleOptionViewItem, QStyle, QWidget, QStyleOptionComboBox,
                             QStylePainter, QTextEdit)
from PyQt6.QtCore import Qt, QModelIndex, QTimer, QDate, QLocale, QRect, QPoint
from PyQt6.QtGui import QColor, QIcon, QPixmap, QPainter
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

# --- Updated Imports ---
# Assuming Database might be needed indirectly via parent_window, but not directly imported
# from financial_tracker_app.data.database import Database
from financial_tracker_app.logic.commands import CellEditCommand # Keep if used directly, otherwise remove
from financial_tracker_app.gui.custom_widgets import ArrowComboBox, ArrowDateEdit
from financial_tracker_app.utils.debug_config import debug_config, debug_print
from financial_tracker_app.data.column_config import get_column_config, DISPLAY_TITLES, DB_FIELDS # Import DB_FIELDS
# --- End Updated Imports ---

class SpreadsheetDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent) # parent is now the main_window instance
        # Store the reference to the main window passed as parent
        self.parent_window = parent
        if not self.parent_window:
            # This should ideally not happen now
            print("CRITICAL WARNING: SpreadsheetDelegate initialized without a valid parent window!")
            self.locale = QLocale() # Fallback locale
        else:
             # Use the parent window's locale for consistency
            self.locale = self.parent_window.locale if hasattr(self.parent_window, 'locale') else QLocale()

        # Fallback icon - stylesheet should override
        self.down_arrow_icon = QIcon.fromTheme("go-down", QIcon(":/icons/down-arrow.png")) # Keep if you have resources

        # CSS style for dropdowns to ensure arrows are visible
        self.dropdown_style = """
            QComboBox, ArrowComboBox, QDateEdit {
                background-color: #2d323b;
                color: #f3f3f3;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 6px;
                padding-right: 15px;
                min-height: 20px;
            }
            QComboBox::drop-down, ArrowComboBox::drop-down, QDateEdit::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 12px;
                background: transparent;
                border: none;
            }
            /* Hide the default down arrow for QDateEdit */
            QDateEdit::down-arrow {
                width: 0px;
                height: 0px;
                background: transparent;
            }
        """

        # Store references to the main GUI data needed for dropdowns
        # These will be populated by the main GUI after initialization
        self.accounts_list = [] # List of dicts {id: ..., name: ...}
        self.categories_list = [] # List of dicts {id: ..., name: ..., type: ...}
        self.subcategories_list = [] # List of dicts {id: ..., name: ..., category_id: ...}

    def setEditorDataSources(self, accounts, categories, subcategories):
        """Called by the main GUI to provide data for dropdowns."""
        self.accounts_list = accounts
        self.categories_list = categories
        self.subcategories_list = subcategories

    def createEditor(self, parent: QWidget, option, index: QModelIndex) -> QWidget:
        col = index.column()
        # Ensure parent_window and COLS exist before accessing
        col_key = None
        if self.parent_window and hasattr(self.parent_window, 'COLS') and col < len(self.parent_window.COLS):
             col_key = self.parent_window.COLS[col]
        else:
             print(f"Warning: Cannot determine column key for col {col}. Parent or COLS missing.")
             return super().createEditor(parent, option, index) # Fallback

        # Get current transaction data for context (needed for filtering dropdowns)
        row = index.row()
        current_transaction_data = None
        main_gui = self.parent_window
        # Make sure main_gui exists and has the required lists
        if main_gui and hasattr(main_gui, 'transactions') and hasattr(main_gui, 'pending'):
            num_transactions = len(main_gui.transactions)
            is_pending = row >= num_transactions
            data_source = None
            data_index = -1

            if is_pending:
                 data_source = main_gui.pending
                 data_index = row - num_transactions
            elif 0 <= row < num_transactions:
                 data_source = main_gui.transactions
                 data_index = row

            if data_source is not None and 0 <= data_index < len(data_source):
                 current_transaction_data = data_source[data_index]

        # --- Editor Creation based on Column Key ---
        if col_key == 'transaction_value':
            editor = QLineEdit(parent)
            editor.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter) # Align numbers right
            return editor
        elif col_key == 'transaction_date':
            editor = ArrowDateEdit(parent)
            value = index.model().data(index, Qt.ItemDataRole.EditRole)
            editor.setDisplayFormat("dd MMM yyyy")
            editor.setLocale(self.locale)
            if isinstance(value, str) and len(value) == 10 and value.count('-') == 2:
                date_val = QDate.fromString(value, "yyyy-MM-dd")
                if date_val.isValid():
                    editor.setDate(date_val)
                else:
                    editor.setDate(QDate.currentDate())
            else:
                editor.setDate(QDate.currentDate())
            current_year = QDate.currentDate().year()
            editor.setDateRange(
                QDate(current_year - 10, 1, 1),  # 10 years ago
                QDate(current_year + 10, 12, 31)  # 10 years in the future
            )
            editor.setCalendarPopup(True)
            return editor
        elif col_key == 'account':
            editor = ArrowComboBox(parent)
            editor.setEditable(False)
            for acc in self.accounts_list:
                editor.addItem(acc['name'], userData=acc['id'])
            if editor.count() == 0:
                editor.addItem("No Accounts Available")
                editor.model().item(0).setEnabled(False)
                editor.setEnabled(False)
            QTimer.singleShot(0, editor.showPopup)
            return editor
        elif col_key == 'transaction_type':
            editor = ArrowComboBox(parent)
            editor.setEditable(False)
            editor.addItem('Expense', userData='Expense')
            editor.addItem('Income', userData='Income')
            if current_transaction_data and 'transaction_type' in current_transaction_data:
                current_type = current_transaction_data['transaction_type']
                index = editor.findText(current_type)
                if index >= 0:
                    editor.setCurrentIndex(index)
            QTimer.singleShot(0, editor.showPopup)
            return editor
        elif col_key == 'category':
            editor = ArrowComboBox(parent)
            editor.setEditable(False)
            current_type = 'Expense'
            if current_transaction_data and 'transaction_type' in current_transaction_data:
                 current_type = current_transaction_data['transaction_type']
            has_uncategorized = False
            # CRITICAL FIX: Always ensure UNCATEGORIZED is available for the current transaction type
            # This ensures we always have an UNCATEGORIZED option in the dropdown

            # SPECIAL CASE: Handle the Bank of America vs UNCATEGORIZED conflict
            # Create a modified categories list that ensures UNCATEGORIZED is displayed for ID 1
            modified_categories = []
            for cat in self.categories_list:
                if cat['id'] == 1 and cat['type'] == current_type:
                    # Force name to be UNCATEGORIZED for ID 1
                    modified_cat = cat.copy()
                    modified_cat['name'] = 'UNCATEGORIZED'
                    modified_categories.append(modified_cat)
                    debug_print('CATEGORY', f"DELEGATE EDITOR FIX: Forcing display of UNCATEGORIZED for category_id=1")
                else:
                    modified_categories.append(cat)

            # First, ensure we have an UNCATEGORIZED category for the current transaction type
            uncategorized_exists = False
            for cat in modified_categories:
                if cat['type'] == current_type and cat['name'] == 'UNCATEGORIZED':
                    uncategorized_exists = True
                    break

            # If UNCATEGORIZED doesn't exist for this transaction type, try to create it
            if not uncategorized_exists and self.parent_window and hasattr(self.parent_window, 'db'):
                debug_print('CATEGORY', f"Creating UNCATEGORIZED category for transaction type {current_type}")
                # Try to create the UNCATEGORIZED category
                uncategorized_id = self.parent_window.db.ensure_category('UNCATEGORIZED', current_type)
                if uncategorized_id:
                    # Add to our modified categories list
                    modified_categories.append({
                        'id': uncategorized_id,
                        'name': 'UNCATEGORIZED',
                        'type': current_type
                    })
                    # Also add to our categories list for future use
                    self.categories_list.append({
                        'id': uncategorized_id,
                        'name': 'UNCATEGORIZED',
                        'type': current_type
                    })
                    # Reload dropdown data in the background
                    QTimer.singleShot(0, lambda: self.parent_window._load_dropdown_data())

            # Now add all categories of the current type to the dropdown
            for cat in modified_categories:
                if cat['type'] == current_type:
                    editor.addItem(cat['name'], userData=cat['id'])
                    if cat['name'] == 'UNCATEGORIZED':
                        has_uncategorized = True

            if editor.count() == 0:
                editor.addItem(f"No {current_type} Categories")
                editor.model().item(0).setEnabled(False)
                editor.setEnabled(False)
            editor.setStyleSheet(self.dropdown_style)
            QTimer.singleShot(0, editor.showPopup)
            return editor
        elif col_key == 'sub_category':
            editor = ArrowComboBox(parent)
            editor.setEditable(False)
            current_category_id = None
            if current_transaction_data:
                if 'category_id' in current_transaction_data:
                    current_category_id = current_transaction_data['category_id']
                elif 'transaction_category' in current_transaction_data:
                    current_category_id = current_transaction_data['transaction_category']
                elif 'category' in current_transaction_data and self.parent_window:
                    category_name = current_transaction_data['category']
                    transaction_type = current_transaction_data.get('transaction_type', 'Expense')
                    for cat in self.categories_list:
                        if cat['name'] == category_name and cat['type'] == transaction_type:
                            current_category_id = cat['id']
                            current_transaction_data['category_id'] = cat['id']
                            break
            has_uncategorized = False
            if current_category_id is not None:
                for subcat in self.subcategories_list:
                    if subcat.get('category_id') == current_category_id:
                        editor.addItem(subcat['name'], userData=subcat['id'])
                        if subcat['name'] == 'UNCATEGORIZED':
                            has_uncategorized = True
                if not has_uncategorized and self.parent_window and hasattr(self.parent_window, 'db'):
                    uncategorized_id = self.parent_window.db.ensure_subcategory('UNCATEGORIZED', current_category_id)
                    if uncategorized_id:
                        editor.addItem('UNCATEGORIZED', userData=uncategorized_id)
                        QTimer.singleShot(0, lambda: self.parent_window._load_dropdown_data())
            if editor.count() == 0:
                placeholder = "Select Category First" if current_category_id is None else "No Subcategories"
                editor.addItem(placeholder)
                editor.model().item(0).setEnabled(False)
                editor.setEnabled(False if current_category_id is None else True)
            editor.setStyleSheet(self.dropdown_style)
            QTimer.singleShot(0, editor.showPopup)
            return editor
        elif col_key == 'transaction_name':
            editor = QLineEdit(parent)
            return editor
        elif col_key == 'transaction_description':
            # Create a single-line editor for descriptions
            editor = QLineEdit(parent)
            editor.setStyleSheet("""
                QLineEdit {
                    background-color: #2d323b;
                    color: #f3f3f3;
                    border: 1px solid #444;
                    border-radius: 4px;
                    padding: 6px;
                }
                QLineEdit:focus {
                    border: 1.5px solid #4fc3f7;
                }
            """)
            return editor
        else:
            print(f"No specific editor for column {col} (key: {col_key}), preventing edit.")
            return None

    def eventFilter(self, editor, event):
        if event.type() == event.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if isinstance(editor, QComboBox) and editor.view().isVisible():
                    editor.hidePopup()
                elif isinstance(editor, QDateEdit) and editor.calendarWidget().isVisible():
                    editor.calendarWidget().hide()
                self.commitData.emit(editor)
                self.closeEditor.emit(editor, QStyledItemDelegate.EndEditHint.SubmitModelCache)
                return True
            elif key == Qt.Key.Key_Escape:
                if isinstance(editor, QComboBox) and editor.view().isVisible():
                    editor.hidePopup()
                elif isinstance(editor, QDateEdit) and editor.calendarWidget().isVisible():
                    editor.calendarWidget().hide()
                self.closeEditor.emit(editor, QStyledItemDelegate.EndEditHint.RevertModelCache)
                return True
            elif key == Qt.Key.Key_Tab or key == Qt.Key.Key_Backtab:
                 self.commitData.emit(editor)
                 return False
        elif event.type() == event.Type.FocusOut:
            if isinstance(editor, QDateEdit):
                if editor.calendarWidget() and editor.calendarWidget().isActiveWindow():
                     return False
            elif isinstance(editor, QComboBox):
                 if editor.view() and editor.view().isActiveWindow():
                     return False
            # For QTextEdit, we want to commit data when focus is lost
            self.commitData.emit(editor)
            return False
        return super().eventFilter(editor, event)

    def setEditorData(self, editor: QWidget, index: QModelIndex) -> None:
        value = index.model().data(index, Qt.ItemDataRole.EditRole)
        col = index.column()
        col_key = None
        if self.parent_window and hasattr(self.parent_window, 'COLS') and col < len(self.parent_window.COLS):
             col_key = self.parent_window.COLS[col]
        else:
             print(f"Warning in setEditorData: Cannot determine column key for col {col}.")
             super().setEditorData(editor, index); return
        if isinstance(editor, QComboBox):
            found_idx = -1
            if value is not None:
                 found_idx = editor.findData(value)
            if found_idx != -1:
                editor.setCurrentIndex(found_idx)
            else:
                found_idx = editor.findText(str(value))
                if found_idx != -1:
                     editor.setCurrentIndex(found_idx)
                else:
                     editor.setCurrentIndex(0)
        elif isinstance(editor, QDateEdit) or isinstance(editor, ArrowDateEdit):
            if isinstance(value, str):
                date_val = QDate.fromString(value, "yyyy-MM-dd")
                if date_val.isValid():
                    editor.setDate(date_val)
                else:
                    date_formats = ["dd MMM yyyy", "MM/dd/yyyy", "dd/MM/yyyy"]
                    for fmt in date_formats:
                        date_val = QDate.fromString(value, fmt)
                        if date_val.isValid():
                            editor.setDate(date_val)
                            break
                    else:
                        editor.setDate(QDate.currentDate())
            elif isinstance(value, QDate):
                editor.setDate(value)
            else:
                editor.setDate(QDate.currentDate())
        # QTextEdit handling removed - now using QLineEdit for descriptions
        elif isinstance(editor, QLineEdit):
             if col_key == 'transaction_value':
                 amount_decimal = Decimal('0.00')
                 if isinstance(value, Decimal):
                      amount_decimal = value
                 elif isinstance(value, str):
                      try:
                           cleaned_value = value
                           for symbol in ['$', '€', '£', '¥', '₹', '₽', '₩', '₴', '₦', '₱', '฿', '₫', '₲', '₪', '₡', '₢', '₣', '₤', '₥', '₧', '₨', '₩', '₭', '₮', '₯', '₰', '₱', '₲', '₳', '₴', '₵', '₶', '₷', '₸', '₹', '₺', '₻', '₼', '₽', '₾', '₿']:
                               cleaned_value = cleaned_value.replace(symbol, '')
                           import re
                           cleaned_value = re.sub(r'\b[A-Z]{3}\b', '', cleaned_value)
                           cleaned_value = cleaned_value.strip()
                           cleaned_value = cleaned_value.replace(self.locale.groupSeparator(), '')
                           cleaned_value = cleaned_value.replace(self.locale.decimalPoint(), '.')
                           amount_decimal = Decimal(cleaned_value)
                      except (InvalidOperation, ValueError):
                           print(f"Warning: Could not convert string value '{value}' to Decimal in setEditorData.")
                           amount_decimal = Decimal('0.00')
                 elif value is not None:
                      try:
                           amount_decimal = Decimal(str(value))
                      except InvalidOperation:
                           print(f"Warning: Could not convert value '{value}' to Decimal in setEditorData.")
                           amount_decimal = Decimal('0.00')
                 formatted_amount = self.locale.toString(float(amount_decimal), 'f', 2)
                 editor.setText(formatted_amount)
                 QTimer.singleShot(0, editor.selectAll)
             else:
                 editor.setText(str(value) if value is not None else "")
                 QTimer.singleShot(0, editor.selectAll)
        else:
             super().setEditorData(editor, index)

    def setModelData(self, editor: QWidget, model, index: QModelIndex) -> None:
        col = index.column()
        col_key = None
        if self.parent_window and hasattr(self.parent_window, 'COLS') and col < len(self.parent_window.COLS):
             col_key = self.parent_window.COLS[col]
        else:
             print(f"Error in setModelData: Cannot determine column key for col {col}.")
             return
        row = index.row()
        old_value = model.data(index, Qt.ItemDataRole.EditRole)
        new_value_for_model = None
        new_value_for_command = None
        try:
            if isinstance(editor, QComboBox):
                current_index = editor.currentIndex()
                if current_index >= 0:
                    new_value_for_model = editor.itemData(current_index)
                    display_text = editor.itemText(current_index)

                    # SPECIAL CASE: Handle the Bank of America vs UNCATEGORIZED conflict
                    # If we're in a category column and the display text is UNCATEGORIZED,
                    # make sure we're using the correct category ID
                    if col_key == 'category' and display_text == 'UNCATEGORIZED':
                        # Find the correct UNCATEGORIZED category ID based on transaction type
                        transaction_type = 'Expense'  # Default
                        if self.parent_window:
                            # Try to get the transaction type from the current row
                            row_data = None
                            if row < len(self.parent_window.transactions):
                                row_data = self.parent_window.transactions[row]
                            elif row - len(self.parent_window.transactions) < len(self.parent_window.pending):
                                row_data = self.parent_window.pending[row - len(self.parent_window.transactions)]

                            if row_data and 'transaction_type' in row_data:
                                transaction_type = row_data['transaction_type']

                        # Find the correct UNCATEGORIZED category ID
                        for cat in self.categories_list:
                            if cat['name'] == 'UNCATEGORIZED' and cat['type'] == transaction_type:
                                new_value_for_model = cat['id']
                                debug_print('CATEGORY', f"SET_MODEL_DATA FIX: Setting category_id to {cat['id']} for UNCATEGORIZED")

                                # Update the underlying data structure directly to ensure consistency
                                if self.parent_window:
                                    if row < len(self.parent_window.transactions):
                                        self.parent_window.transactions[row]['category'] = 'UNCATEGORIZED'
                                        self.parent_window.transactions[row]['category_id'] = cat['id']
                                    elif row - len(self.parent_window.transactions) < len(self.parent_window.pending):
                                        pending_idx = row - len(self.parent_window.transactions)
                                        self.parent_window.pending[pending_idx]['category'] = 'UNCATEGORIZED'
                                        self.parent_window.pending[pending_idx]['category_id'] = cat['id']
                                break

                    # SPECIAL CASE: If we're setting category_id to 1, ensure we're setting it for UNCATEGORIZED
                    # This handles the case where the user selects a category that happens to have ID 1
                    elif col_key == 'category' and new_value_for_model == 1:
                        # Force the display text to be UNCATEGORIZED
                        if display_text != 'UNCATEGORIZED':
                            debug_print('CATEGORY', f"SET_MODEL_DATA FIX: Forcing display text to UNCATEGORIZED for category_id=1")
                            # Update the item text directly
                            item = self.parent_window.tbl.item(row, col)
                            if item:
                                item.setText('UNCATEGORIZED')

                            # Update the underlying data structure
                            if self.parent_window:
                                if row < len(self.parent_window.transactions):
                                    self.parent_window.transactions[row]['category'] = 'UNCATEGORIZED'
                                elif row - len(self.parent_window.transactions) < len(self.parent_window.pending):
                                    pending_idx = row - len(self.parent_window.transactions)
                                    self.parent_window.pending[pending_idx]['category'] = 'UNCATEGORIZED'

                    if new_value_for_model == "" and display_text == "":
                         new_value_for_model = None
                    new_value_for_command = new_value_for_model
            elif isinstance(editor, QDateEdit):
                new_value_for_model = editor.date().toString("yyyy-MM-dd")
                new_value_for_command = new_value_for_model
            # QTextEdit handling removed - now using QLineEdit for descriptions
            elif isinstance(editor, QLineEdit):
                text = editor.text()
                if col_key == 'transaction_value':
                    try:
                        cleaned_text = text.replace(self.locale.groupSeparator(),'').replace(self.locale.currencySymbol(),'').replace(self.locale.decimalPoint(),'.')
                        import re
                        cleaned_text = re.sub(r'\s[A-Z]{3}$', '', cleaned_text).strip()
                        new_value_for_model = Decimal(cleaned_text)
                        new_value_for_command = new_value_for_model
                    except InvalidOperation:
                        print(f"Warning: Invalid decimal format '{text}' for {col_key}. Reverting.")
                        self.closeEditor.emit(editor, QStyledItemDelegate.EndEditHint.RevertModelCache)
                        return
                else:
                    new_value_for_model = text
                    new_value_for_command = new_value_for_model
            else:
                print(f"Warning: Unsupported editor type {type(editor)} in setModelData.")
                return
            changed = False
            if isinstance(new_value_for_model, Decimal) and isinstance(old_value, Decimal):
                 changed = (new_value_for_model != old_value)
            elif str(new_value_for_model) != str(old_value):
                 changed = True
            if changed:
                model.setData(index, new_value_for_model, Qt.ItemDataRole.EditRole)
                if self.parent_window and hasattr(self.parent_window, 'undo_stack'):
                    command = CellEditCommand(self.parent_window, row, col, old_value, new_value_for_command)
                    self.parent_window.undo_stack.push(command)
                else:
                    print("Warning: Could not create undo command (parent window or undo stack missing).")
        except Exception as e:
             print(f"Error in setModelData for row {row}, col {col} (key: {col_key}): {e}")
             self.closeEditor.emit(editor, QStyledItemDelegate.EndEditHint.RevertModelCache)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        col = index.column()
        col_key = None
        if self.parent_window and hasattr(self.parent_window, 'COLS') and col < len(self.parent_window.COLS):
            col_key = self.parent_window.COLS[col]
        if col_key in ['account', 'transaction_type', 'category', 'sub_category', 'transaction_date']:
            from PyQt6.QtGui import QColor, QPen, QPolygon, QBrush
            from PyQt6.QtCore import QPoint, QRect
            painter.save()
            rect = option.rect
            arrow_width = 20
            arrow_rect = QRect(rect.right() - arrow_width, rect.top(), arrow_width, rect.height())
            if not hasattr(self, 'arrow_rects'):
                self.arrow_rects = {}
            if col_key == 'transaction_date':
                date_arrow_width = 30
                date_arrow_rect = QRect(rect.right() - date_arrow_width, rect.top(), date_arrow_width, rect.height())
                self.arrow_rects[(index.row(), index.column())] = date_arrow_rect
            else:
                self.arrow_rects[(index.row(), index.column())] = arrow_rect
            is_editing = False
            if self.parent_window and hasattr(self.parent_window, 'tbl'):
                current_index = self.parent_window.tbl.currentIndex()
                if current_index.isValid() and current_index.row() == index.row() and current_index.column() == index.column():
                    editor = self.parent_window.tbl.indexWidget(current_index)
                    is_editing = editor is not None
            if not is_editing:
                if col_key == 'transaction_date':
                    painter.setPen(QPen(QColor(150, 150, 150)))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    center_x = int(rect.right() - (arrow_width / 2))
                    center_y = rect.center().y()
                    icon_size = 4
                    calendar_rect = QRect(
                        center_x - icon_size,
                        center_y - icon_size,
                        icon_size * 2,
                        icon_size * 2
                    )
                    painter.drawRect(calendar_rect)
                    header_y = center_y - icon_size + 1
                    painter.drawLine(
                        center_x - icon_size,
                        header_y,
                        center_x + icon_size,
                        header_y
                    )
                else:
                    painter.setPen(QPen(QColor(150, 150, 150)))
                    painter.setBrush(QBrush(QColor(150, 150, 150)))
                    painter.setBrush(QBrush(QColor(150, 150, 150)))
                    arrow_size = 3
                    center_x = int(rect.right() - (arrow_width / 2))
                    center_y = rect.center().y()
                    arrow = QPolygon([
                        QPoint(center_x - arrow_size, int(center_y - arrow_size/2)),
                        QPoint(center_x + arrow_size, int(center_y - arrow_size/2)),
                        QPoint(center_x, center_y + arrow_size)
                    ])
                    painter.drawPolygon(arrow)
            painter.restore()

    def displayText(self, value, locale) -> str:
        # Basic type formatting only. Currency/context-specific formatting
        # is handled by main_window.py setting the item text directly.

        if isinstance(value, Decimal):
            # Use default locale formatting for decimals here
            try:
                # Determine decimals based on column config if possible, default to 2
                decimals = 2
                # We need the column key, but displayText doesn't get the index.
                # This part is problematic without the index.
                # For simplicity, always use 2 decimals here.
                # More specific formatting is done in main_window.py.
                formatted_value = self.locale.toString(float(value), 'f', decimals)
                return formatted_value
            except Exception as e:
                print(f"Error formatting decimal value in displayText: {e}")
                return "Error" # Fallback display

        if isinstance(value, str) and len(value) == 10 and value.count('-') == 2:
            # Format dates consistently
            try:
                date = QDate.fromString(value, "yyyy-MM-dd")
                if date.isValid():
                    return date.toString("dd MMM yyyy")
            except Exception:
                pass # Ignore formatting errors, return original string

        # Handle ID lookups for display (Account, Category, SubCategory)
        if isinstance(value, int) and self.parent_window:
            # This requires knowing which column we are displaying.
            # This logic is complex without the index.
            # It's better handled by main_window setting the display text.
            # Return a generic ID representation here as a fallback.
            # The main window should override this with the correct name.
            # Check if it's likely an ID based on known dropdown data
            is_account_id = any(acc['id'] == value for acc in self.accounts_list)
            is_category_id = any(cat['id'] == value for cat in self.categories_list)
            is_subcategory_id = any(subcat['id'] == value for subcat in self.subcategories_list)

            if is_account_id:
                 name = self._find_name_for_id('account', value)
                 return name if name else f"AccID:{value}"
            if is_category_id:
                 # SPECIAL CASE: Handle ID conflicts using the parent window's mapping
                 if self.parent_window and hasattr(self.parent_window, '_id_conflict_mapping'):
                     if 'category' in self.parent_window._id_conflict_mapping and value in self.parent_window._id_conflict_mapping['category']:
                         forced_name = self.parent_window._id_conflict_mapping['category'][value]
                         debug_print('CATEGORY', f"DELEGATE FIX: Forcing display of {forced_name} for category_id={value}")
                         return forced_name

                 # Fallback for backward compatibility
                 if value == 1:
                     debug_print('CATEGORY', f"DELEGATE FIX: Forcing display of UNCATEGORIZED for category_id=1")
                     return 'UNCATEGORIZED'

                 name = self._find_name_for_id('category', value)
                 return name if name else f"CatID:{value}"
            if is_subcategory_id:
                 name = self._find_name_for_id('sub_category', value)
                 return name if name else f"SubCatID:{value}"
            # If it's an int but not a known ID, display it as such
            # return f"ID:{value}" # Or just the string value?

        # Default: return string representation
        return str(value) if value is not None else ""

    def _find_name_for_id(self, field_type, item_id, context=None):
        """Helper to find name for ID within the delegate."""
        if item_id is None: return ""
        try:
            # SPECIAL CASE: Handle ID conflicts using the parent window's mapping
            if field_type == 'category' and self.parent_window and hasattr(self.parent_window, '_id_conflict_mapping'):
                if 'category' in self.parent_window._id_conflict_mapping and item_id in self.parent_window._id_conflict_mapping['category']:
                    forced_name = self.parent_window._id_conflict_mapping['category'][item_id]
                    debug_print('CATEGORY', f"FIND_NAME_FOR_ID FIX: Forcing display of {forced_name} for category_id={item_id}")
                    return forced_name

            # Fallback for backward compatibility
            if field_type == 'category' and item_id == 1:
                debug_print('CATEGORY', f"FIND_NAME_FOR_ID FIX: Forcing display of UNCATEGORIZED for category_id=1")
                return 'UNCATEGORIZED'

            if field_type == 'account':
                return next((acc['name'] for acc in self.accounts_list if acc['id'] == item_id), "")
            elif field_type == 'category':
                # Category name doesn't depend on type context for display lookup
                return next((cat['name'] for cat in self.categories_list if cat['id'] == item_id), "")
            elif field_type == 'sub_category':
                # SubCategory name doesn't depend on category context for display lookup
                return next((subcat['name'] for subcat in self.subcategories_list if subcat['id'] == item_id), "")
        except Exception as e:
            print(f"Error finding name for {field_type} ID {item_id}: {e}")
        return ""

# --- END OF FILE delegates.py ---