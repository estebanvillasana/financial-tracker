# --- START OF FILE commands.py ---

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP # Import Decimal and rounding mode

from PyQt6.QtGui import QUndoCommand
from PyQt6.QtCore import Qt, QTimer # Import Qt for roles and QTimer
from PyQt6.QtWidgets import QTableWidgetItem

class CellEditCommand(QUndoCommand):
    """Undo/Redo command for cell edits."""
    def __init__(self, main_window, row, col, old_value, new_value, parent=None):
        """
        Initializes the command for a cell edit.

        Args:
            main_window: Reference to the main ExpenseTrackerGUI instance.
            row (int): The visual row index in the table.
            col (int): The visual column index in the table.
            old_value: The value before the edit (type depends on column, e.g., Decimal, str, int ID).
            new_value: The value after the edit (type depends on column, e.g., Decimal, str, int ID).
            parent: Optional parent for the QUndoCommand.
        """
        super().__init__(parent)
        self.main_window = main_window
        self.row = row
        self.col = col

        # Store raw old/new values as passed by the delegate
        self._raw_old_value = old_value
        self._raw_new_value = new_value

        self.target_data_dict = None # The actual dictionary (in transactions or pending) being modified
        self.is_pending = False
        self.target_index = -1 # Index within the transactions or pending list
        self.rowid = None # Database rowid (None for pending rows)

        # --- Determine target data list and index ---
        num_transactions = len(self.main_window.transactions)
        if self.row >= num_transactions:
            self.is_pending = True
            pending_index = self.row - num_transactions
            if 0 <= pending_index < len(self.main_window.pending):
                self.target_index = pending_index
                self.target_data_dict = self.main_window.pending[self.target_index]
            else:
                 print(f"Error (Command Init): Invalid pending index {pending_index} for row {self.row}")
                 self.setObsolete(True); return # Mark command as invalid immediately
        else:
            self.is_pending = False
            if 0 <= self.row < len(self.main_window.transactions):
                self.target_index = self.row
                self.target_data_dict = self.main_window.transactions[self.target_index]
                self.rowid = self.target_data_dict.get('rowid') # Get rowid for existing transactions
            else:
                 print(f"Error (Command Init): Invalid transaction index {self.row}")
                 self.setObsolete(True); return # Mark command as invalid

        # --- Get Column Key ---
        try:
            self.col_key = self.main_window.COLS[self.col]
        except IndexError:
             print(f"Error (Command Init): Invalid column index {self.col}")
             self.setObsolete(True); return # Mark command as invalid

        # --- Type Conversion and Value Preparation ---
        # Convert amount values to Decimal, handle potential errors
        if self.col_key == 'transaction_value':
            self.old_value = self._prepare_decimal(self._raw_old_value)
            self.new_value = self._prepare_decimal(self._raw_new_value)
            if self.new_value is None: # If new value conversion failed
                 print(f"Error (Command Init): Invalid new Decimal value for {self.col_key}: '{self._raw_new_value}'")
                 self.setObsolete(True); return
        else:
             # For other columns, use the values as passed (should be IDs for linked fields)
             self.old_value = self._raw_old_value
             self.new_value = self._raw_new_value

        # --- Store related IDs for context changes (e.g., category change affects subcategory) ---
        # These will be captured from the target_data_dict *before* the first redo applies the change.
        self._old_related_ids = {}
        self._new_related_ids_after_change = {} # Store IDs *after* the change is applied by redo

        self.setText(f"Edit {self.col_key} at row {self.row + 1}")

    def _prepare_decimal(self, value):
        """Safely converts a value to Decimal or returns None on failure."""
        if isinstance(value, Decimal):
            return value.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
        if value is None:
            return Decimal('0.00')
        try:
            # Convert potential float/int/str to Decimal
            d = Decimal(str(value))
            return d.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
        except (InvalidOperation, TypeError, ValueError):
            return None # Indicate conversion failure

    def _capture_related_ids(self, capture_for='old'):
        """Captures the state of related IDs (account, category, subcategory, type)"""
        if not self.target_data_dict: return

        ids_to_capture = {
             'account_id': self.target_data_dict.get('account_id'),
             'category_id': self.target_data_dict.get('category_id'),
             'sub_category_id': self.target_data_dict.get('sub_category_id'),
             'transaction_type': self.target_data_dict.get('transaction_type')
        }
        if capture_for == 'old':
             self._old_related_ids = ids_to_capture
        else: # 'new'
             self._new_related_ids_after_change = ids_to_capture


    def _update_data(self, value_to_set, related_ids_to_restore=None):
        """
        Updates the underlying data dictionary and handles side effects.

        Args:
            value_to_set: The primary value to set for self.col_key.
            related_ids_to_restore (dict, optional): If provided (during undo),
                                                    restore related IDs to this state.
        Returns:
            bool: True if successful, False otherwise.
        """
        if self.target_data_dict is None:
            print(f"Error in _update_data: Command is obsolete or target_data_dict is None.")
            return False

        # --- Apply the main value change ---
        # The 'value_to_set' from dropdowns is the ID.
        target_value_id = None
        target_value_name = ""

        # Determine the correct ID and Name based on the column being edited
        if self.col_key == 'account':
            target_value_id = value_to_set # value_to_set is the account_id
            target_value_name = self._find_name_for_id('account', target_value_id)
            self.target_data_dict['account_id'] = target_value_id
            self.target_data_dict['account'] = target_value_name
            # print(f"DEBUG _update_data: Updated account_id={target_value_id}, account='{target_value_name}'")
        elif self.col_key == 'transaction_type':
            # Handle transaction type change
            self.target_data_dict['transaction_type'] = value_to_set

            # When transaction type changes, we need to update the category to an appropriate one for the new type
            old_type = self._old_related_ids.get('transaction_type')
            if old_type != value_to_set:
                # Find UNCATEGORIZED category for the new transaction type
                uncategorized_cat = None
                for cat in self.main_window._categories_data:
                    if cat['name'] == 'UNCATEGORIZED' and cat['type'] == value_to_set:
                        uncategorized_cat = cat
                        break

                if uncategorized_cat:
                    # Update category
                    self.target_data_dict['category_id'] = uncategorized_cat['id']
                    self.target_data_dict['category'] = uncategorized_cat['name']

                    # Find UNCATEGORIZED subcategory for this category
                    uncategorized_subcat = None
                    for subcat in self.main_window._subcategories_data:
                        if subcat['category_id'] == uncategorized_cat['id'] and subcat['name'] == 'UNCATEGORIZED':
                            uncategorized_subcat = subcat
                            break

                    if uncategorized_subcat:
                        self.target_data_dict['sub_category_id'] = uncategorized_subcat['id']
                        self.target_data_dict['sub_category'] = uncategorized_subcat['name']
                    else:
                        # If UNCATEGORIZED subcategory doesn't exist, create it
                        uncat_subcat_id = self.main_window.db.ensure_subcategory('UNCATEGORIZED', uncategorized_cat['id'])
                        if uncat_subcat_id:
                            self.target_data_dict['sub_category_id'] = uncat_subcat_id
                            self.target_data_dict['sub_category'] = 'UNCATEGORIZED'
                            QTimer.singleShot(0, self.main_window._load_dropdown_data)

                    # Update the UI to reflect the changes
                    row = self.target_index
                    if row >= 0:
                        # Update category cell
                        cat_col = self.main_window.COLS.index('category')
                        self.main_window.tbl.item(row, cat_col).setText('UNCATEGORIZED')

                        # Update subcategory cell
                        subcat_col = self.main_window.COLS.index('sub_category')
                        if self.main_window.tbl.item(row, subcat_col) is None:
                            self.main_window.tbl.setItem(row, subcat_col, QTableWidgetItem('UNCATEGORIZED'))
                        else:
                            self.main_window.tbl.item(row, subcat_col).setText('UNCATEGORIZED')

                print(f"Transaction type changed from {old_type} to {value_to_set}, updated category and subcategory")

        elif self.col_key == 'category':
            target_value_id = value_to_set # value_to_set is the category_id
            current_type = self.target_data_dict.get('transaction_type', 'Expense')
            target_value_name = self._find_name_for_id('category', target_value_id, current_type)
            self.target_data_dict['category_id'] = target_value_id # Ensure ID key is updated
            self.target_data_dict['category'] = target_value_name
            # Clear subcategory if category changed (delegate should create new subcat dropdown)
            # Check against the *old* related ID captured before the change
            if target_value_id != self._old_related_ids.get('category_id'):
                 # Find default 'UNCATEGORIZED' subcategory ID for the new category
                 uncat_subcat_id = self._find_id_for_name('sub_category', 'UNCATEGORIZED', target_value_id)
                 if uncat_subcat_id is None:
                     # Try to ensure it exists if lookup failed
                     print(f"Warning: UNCATEGORIZED subcategory not found for category ID {target_value_id}. Attempting creation.")
                     uncat_subcat_id = self.main_window.db.ensure_subcategory('UNCATEGORIZED', target_value_id)
                     if uncat_subcat_id:
                          QTimer.singleShot(0, self.main_window._load_dropdown_data) # Reload if created

                 self.target_data_dict['sub_category_id'] = uncat_subcat_id
                 self.target_data_dict['sub_category'] = 'UNCATEGORIZED' if uncat_subcat_id else '' # Set name
                 # print(f"DEBUG _update_data: Category changed, reset subcategory to ID={uncat_subcat_id}")
            # print(f"DEBUG _update_data: Updated category_id={target_value_id}, category='{target_value_name}'")
        elif self.col_key == 'sub_category':
            target_value_id = value_to_set # value_to_set is the sub_category_id
            current_cat_id = self.target_data_dict.get('category_id')
            target_value_name = self._find_name_for_id('sub_category', target_value_id, current_cat_id)
            self.target_data_dict['sub_category_id'] = target_value_id # Ensure ID key is updated
            self.target_data_dict['sub_category'] = target_value_name
            # print(f"DEBUG _update_data: Updated sub_category_id={target_value_id}, sub_category='{target_value_name}'")
        else:
            # For non-dropdown columns, just set the value for the primary key
            self.target_data_dict[self.col_key] = value_to_set
            # print(f"DEBUG _update_data: Set {self.col_key} to {value_to_set}")

        # --- Handle Side Effects / Restore Related State ---
        if related_ids_to_restore:
             # Restoring state during UNDO
             # print(f"DEBUG _update_data: Restoring related IDs: {related_ids_to_restore}")
             self.target_data_dict['account_id'] = related_ids_to_restore.get('account_id')
             self.target_data_dict['category_id'] = related_ids_to_restore.get('category_id')
             self.target_data_dict['sub_category_id'] = related_ids_to_restore.get('sub_category_id')
             self.target_data_dict['transaction_type'] = related_ids_to_restore.get('transaction_type')

             # Also restore the *name* fields if the change was to an ID field being undone
             if self.col_key == 'account':
                 self.target_data_dict['account'] = self._find_name_for_id('account', related_ids_to_restore.get('account_id'))
             elif self.col_key == 'category':
                  self.target_data_dict['category'] = self._find_name_for_id('category', related_ids_to_restore.get('category_id'), related_ids_to_restore.get('transaction_type'))
             elif self.col_key == 'sub_category':
                  self.target_data_dict['sub_category'] = self._find_name_for_id('sub_category', related_ids_to_restore.get('sub_category_id'), related_ids_to_restore.get('category_id'))

        else:
            # Applying change during REDO
            # Update the corresponding *name* field if an *ID* field was the primary change
            if self.col_key == 'account_id':
                 self.target_data_dict['account'] = self._find_name_for_id('account', value_to_set)
            elif self.col_key == 'category_id':
                 current_type = self.target_data_dict.get('transaction_type', 'Expense')
                 self.target_data_dict['category'] = self._find_name_for_id('category', value_to_set, current_type)
                 # If category ID changes, clear subcategory unless it's being set simultaneously?
                 # For simplicity, let's assume category/subcategory are changed via their *name* columns by the user/delegate.
            elif self.col_key == 'sub_category_id':
                 current_cat_id = self.target_data_dict.get('category_id')
                 self.target_data_dict['sub_category'] = self._find_name_for_id('sub_category', value_to_set, current_cat_id)

            # Update the corresponding *ID* field if a *name* field was the primary change
            # This requires looking up the ID based on the new name.
            elif self.col_key == 'account':
                acc_id = self._find_id_for_name('account', value_to_set)
                self.target_data_dict['account_id'] = acc_id
                # print(f"DEBUG _update_data: Set account_id to {acc_id} based on name '{value_to_set}'")
            elif self.col_key == 'category':
                 current_type = self.target_data_dict.get('transaction_type', 'Expense')
                 cat_id = self._find_id_for_name('category', value_to_set, current_type)
                 self.target_data_dict['category_id'] = cat_id
                 # Set subcategory to UNCATEGORIZED when category changes or when category is UNCATEGORIZED
                 if self.target_data_dict.get('category_id') != self._old_related_ids.get('category_id'):
                     # Find UNCATEGORIZED subcategory for the new category
                     new_cat_id = self.target_data_dict.get('category_id')
                     if new_cat_id is not None:
                         # Try to find existing UNCATEGORIZED subcategory
                         uncat_subcat_id = self._find_id_for_name('sub_category', 'UNCATEGORIZED', new_cat_id)
                         if uncat_subcat_id is None:
                             # Try to create it if it doesn't exist
                             print(f"Creating UNCATEGORIZED subcategory for category ID {new_cat_id}")
                             uncat_subcat_id = self.main_window.db.ensure_subcategory('UNCATEGORIZED', new_cat_id)
                             if uncat_subcat_id:
                                 # Add to subcategories list
                                 self.main_window._subcategories_data.append({
                                     'id': uncat_subcat_id,
                                     'name': 'UNCATEGORIZED',
                                     'category_id': new_cat_id
                                 })
                                 # Reload dropdown data in the background
                                 QTimer.singleShot(0, self.main_window._load_dropdown_data)

                         # Set the subcategory to UNCATEGORIZED
                         self.target_data_dict['sub_category_id'] = uncat_subcat_id
                         self.target_data_dict['sub_category'] = 'UNCATEGORIZED'
                         print(f"DEBUG _update_data: Category is {target_value_name}, setting subcategory to UNCATEGORIZED (ID: {uncat_subcat_id})")

                         # Update the UI to reflect the changes
                         subcategory_col = self.main_window.COLS.index('sub_category')
                         if self.row < self.main_window.tbl.rowCount():
                             item = self.main_window.tbl.item(self.row, subcategory_col)
                             if item:
                                 item.setText('UNCATEGORIZED')
                 # print(f"DEBUG _update_data: Set category_id to {cat_id} based on name '{value_to_set}' (type: {current_type})")
            elif self.col_key == 'sub_category':
                 current_cat_id = self.target_data_dict.get('category_id')
                 subcat_id = self._find_id_for_name('sub_category', value_to_set, current_cat_id)
                 self.target_data_dict['sub_category_id'] = subcat_id
                 print(f"DEBUG _update_data: Set sub_category_id to {subcat_id} based on name '{value_to_set}' (cat_id: {current_cat_id})")

            # If transaction_type changes, the category/subcategory might become invalid.
            # The validation in _save_changes should catch this. We could try to auto-fix here,
            # e.g., reset category/subcategory to UNCATEGORIZED for the new type, but it adds complexity.
            # Let's rely on validation for now. The command just records the change.

        # --- Update Dirty State (for existing transactions only) ---
        if not self.is_pending and self.rowid is not None:
            original_db_value = self.main_window._original_data_cache.get(self.rowid, {}).get(self.col_key)
            current_value_in_dict = self.target_data_dict[self.col_key]

            # Compare appropriately (Decimal vs Decimal, others as string)
            is_dirty = False
            if isinstance(current_value_in_dict, Decimal):
                 original_db_decimal = self._prepare_decimal(original_db_value)
                 # Compare only if original value was also a valid Decimal
                 if original_db_decimal is not None:
                      is_dirty = (current_value_in_dict != original_db_decimal)
                 else: # Treat mismatch if original wasn't valid decimal but current is
                      is_dirty = True
            elif current_value_in_dict is None and original_db_value is None:
                 is_dirty = False # NULL == NULL
            elif str(current_value_in_dict) != str(original_db_value):
                 is_dirty = True

            # Update dirty sets
            if is_dirty:
                self.main_window.dirty.add(self.rowid)
                dirty_fields = self.main_window.dirty_fields.setdefault(self.rowid, set())
                dirty_fields.add(self.col_key)
                # print(f"DEBUG DirtyState: Marked row {self.rowid}, field {self.col_key} as dirty.")
            else:
                # Field potentially reverted to original value
                if self.rowid in self.main_window.dirty_fields:
                    self.main_window.dirty_fields[self.rowid].discard(self.col_key)
                    if not self.main_window.dirty_fields[self.rowid]: # No more dirty fields for this row
                        del self.main_window.dirty_fields[self.rowid]
                        self.main_window.dirty.discard(self.rowid)
                        # print(f"DEBUG DirtyState: Row {self.rowid} is no longer dirty.")

        # --- Trigger UI Update ---
        # Re-validate the row after change (clears errors if fixed, adds if created)
        # self.main_window._validate_row(self.target_data_dict, self.row) # This might be too slow if called often

        # Recolor the row and update button states
        # Need to inform the Table Model that data has changed so it emits dataChanged
        model = self.main_window.tbl.model()
        if model:
             model_index = model.index(self.row, self.col)
             # Emit dataChanged for the specific cell that was the primary target
             # The model should ideally return the correct DisplayRole data now.
             model.dataChanged.emit(model_index, model_index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])

             # If related fields changed (like category causing subcategory change), emit for those too?
             # This gets complicated. Relying on _recolor_row might be sufficient visually.

        self.main_window._recolor_row(self.row) # Update row background/cell colors
        self.main_window._update_button_states()
        return True # Indicate success

    def redo(self):
        """Apply the new value."""
        # print(f"Redo: Set row {self.row}, col {self.col} ({self.col_key}) to '{self.new_value}'")

        # Capture related IDs *before* applying the change
        self._capture_related_ids('old')

        if not self._update_data(self.new_value):
             self.setObsolete(True)
        else:
            # Capture related IDs *after* applying the change (for undo restoration)
            self._capture_related_ids('new')

    def undo(self):
        """Revert to the old value."""
        # print(f"Undo: Set row {self.row}, col {self.col} ({self.col_key}) to '{self.old_value}'")

        # Restore the primary value and the related IDs captured before the redo
        if not self._update_data(self.old_value, related_ids_to_restore=self._old_related_ids):
             self.setObsolete(True)


    # --- Helper methods for ID/Name lookup ---

    def _find_id_for_name(self, field_type, name, context=None):
        """Finds the ID for a given name (account, category, sub_category). Context needed for category/sub_category."""
        if name is None: return None

        if field_type == 'account':
            for acc in self.main_window._accounts_data:
                if acc['name'] == name: return acc['id']
        elif field_type == 'category':
            # Context is the transaction_type ('Income' or 'Expense')
            trans_type = context if context else 'Expense' # Default assumption
            for cat in self.main_window._categories_data:
                if cat['name'] == name and cat['type'] == trans_type: return cat['id']
        elif field_type == 'sub_category':
            # Context is the category_id
            cat_id = context
            if cat_id is not None:
                for subcat in self.main_window._subcategories_data:
                    if subcat['name'] == name and subcat['category_id'] == cat_id: return subcat['id']

        # print(f"Warning (Command Lookup): Could not find ID for {field_type} '{name}' with context '{context}'")
        return None # Not found

    def _find_name_for_id(self, field_type, item_id, context=None):
        """Finds the name for a given ID (account, category, sub_category). Context needed for category/sub_category."""
        if item_id is None: return "" # Return empty string for None ID

        if field_type == 'account':
            for acc in self.main_window._accounts_data:
                if acc['id'] == item_id: return acc['name']
        elif field_type == 'category':
             # Context is transaction type (used for display consistency, though ID is unique)
            for cat in self.main_window._categories_data:
                if cat['id'] == item_id: return cat['name']
        elif field_type == 'sub_category':
             # Context is category_id (needed if names weren't unique across categories)
            for subcat in self.main_window._subcategories_data:
                if subcat['id'] == item_id: return subcat['name']

        # print(f"Warning (Command Lookup): Could not find name for {field_type} ID '{item_id}' with context '{context}'")
        return "" # Not found or ID was None


# --- END OF FILE commands.py ---