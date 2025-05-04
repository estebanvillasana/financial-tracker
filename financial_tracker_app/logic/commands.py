# --- START OF FILE commands.py ---

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP # Re-add InvalidOperation and ROUND_HALF_UP
from PyQt6.QtGui import QUndoCommand
from PyQt6.QtCore import Qt, QTimer # Import Qt for roles and QTimer
from PyQt6.QtWidgets import QTableWidgetItem

# Import debug configuration
try:
    from financial_tracker_app.utils.debug_config import debug_config, debug_print
except ImportError:
    # Fallback if debug_config.py doesn't exist yet
    class DummyDebugConfig:
        def is_enabled(self, category):
            return False
    debug_config = DummyDebugConfig()
    def debug_print(category, message):
        pass

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
                 debug_print('UNDERLYING_DATA', f"Error: Invalid pending index {pending_index} for row {self.row}")
                 self.setObsolete(True); return # Mark command as invalid immediately
        else:
            self.is_pending = False
            if 0 <= self.row < len(self.main_window.transactions):
                self.target_index = self.row
                self.target_data_dict = self.main_window.transactions[self.target_index]
                self.rowid = self.target_data_dict.get('rowid') # Get rowid for existing transactions
            else:
                 debug_print('UNDERLYING_DATA', f"Error: Invalid transaction index {self.row}")
                 self.setObsolete(True); return # Mark command as invalid

        # --- Get Column Key ---
        try:
            self.col_key = self.main_window.COLS[self.col]
        except IndexError:
             debug_print('UNDERLYING_DATA', f"Error: Invalid column index {self.col}")
             self.setObsolete(True); return # Mark command as invalid

        # --- Type Conversion and Value Preparation ---
        # Convert amount values to Decimal, handle potential errors
        if self.col_key == 'transaction_value':
            self.old_value = self._prepare_decimal(self._raw_old_value)
            self.new_value = self._prepare_decimal(self._raw_new_value)
            if self.new_value is None: # If new value conversion failed
                 debug_print('CURRENCY', f"Error: Invalid new Decimal value for {self.col_key}: '{self._raw_new_value}'")
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
            return value.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP) # Use imported ROUND_HALF_UP
        if value is None:
            return Decimal('0.00')
        try:
            # Convert potential float/int/str to Decimal
            d = Decimal(str(value))
            return d.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP) # Use imported ROUND_HALF_UP
        except (InvalidOperation, TypeError, ValueError): # Use imported InvalidOperation
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
            debug_print('UNDERLYING_DATA', f"Error in _update_data: Command is obsolete or target_data_dict is None.")
            return False

        # --- Apply the main value change ---
        # Store the primary value being set
        primary_value = value_to_set

        # --- Update ID and Name fields based on the column edited ---
        if self.col_key == 'account':
            account_id = primary_value # The value from dropdown is the ID
            account_name = self._find_name_for_id('account', account_id)
            self.target_data_dict['account_id'] = account_id
            self.target_data_dict['account'] = account_name
            debug_print('ACCOUNT_CONVERSION', f"Set account_id={account_id}, account='{account_name}'")
            # Trigger currency update
            QTimer.singleShot(0, lambda: self.main_window._update_currency_display_for_row(self.row))
        elif self.col_key == 'transaction_type':
            self.target_data_dict['transaction_type'] = primary_value
            # Reset category/subcategory when type changes
            if primary_value != self._old_related_ids.get('transaction_type'):
                debug_print('DROPDOWN', f"Transaction type changed to {primary_value}. Resetting category/subcategory.")
                new_type = primary_value
                # Find UNCATEGORIZED category for the new type
                uncat_cat_id = self._find_id_for_name('category', 'UNCATEGORIZED', new_type)
                if uncat_cat_id is None: # Ensure it exists
                    print(f"Warning: UNCATEGORIZED category for type '{new_type}' not found. DB interaction might be needed.")
                    # Potentially call db.ensure_category here if needed, then reload dropdown data
                self.target_data_dict['category_id'] = uncat_cat_id
                self.target_data_dict['category'] = 'UNCATEGORIZED' if uncat_cat_id else ''
                # Find UNCATEGORIZED subcategory for the new category
                uncat_subcat_id = None
                if uncat_cat_id is not None:
                    uncat_subcat_id = self._find_id_for_name('sub_category', 'UNCATEGORIZED', uncat_cat_id)
                    if uncat_subcat_id is None: # Ensure it exists
                         uncat_subcat_id = self.main_window.db.ensure_subcategory('UNCATEGORIZED', uncat_cat_id)
                         if uncat_subcat_id: QTimer.singleShot(0, self.main_window._load_dropdown_data) # Reload if created
                self.target_data_dict['sub_category_id'] = uncat_subcat_id
                self.target_data_dict['sub_category'] = 'UNCATEGORIZED' if uncat_subcat_id else ''
        elif self.col_key == 'category':
            category_id = primary_value # The value from dropdown is the ID
            current_type = self.target_data_dict.get('transaction_type', 'Expense')
            category_name = self._find_name_for_id('category', category_id, current_type)
            self.target_data_dict['category_id'] = category_id
            self.target_data_dict['category'] = category_name
            # Reset subcategory if category changed
            if category_id != self._old_related_ids.get('category_id'):
                debug_print('DROPDOWN', f"Category changed to ID {category_id}. Resetting subcategory.")
                uncat_subcat_id = self._find_id_for_name('sub_category', 'UNCATEGORIZED', category_id)
                if uncat_subcat_id is None and category_id is not None: # Ensure it exists
                    uncat_subcat_id = self.main_window.db.ensure_subcategory('UNCATEGORIZED', category_id)
                    if uncat_subcat_id: QTimer.singleShot(0, self.main_window._load_dropdown_data) # Reload if created
                self.target_data_dict['sub_category_id'] = uncat_subcat_id
                self.target_data_dict['sub_category'] = 'UNCATEGORIZED' if uncat_subcat_id else ''
        elif self.col_key == 'sub_category':
            subcategory_id = primary_value # The value from dropdown is the ID
            current_cat_id = self.target_data_dict.get('category_id')
            subcategory_name = self._find_name_for_id('sub_category', subcategory_id, current_cat_id)
            self.target_data_dict['sub_category_id'] = subcategory_id
            self.target_data_dict['sub_category'] = subcategory_name
        else:
            # For non-dropdown columns (name, description, value, date), just set the value
            self.target_data_dict[self.col_key] = primary_value
            # If value changed, trigger currency update
            if self.col_key == 'transaction_value':
                 QTimer.singleShot(0, lambda: self.main_window._update_currency_display_for_row(self.row))


        # --- Handle UNDO State Restoration ---
        if related_ids_to_restore:
             # This block is executed during UNDO.
             # Restore all related IDs to their state *before* the original change.
             self.target_data_dict['account_id'] = related_ids_to_restore.get('account_id')
             self.target_data_dict['category_id'] = related_ids_to_restore.get('category_id')
             self.target_data_dict['sub_category_id'] = related_ids_to_restore.get('sub_category_id')
             self.target_data_dict['transaction_type'] = related_ids_to_restore.get('transaction_type')

             # Also restore the corresponding *name* fields based on the restored IDs.
             self.target_data_dict['account'] = self._find_name_for_id('account', related_ids_to_restore.get('account_id'))
             restored_type = related_ids_to_restore.get('transaction_type')
             restored_cat_id = related_ids_to_restore.get('category_id')
             self.target_data_dict['category'] = self._find_name_for_id('category', restored_cat_id, restored_type)
             self.target_data_dict['sub_category'] = self._find_name_for_id('sub_category', related_ids_to_restore.get('sub_category_id'), restored_cat_id)

             # Ensure the primary value being undone is also set correctly
             # (This might be redundant if primary_value was already the old value, but ensures consistency)
             self.target_data_dict[self.col_key] = primary_value # primary_value is old_value during undo

        # --- Update Dirty State (for existing transactions only) ---
        if not self.is_pending and self.rowid is not None:
            original_db_value = self.main_window._original_data_cache.get(self.rowid, {}).get(self.col_key)
            current_value_in_dict = self.target_data_dict.get(self.col_key) # Use .get for safety

            # Compare appropriately (Decimal vs Decimal, others as string)
            is_dirty = False
            if isinstance(current_value_in_dict, Decimal):
                 original_db_decimal = self._prepare_decimal(original_db_value)
                 if original_db_decimal is not None:
                      # Compare quantized values
                      is_dirty = (current_value_in_dict.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP) != original_db_decimal)
                 else:
                      is_dirty = True # Consider dirty if original couldn't be parsed
            elif current_value_in_dict is None and original_db_value is None:
                 is_dirty = False
            elif str(current_value_in_dict) != str(original_db_value):
                 is_dirty = True

            # Update dirty sets
            if is_dirty:
                self.main_window.dirty.add(self.rowid)
                dirty_fields = self.main_window.dirty_fields.setdefault(self.rowid, set())
                dirty_fields.add(self.col_key)
                debug_print('DIRTY_STATE', f"RowID {self.rowid} marked dirty for field {self.col_key}. Current: '{current_value_in_dict}', Original: '{original_db_value}'")
            else:
                # Field reverted to original value
                if self.rowid in self.main_window.dirty_fields:
                    self.main_window.dirty_fields[self.rowid].discard(self.col_key)
                    debug_print('DIRTY_STATE', f"Field {self.col_key} for RowID {self.rowid} reverted to original. Removing from dirty fields.")
                    if not self.main_window.dirty_fields[self.rowid]:
                        del self.main_window.dirty_fields[self.rowid]
                        self.main_window.dirty.discard(self.rowid)
                        debug_print('DIRTY_STATE', f"RowID {self.rowid} no longer dirty.")

        # --- Trigger UI Update ---
        model = self.main_window.tbl.model()
        if model:
             model_index = model.index(self.row, self.col)
             # Emit dataChanged for the specific cell and potentially related cells if names changed
             model.dataChanged.emit(model_index, model_index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
             # TODO: If name fields were updated due to ID change, emit dataChanged for those cells too

        self.main_window._recolor_row(self.row)
        self.main_window._update_button_states()
        # Print underlying data after update for debugging
        debug_print('UNDERLYING_DATA', f"Data dict after update (Row {self.row}, Col {self.col}, Key {self.col_key}): {self.target_data_dict}")
        return True

    def redo(self):
        """Apply the new value."""
        self._capture_related_ids('old')

        if not self._update_data(self.new_value):
             self.setObsolete(True)
        else:
            self._capture_related_ids('new')

    def undo(self):
        """Revert to the old value."""
        if not self._update_data(self.old_value, related_ids_to_restore=self._old_related_ids):
             self.setObsolete(True)

    def _find_id_for_name(self, field_type, name, context=None):
        """Finds the ID for a given name (account, category, sub_category). Context needed for category/sub_category."""
        if name is None: return None

        if field_type == 'account':
            for acc in self.main_window._accounts_data:
                if acc['name'] == name: return acc['id']
        elif field_type == 'category':
            trans_type = context if context else 'Expense'
            for cat in self.main_window._categories_data:
                if cat['name'] == name and cat['type'] == trans_type: return cat['id']
        elif field_type == 'sub_category':
            cat_id = context
            if cat_id is not None:
                for subcat in self.main_window._subcategories_data:
                    if subcat['name'] == name and subcat['category_id'] == cat_id: return subcat['id']

        return None

    def _find_name_for_id(self, field_type, item_id, context=None):
        """Finds the name for a given ID (account, category, sub_category). Context needed for category/sub_category."""
        if item_id is None: return ""

        if field_type == 'account':
            for acc in self.main_window._accounts_data:
                if acc['id'] == item_id: return acc['name']
        elif field_type == 'category':
            for cat in self.main_window._categories_data:
                if cat['id'] == item_id: return cat['name']
        elif field_type == 'sub_category':
            for subcat in self.main_window._subcategories_data:
                if subcat['id'] == item_id: return subcat['name']

        return ""

# --- END OF FILE commands.py ---