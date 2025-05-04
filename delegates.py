# --- START OF FILE delegates.py ---

from PyQt6.QtWidgets import (QStyledItemDelegate, QWidget, QComboBox,
                             QDateEdit, QLineEdit, QStyleOptionComboBox,
                             QStyle, QApplication)
from PyQt6.QtCore import Qt, QModelIndex, QDate, QLocale, QTimer
from PyQt6.QtGui import QColor, QIcon, QDoubleValidator # QDoubleValidator might not be flexible enough for locale
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from commands import CellEditCommand

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
        # No print needed here generally, unless debugging setup
        # print(f"Delegate received {len(accounts)} accounts, {len(categories)} categories, {len(subcategories)} subcategories.")

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
            # else: No data found for this row index, dropdowns might be empty/unfiltered

        # --- Editor Creation based on Column Key ---
        if col_key == 'transaction_value':
            editor = QLineEdit(parent)
            # Using QLineEdit allows more flexible input, validation happens on commit
            # A QDoubleValidator isn't flexible enough for different locale formats easily.
            editor.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter) # Align numbers right
            return editor
        elif col_key == 'transaction_date':
            editor = QDateEdit(parent, calendarPopup=True)
            editor.setDisplayFormat("yyyy-MM-dd") # Store in ISO format
            # Set locale for calendar widget appearance if desired
            editor.setLocale(self.locale)
            editor.setDate(QDate.currentDate()) # Default to today
            return editor
        elif col_key == 'account':
            editor = QComboBox(parent)
            editor.setEditable(False)
            # Don't add empty item, just populate with accounts
            for acc in self.accounts_list:
                editor.addItem(acc['name'], userData=acc['id'])
            if editor.count() == 0:
                editor.addItem("No Accounts Available")
                editor.model().item(0).setEnabled(False) # Disable the message item
                editor.setEnabled(False)
            return editor
        elif col_key == 'transaction_type':
            editor = QComboBox(parent)
            editor.setEditable(False)
            editor.addItem('Expense', userData='Expense')
            editor.addItem('Income', userData='Income')

            # Set current value if available
            if current_transaction_data and 'transaction_type' in current_transaction_data:
                current_type = current_transaction_data['transaction_type']
                index = editor.findText(current_type)
                if index >= 0:
                    editor.setCurrentIndex(index)

            return editor

        elif col_key == 'category':
            editor = QComboBox(parent)
            editor.setEditable(False)
            # Filter categories based on the current row's transaction type
            current_type = 'Expense' # Default assumption

            # Debug print to see what data we have for this row
            print(f"Category dropdown - Transaction data keys: {current_transaction_data.keys() if current_transaction_data else 'None'}")

            # Check if this is a bank account mistakenly set as a category
            if current_transaction_data and 'account' in current_transaction_data:
                account_name = current_transaction_data.get('account')
                for acc in self.accounts_list:
                    if acc['name'] == account_name and 'category' in current_transaction_data and current_transaction_data['category'] == account_name:
                        # This is a bank account mistakenly set as a category
                        print(f"WARNING: Bank account '{account_name}' found in category field. Will be fixed on refresh.")
                        # The fix will happen in _refresh method

            if current_transaction_data and 'transaction_type' in current_transaction_data:
                 current_type = current_transaction_data['transaction_type']

            print(f"Category dropdown - Using transaction type: {current_type}")

            # Don't add empty item, just populate with categories
            has_uncategorized = False
            for cat in self.categories_list:
                 if cat['type'] == current_type:
                      print(f"  Adding category: {cat['name']} (ID: {cat['id']}, Type: {cat['type']})")
                      editor.addItem(cat['name'], userData=cat['id'])
                      if cat['name'] == 'UNCATEGORIZED':
                          has_uncategorized = True

            if editor.count() == 0:
                editor.addItem(f"No {current_type} Categories")
                editor.model().item(0).setEnabled(False)
                editor.setEnabled(False)
            return editor
        elif col_key == 'sub_category':
            editor = QComboBox(parent)
            editor.setEditable(False)
            # Filter subcategories based on the current row's category ID
            current_category_id = None

            # Check for category ID in different possible fields
            if current_transaction_data:
                if 'category_id' in current_transaction_data:
                    current_category_id = current_transaction_data['category_id']
                elif 'transaction_category' in current_transaction_data:
                    current_category_id = current_transaction_data['transaction_category']
                # If we have a category name but no ID, try to find the ID
                elif 'category' in current_transaction_data and self.parent_window:
                    category_name = current_transaction_data['category']
                    transaction_type = current_transaction_data.get('transaction_type', 'Expense')

                    # Find the category ID by name and type
                    for cat in self.categories_list:
                        if cat['name'] == category_name and cat['type'] == transaction_type:
                            current_category_id = cat['id']
                            # Update the transaction data with the category ID
                            current_transaction_data['category_id'] = cat['id']
                            break

                    # If we couldn't find the category, check if it's a bank account mistakenly set as category
                    if current_category_id is None and 'account' in current_transaction_data:
                        account_name = current_transaction_data.get('account')
                        if account_name == category_name:
                            # This is a bank account mistakenly set as category
                            # Find UNCATEGORIZED category for the current transaction type
                            transaction_type = current_transaction_data.get('transaction_type', 'Expense')
                            for cat in self.categories_list:
                                if cat['name'] == 'UNCATEGORIZED' and cat['type'] == transaction_type:
                                    current_category_id = cat['id']
                                    # Update the transaction data
                                    current_transaction_data['category'] = 'UNCATEGORIZED'
                                    current_transaction_data['category_id'] = cat['id']
                                    break

            # Debug print to help diagnose issues
            print(f"Subcategory dropdown - Current category ID: {current_category_id}")
            print(f"Transaction data keys: {current_transaction_data.keys() if current_transaction_data else 'None'}")

            # Check if the category is UNCATEGORIZED
            category_is_uncategorized = False
            if current_category_id is not None:
                for cat in self.categories_list:
                    if cat['id'] == current_category_id and cat['name'] == 'UNCATEGORIZED':
                        category_is_uncategorized = True
                        break

            has_uncategorized = False
            if current_category_id is not None:
                # Don't add empty item, just populate with subcategories
                for subcat in self.subcategories_list:
                    # Ensure category_id types match for comparison (e.g., both int)
                    if subcat.get('category_id') == current_category_id:
                        print(f"  Adding subcategory: {subcat['name']} (ID: {subcat['id']}, Category ID: {subcat['category_id']})")
                        editor.addItem(subcat['name'], userData=subcat['id'])
                        if subcat['name'] == 'UNCATEGORIZED':
                            has_uncategorized = True
                            # If category is UNCATEGORIZED, select UNCATEGORIZED subcategory by default
                            if category_is_uncategorized:
                                editor.setCurrentIndex(editor.count() - 1)

                # If no UNCATEGORIZED subcategory exists for this category, create one
                if not has_uncategorized and self.parent_window and hasattr(self.parent_window, 'db'):
                    print(f"Creating UNCATEGORIZED subcategory for category ID {current_category_id}")
                    uncategorized_id = self.parent_window.db.ensure_subcategory('UNCATEGORIZED', current_category_id)
                    if uncategorized_id:
                        editor.addItem('UNCATEGORIZED', userData=uncategorized_id)
                        # Reload dropdown data in the background
                        QTimer.singleShot(0, lambda: self.parent_window._load_dropdown_data())

            if editor.count() == 0:
                # Provide a more informative placeholder if category isn't selected yet
                placeholder = "Select Category First" if current_category_id is None else "No Subcategories"
                editor.addItem(placeholder)
                editor.model().item(0).setEnabled(False)
                editor.setEnabled(False if current_category_id is None else True) # Enable if category is selected but no subcats exist

            return editor
        elif col_key in ['transaction_name', 'transaction_description']:
            # Default editor (QLineEdit) is fine for text fields
            return super().createEditor(parent, option, index)
        else:
            # For columns like 'transaction_type' which shouldn't be edited directly
            # Or return default editor if col_key is None/unhandled
            print(f"No specific editor for column {col} (key: {col_key}), preventing edit.")
            # Returning None prevents editing for this cell
            return None
            # Or return default LineEdit:
            # return super().createEditor(parent, option, index)

    # --- eventFilter remains largely the same ---
    # It correctly handles commit/revert triggers.
    def eventFilter(self, editor, event):
        if event.type() == event.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if isinstance(editor, QComboBox) and editor.view().isVisible():
                    editor.hidePopup()
                elif isinstance(editor, QDateEdit) and editor.calendarWidget().isVisible():
                    editor.calendarWidget().hide() # Hide calendar on Enter

                # Commit data and close editor after handling popup
                # Use CommitModelCache which hints to the view to update caches
                self.commitData.emit(editor)
                self.closeEditor.emit(editor, QStyledItemDelegate.EndEditHint.SubmitModelCache)
                return True # Event handled

            elif key == Qt.Key.Key_Escape:
                if isinstance(editor, QComboBox) and editor.view().isVisible():
                    editor.hidePopup()
                elif isinstance(editor, QDateEdit) and editor.calendarWidget().isVisible():
                    editor.calendarWidget().hide()

                self.closeEditor.emit(editor, QStyledItemDelegate.EndEditHint.RevertModelCache)
                return True # Event handled

            elif key == Qt.Key.Key_Tab or key == Qt.Key.Key_Backtab:
                 # Commit on Tab/Backtab press, then let default handling move focus
                 self.commitData.emit(editor)
                 # Return False to allow default Tab/Backtab focus traversal
                 return False

        elif event.type() == event.Type.FocusOut:
             # Check if focus is moving *within* the editor complex widget itself
             # (e.g., clicking the calendar button in QDateEdit)
            if isinstance(editor, QDateEdit):
                # If the calendar popup is becoming active, don't commit yet
                if editor.calendarWidget() and editor.calendarWidget().isActiveWindow():
                     return False # Don't commit yet
            elif isinstance(editor, QComboBox):
                 # If the dropdown view is becoming active, don't commit yet
                 if editor.view() and editor.view().isActiveWindow():
                     return False # Don't commit yet

            # Otherwise, commit data when the editor truly loses focus
            self.commitData.emit(editor)
            # Let the default handler process the focus out event
            # No need to explicitly close editor here, commit handles it? Let's test this.
            return False # Let the event propagate

        # Fallback to default event processing
        return super().eventFilter(editor, event)

    def setEditorData(self, editor: QWidget, index: QModelIndex) -> None:
        # Get the raw data value using EditRole (should be Decimal for amount, str for others)
        value = index.model().data(index, Qt.ItemDataRole.EditRole)
        col = index.column()
        # Ensure parent_window and COLS exist before accessing
        col_key = None
        if self.parent_window and hasattr(self.parent_window, 'COLS') and col < len(self.parent_window.COLS):
             col_key = self.parent_window.COLS[col]
        else:
             print(f"Warning in setEditorData: Cannot determine column key for col {col}.")
             super().setEditorData(editor, index); return # Fallback

        # print(f"DEBUG setEditorData - Row: {index.row()}, Col: {col}, Key: {col_key}, Value: {value} (Type: {type(value)})")

        if isinstance(editor, QComboBox):
            # Combo boxes store ID in userData. The 'value' from the model here
            # *should* ideally be the ID for account/category/subcategory if the model stores it correctly.
            # However, the current model/gui seems to pass the *name* string via EditRole sometimes.
            # Let's try finding by userData (ID) first, then by text as fallback.
            found_idx = -1
            if value is not None: # Attempt to find by ID first
                 found_idx = editor.findData(value) # value should be the ID here

            if found_idx != -1:
                editor.setCurrentIndex(found_idx)
            else:
                # Fallback: If ID match failed or value wasn't an ID, try finding by text
                found_idx = editor.findText(str(value))
                if found_idx != -1:
                     editor.setCurrentIndex(found_idx)
                else:
                     # Value not found by ID or Text, select the first item (often the empty one)
                     editor.setCurrentIndex(0)
                     # print(f"Warning: Value '{value}' not found in ComboBox for {col_key}. Setting to index 0.")

        elif isinstance(editor, QDateEdit):
            if isinstance(value, str):
                date_val = QDate.fromString(value, "yyyy-MM-dd")
                if date_val.isValid():
                    editor.setDate(date_val)
                else:
                    editor.setDate(QDate.currentDate()) # Fallback
            elif isinstance(value, QDate):
                editor.setDate(value) # If model stores QDate directly
            else:
                editor.setDate(QDate.currentDate()) # Fallback

        elif isinstance(editor, QLineEdit):
             if col_key == 'transaction_value':
                 # value should be a Decimal from the model's EditRole
                 amount_decimal = Decimal('0.00') # Default
                 if isinstance(value, Decimal):
                      amount_decimal = value
                 elif value is not None: # Try converting if not Decimal (e.g., float, str)
                      try:
                           amount_decimal = Decimal(str(value))
                      except InvalidOperation:
                           print(f"Warning: Could not convert value '{value}' to Decimal in setEditorData.")
                           amount_decimal = Decimal('0.00')

                 # Format the Decimal amount according to locale for display *in the editor*
                 # Use 'f' format, 2 decimal places. Convert to float for locale.toString compatibility.
                 formatted_amount = self.locale.toString(float(amount_decimal), 'f', 2)
                 editor.setText(formatted_amount)
                 # Select text after setting it
                 QTimer.singleShot(0, editor.selectAll)
             else: # Name, Description
                 editor.setText(str(value) if value is not None else "")
                 QTimer.singleShot(0, editor.selectAll)
        else:
             # Fallback for any other editor types
             super().setEditorData(editor, index)

    def setModelData(self, editor: QWidget, model, index: QModelIndex) -> None:
        # Ensure parent_window and COLS exist before accessing
        col = index.column()
        col_key = None
        if self.parent_window and hasattr(self.parent_window, 'COLS') and col < len(self.parent_window.COLS):
             col_key = self.parent_window.COLS[col]
        else:
             print(f"Error in setModelData: Cannot determine column key for col {col}.")
             # Cannot proceed without col_key
             return

        row = index.row()

        # --- Get OLD value BEFORE model is updated ---
        # Use EditRole to get the underlying data (should be Decimal for amount, str/int for others)
        old_value = model.data(index, Qt.ItemDataRole.EditRole)
        # We'll compare the actual values later, after determining the new value type.

        new_value_for_model = None # Value to store in model (using EditRole)
        new_value_for_command = None # Value to pass to the command (might be same or different)

        try:
            if isinstance(editor, QComboBox):
                # For dropdowns, we want to store the ID in the model (EditRole)
                # and pass the ID to the command.
                current_index = editor.currentIndex()
                if current_index >= 0: # Ensure a valid item is selected
                    new_value_for_model = editor.itemData(current_index) # Get ID from userData
                    display_text = editor.itemText(current_index)

                    # Handle the case where the empty item ("") is selected, store None
                    if new_value_for_model == "" and display_text == "":
                         new_value_for_model = None

                    new_value_for_command = new_value_for_model # Pass ID to command

                    # Special handling for transaction type changes
                    if col_key == 'transaction_type':
                        # When transaction type changes, we need to update the category to UNCATEGORIZED for the new type
                        # Find the category and subcategory column indices
                        category_col = self.parent_window.COLS.index('category')
                        subcategory_col = self.parent_window.COLS.index('sub_category')

                        # Find UNCATEGORIZED category for the new transaction type
                        uncategorized_cat = None
                        for cat in self.categories_list:
                            if cat['name'] == 'UNCATEGORIZED' and cat['type'] == display_text:
                                uncategorized_cat = cat
                                break

                        if uncategorized_cat:
                            # Find UNCATEGORIZED subcategory for this category
                            uncategorized_subcat = None
                            for subcat in self.subcategories_list:
                                if subcat['category_id'] == uncategorized_cat['id'] and subcat['name'] == 'UNCATEGORIZED':
                                    uncategorized_subcat = subcat
                                    break

                            # Update the model with the new category and subcategory
                            if uncategorized_subcat:
                                # Schedule the updates to happen after this method completes
                                QTimer.singleShot(0, lambda: model.setData(model.index(row, category_col), 'UNCATEGORIZED'))
                                QTimer.singleShot(0, lambda: model.setData(model.index(row, subcategory_col), 'UNCATEGORIZED'))

                                # Also update the command's target_data_dict directly
                                if hasattr(self.parent_window, 'undo_stack'):
                                    # Get the most recent command
                                    command = self.parent_window.undo_stack.command(self.parent_window.undo_stack.count() - 1)
                                    if hasattr(command, 'target_data_dict'):
                                        command.target_data_dict['category'] = 'UNCATEGORIZED'
                                        command.target_data_dict['category_id'] = uncategorized_cat['id']
                                        command.target_data_dict['sub_category'] = 'UNCATEGORIZED'
                                        command.target_data_dict['sub_category_id'] = uncategorized_subcat['id']

                                print(f"Transaction type changed to {display_text}, setting category and subcategory to UNCATEGORIZED")

                    # Special handling for category selection
                    elif col_key == 'category':
                        # Debug print for all category selections
                        print(f"DEBUG CATEGORY SELECTION: Row {row}, Selected='{display_text}', ID={new_value_for_model}")

                        # Find the subcategory column index (needed for all category selections)
                        subcategory_col = self.parent_window.COLS.index('sub_category')

                        # Get the transaction type to find the correct UNCATEGORIZED category
                        transaction_type = 'Expense'  # Default
                        transaction_data = None

                        # Get the current transaction data to determine the transaction type
                        if row < len(self.parent_window.transactions):
                            transaction_data = self.parent_window.transactions[row]
                        elif row - len(self.parent_window.transactions) < len(self.parent_window.pending):
                            transaction_data = self.parent_window.pending[row - len(self.parent_window.transactions)]

                        if transaction_data and 'transaction_type' in transaction_data:
                            transaction_type = transaction_data['transaction_type']

                        # Only verify if the selected category is UNCATEGORIZED
                        if display_text == 'UNCATEGORIZED':
                            # Verify we have the correct UNCATEGORIZED category for this transaction type
                            correct_category_id = None
                            for cat in self.categories_list:
                                if cat['name'] == 'UNCATEGORIZED' and cat['type'] == transaction_type:
                                    correct_category_id = cat['id']
                                    # If the selected category ID doesn't match the correct one, update it
                                    if new_value_for_model != correct_category_id:
                                        new_value_for_model = correct_category_id
                                    break

                        # Directly update the underlying data in the transaction or pending list
                        if transaction_data:
                            # Get the selected category name
                            selected_category_name = display_text
                            transaction_data['category'] = selected_category_name
                            transaction_data['category_id'] = new_value_for_model

                            # Update the model with the correct category ID and name
                            model.setData(index, new_value_for_model, Qt.ItemDataRole.EditRole)
                            model.setData(index, selected_category_name, Qt.ItemDataRole.DisplayRole)

                        # Only set subcategory to UNCATEGORIZED if the selected category is UNCATEGORIZED
                        if display_text == 'UNCATEGORIZED':
                            # Find UNCATEGORIZED subcategory for this category
                            uncat_subcat_id = None
                            for subcat in self.subcategories_list:
                                if subcat['category_id'] == new_value_for_model and subcat['name'] == 'UNCATEGORIZED':
                                    uncat_subcat_id = subcat['id']
                                    break

                            # If not found, try to create it
                            if uncat_subcat_id is None and self.parent_window and hasattr(self.parent_window, 'db'):
                                print(f"Creating UNCATEGORIZED subcategory for category ID {new_value_for_model}")
                                uncat_subcat_id = self.parent_window.db.ensure_subcategory('UNCATEGORIZED', new_value_for_model)
                                if uncat_subcat_id:
                                    # Add to subcategories list
                                    self.subcategories_list.append({
                                        'id': uncat_subcat_id,
                                        'name': 'UNCATEGORIZED',
                                        'category_id': new_value_for_model
                                    })
                                    # Reload dropdown data in the background
                                    QTimer.singleShot(0, lambda: self.parent_window._load_dropdown_data())

                            # If found, update the subcategory in the model and underlying data
                            if uncat_subcat_id is not None and transaction_data:
                                # Update the underlying data
                                transaction_data['sub_category'] = 'UNCATEGORIZED'
                                transaction_data['sub_category_id'] = uncat_subcat_id

                                # Update the model with the subcategory ID and name
                                model.setData(model.index(row, subcategory_col), uncat_subcat_id, Qt.ItemDataRole.EditRole)
                                model.setData(model.index(row, subcategory_col), 'UNCATEGORIZED', Qt.ItemDataRole.DisplayRole)

                                # Also update the command's target_data_dict directly
                                if hasattr(self.parent_window, 'undo_stack'):
                                    # Get the most recent command
                                    command = self.parent_window.undo_stack.command(self.parent_window.undo_stack.count() - 1)
                                    if hasattr(command, 'target_data_dict'):
                                        command.target_data_dict['category_id'] = new_value_for_model
                                        command.target_data_dict['category'] = 'UNCATEGORIZED'
                                        command.target_data_dict['sub_category'] = 'UNCATEGORIZED'
                                        command.target_data_dict['sub_category_id'] = uncat_subcat_id

                                print(f"Category is UNCATEGORIZED, setting subcategory to UNCATEGORIZED (ID: {uncat_subcat_id})")

                    # Special handling for subcategory selection
                    elif col_key == 'sub_category':
                        # Debug print for subcategory selection
                        print(f"DEBUG SUBCATEGORY SELECTION: Row {row}, Selected='{display_text}', ID={new_value_for_model}")

                        # Get the current transaction data
                        transaction_data = None
                        if row < len(self.parent_window.transactions):
                            transaction_data = self.parent_window.transactions[row]
                        elif row - len(self.parent_window.transactions) < len(self.parent_window.pending):
                            transaction_data = self.parent_window.pending[row - len(self.parent_window.transactions)]

                        # Get the current category ID
                        category_id = None
                        if transaction_data:
                            category_id = transaction_data.get('category_id')
                            print(f"DEBUG SUBCATEGORY: Category ID for this row is {category_id}")

                        # Verify the subcategory belongs to the current category
                        found = False
                        for subcat in self.subcategories_list:
                            if subcat['id'] == new_value_for_model:
                                if subcat['category_id'] == category_id:
                                    found = True
                                    print(f"DEBUG SUBCATEGORY: Verified subcategory ID {new_value_for_model} belongs to category {category_id}")
                                else:
                                    print(f"WARNING: Subcategory ID {new_value_for_model} belongs to category {subcat['category_id']}, not {category_id}")
                                    # If the subcategory doesn't belong to the current category, find the UNCATEGORIZED subcategory
                                    if category_id is not None:
                                        for uncat_subcat in self.subcategories_list:
                                            if uncat_subcat['category_id'] == category_id and uncat_subcat['name'] == 'UNCATEGORIZED':
                                                new_value_for_model = uncat_subcat['id']
                                                print(f"DEBUG SUBCATEGORY: Using UNCATEGORIZED subcategory ID {new_value_for_model} instead")
                                                found = True
                                                break
                                break

                        # If we couldn't find a valid subcategory, try to create an UNCATEGORIZED one
                        if not found and category_id is not None:
                            print(f"WARNING: Could not find valid subcategory for category ID {category_id}, creating UNCATEGORIZED")
                            uncat_subcat_id = None
                            for subcat in self.subcategories_list:
                                if subcat['category_id'] == category_id and subcat['name'] == 'UNCATEGORIZED':
                                    uncat_subcat_id = subcat['id']
                                    break

                            if uncat_subcat_id is None and self.parent_window and hasattr(self.parent_window, 'db'):
                                print(f"Creating UNCATEGORIZED subcategory for category ID {category_id}")
                                uncat_subcat_id = self.parent_window.db.ensure_subcategory('UNCATEGORIZED', category_id)
                                if uncat_subcat_id:
                                    # Add to subcategories list
                                    self.subcategories_list.append({
                                        'id': uncat_subcat_id,
                                        'name': 'UNCATEGORIZED',
                                        'category_id': category_id
                                    })
                                    # Use this as the new value
                                    new_value_for_model = uncat_subcat_id
                                    # Reload dropdown data in the background
                                    QTimer.singleShot(0, lambda: self.parent_window._load_dropdown_data())

                        # Update the underlying data
                        if transaction_data and new_value_for_model is not None:
                            # Find the subcategory name
                            subcat_name = 'UNCATEGORIZED'  # Default
                            for subcat in self.subcategories_list:
                                if subcat['id'] == new_value_for_model:
                                    subcat_name = subcat['name']
                                    break

                            transaction_data['sub_category'] = subcat_name
                            transaction_data['sub_category_id'] = new_value_for_model
                            print(f"DEBUG SUBCATEGORY: Updated transaction data with subcategory '{subcat_name}' (ID: {new_value_for_model})")

                            # Update the model with both the ID and display text
                            model.setData(index, new_value_for_model, Qt.ItemDataRole.EditRole)
                            model.setData(index, subcat_name, Qt.ItemDataRole.DisplayRole)
                else:
                     # No item selected or invalid index, revert? Or store None? Let's store None.
                     new_value_for_model = None
                     new_value_for_command = None
                # Ensure old_value is also an ID for comparison if it came from a dropdown
                # This requires the model to consistently provide the ID via EditRole
                # Let's assume old_value could be name or ID, try comparison carefully later

            elif isinstance(editor, QDateEdit):
                # Store date as ISO string "yyyy-MM-dd"
                new_value_for_model = editor.date().toString("yyyy-MM-dd")
                new_value_for_command = new_value_for_model # Pass string to command
                # old_value should already be a string in the same format

            elif isinstance(editor, QLineEdit):
                text = editor.text()
                if col_key == 'transaction_value':
                    try:
                        # Use locale-aware conversion from string to Decimal
                        # Remove group separators, then replace locale decimal point with '.'
                        cleaned_text = text.replace(self.locale.groupSeparator(), '')
                        cleaned_text = cleaned_text.replace(self.locale.decimalPoint(), '.')
                        # Also remove currency symbol if present
                        cleaned_text = cleaned_text.replace(self.locale.currencySymbol(), '').strip()

                        amount_decimal = Decimal(cleaned_text)
                        # Optional: Quantize to 2 decimal places upon commit
                        amount_decimal = amount_decimal.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)

                        new_value_for_model = amount_decimal # Store Decimal in model
                        new_value_for_command = amount_decimal # Store Decimal in command
                        # old_value should already be a Decimal

                    except (InvalidOperation, ValueError):
                        print(f"Warning: Invalid amount input '{text}', reverting.")
                        # Don't change the model data if input is invalid
                        # We can emit closeEditor to signal reversion? Or just return.
                        self.closeEditor.emit(editor, QStyledItemDelegate.EndEditHint.RevertModelCache)
                        return # Exit without setting model data or pushing command

                else: # Name, Description
                    new_value_for_model = text
                    new_value_for_command = new_value_for_model # Store string
                    # old_value should already be a string

            else:
                # Fallback for other potential editors (unlikely with current setup)
                # Use superclass method which likely handles basic types.
                # Note: We need to get the value from the editor *before* calling super.setModelData
                # This part is tricky, might need specific handling if other editors are used.
                # For now, assume only the above editors are used.
                print(f"Warning: Unsupported editor type {type(editor)} in setModelData.")
                return # Exit

            # --- Compare and Update ---
            # Compare potentially different types carefully.
            changed = False
            if isinstance(new_value_for_model, Decimal) and isinstance(old_value, Decimal):
                 changed = (new_value_for_model != old_value)
            # Add specific comparisons for other types if necessary (e.g., int IDs)
            # General comparison using string representation as a fallback
            elif str(new_value_for_model) != str(old_value):
                 changed = True

            if changed:
                # Set the raw data (Decimal, string, int ID) in the model via EditRole
                model.setData(index, new_value_for_model, Qt.ItemDataRole.EditRole)

                # Create command with appropriate old/new values for the command's logic
                # Ensure old_value type passed to command matches new_value_for_command type
                # If old_value from model wasn't the expected type, try converting or use a placeholder
                # (Command needs robust handling)
                command = CellEditCommand(self.parent_window, row, col, old_value, new_value_for_command)
                # Check if the command is valid before pushing (e.g., target index exists)
                if command.target_index != -1:
                     self.parent_window.undo_stack.push(command)
                else:
                     print(f"Error: Could not create valid Undo command for row {row}, col {col}.")

            # elif new_value_for_model is not None:
                 # Value hasn't changed significantly, but ensure model data is set
                 # This might be needed if internal caches need updating,
                 # or if type changed slightly (e.g. int 1 to Decimal 1.00)
                 # model.setData(index, new_value_for_model, Qt.ItemDataRole.EditRole)
                 # Don't push command if no meaningful change occurred.
            # else: # Handle case where new_value is None (e.g., invalid input handled earlier)
                 # No change, do nothing

        except Exception as e:
             print(f"Error in setModelData for row {row}, col {col} (key: {col_key}): {e}")
             # Optionally revert model data if error occurs during processing
             # model.setData(index, old_value, Qt.ItemDataRole.EditRole)
             # Close editor to signal failure
             self.closeEditor.emit(editor, QStyledItemDelegate.EndEditHint.RevertModelCache)

    def updateEditorGeometry(self, editor, option, index):
        # Default geometry is usually fine
        editor.setGeometry(option.rect)

    def displayText(self, value, locale) -> str:
        # This method formats the data for display in the table *when not editing*.
        # It receives the raw data from the model (DisplayRole or EditRole fallback).
        # Value type depends on what the model provides (needs consistency!).

        # Handle Decimal for amount
        if isinstance(value, Decimal):
            # Format Decimal using locale. Use float conversion for toString compatibility.
            try:
                return self.locale.toString(float(value), 'f', 2)
            except Exception: # Handle potential float conversion errors for edge cases like NaN
                return "Error" # Or some indicator

        # Handle Date (assuming model stores 'yyyy-MM-dd' string)
        if isinstance(value, str) and len(value) == 10 and value.count('-') == 2:
            try:
                date = QDate.fromString(value, "yyyy-MM-dd")
                if date.isValid():
                    # Format date nicely using locale's default short format or a custom one
                    # return self.locale.toString(date, QLocale.FormatType.ShortFormat)
                    return date.toString("dd MMM yyyy") # Custom format
            except Exception:
                pass # Not a valid date string in the expected format

        # Handle Account/Category/SubCategory IDs by looking up their names
        if isinstance(value, int) and self.parent_window:
            # Try to determine which column we're displaying
            # This is a bit of a hack since displayText doesn't get the column index
            # We'll try to guess based on the value and available data

            # Check if it's an account ID
            for acc in self.accounts_list:
                if acc['id'] == value:
                    return acc['name']

            # Check if it's a category ID
            for cat in self.categories_list:
                if cat['id'] == value:
                    return cat['name']

            # Check if it's a subcategory ID
            for subcat in self.subcategories_list:
                if subcat['id'] == value:
                    print(f"DEBUG DISPLAY: Found subcategory name '{subcat['name']}' for ID {value}")
                    return subcat['name']

            # If we get here, it's an ID we couldn't resolve
            return f"ID:{value}"

        # Fallback: Display value as string (works for name, description, and potentially IDs if lookup fails)
        return str(value) if value is not None else ""

# --- END OF FILE delegates.py ---