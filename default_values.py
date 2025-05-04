"""
Default Values Module for Financial Tracker

This module provides functionality to store and manage default values for transaction fields.
"""
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import QLineEdit, QComboBox, QDateEdit

from debug_config import debug_config, debug_print

# Configuration file path
DEFAULT_VALUES_FILE = "default_values.json"

class DefaultValues:
    """Class for managing default values for transaction fields"""

    # Define the fields that can have defaults
    # Use the keys expected by the form_widgets dictionary in the main GUI
    DEFAULTABLE_FIELDS = [
        'name_in', 'value_in', 'type_in', 'account_in',
        'cat_in', 'subcat_in', 'desc_in', 'date_in'
    ]

    # Map form widget keys to the keys used in the transaction data dictionary
    FORM_TO_DATA_MAP = {
        'name_in': 'transaction_name',
        'value_in': 'transaction_value',
        'type_in': 'transaction_type',
        'account_in': 'account_id', # Store ID
        'cat_in': 'category_id',    # Store ID
        'subcat_in': 'sub_category_id', # Store ID
        'desc_in': 'transaction_description',
        'date_in': 'transaction_date' # Store ISO string
    }

    def __init__(self):
        """Initialize and load default values from file."""
        self._defaults = {}
        self.load()

    def load(self):
        """Load default values from the JSON file."""
        try:
            with open(DEFAULT_VALUES_FILE, 'r') as f:
                loaded_defaults = json.load(f)
                # Validate loaded keys against known fields
                self._defaults = {k: v for k, v in loaded_defaults.items() if k in self.DEFAULTABLE_FIELDS}
                debug_print('DEFAULTS', f"Loaded defaults: {self._defaults}")
        except FileNotFoundError:
            debug_print('DEFAULTS', f"Defaults file '{DEFAULT_VALUES_FILE}' not found. Using empty defaults.")
            self._defaults = {}
        except json.JSONDecodeError:
            debug_print('DEFAULTS', f"Error decoding JSON from '{DEFAULT_VALUES_FILE}'. Using empty defaults.")
            self._defaults = {}
        except Exception as e:
            debug_print('DEFAULTS', f"Error loading defaults: {e}. Using empty defaults.")
            self._defaults = {}

    def save(self):
        """Save the current default values to the JSON file."""
        try:
            with open(DEFAULT_VALUES_FILE, 'w') as f:
                json.dump(self._defaults, f, indent=4)
                debug_print('DEFAULTS', f"Saved defaults: {self._defaults}")
        except Exception as e:
            debug_print('DEFAULTS', f"Error saving defaults: {e}")

    def get_value(self, field_key):
        """Get the default value for a specific field key."""
        return self._defaults.get(field_key)

    def set_value(self, field_key, value):
        """Set a default value for a field key and save."""
        if field_key in self.DEFAULTABLE_FIELDS:
            # Basic type handling for saving (ensure JSON compatibility)
            if isinstance(value, Decimal):
                value = str(value) # Store Decimals as strings
            elif isinstance(value, QDate):
                value = value.toString("yyyy-MM-dd") # Store QDate as ISO string
            elif value is None:
                 # Allow explicitly clearing a default
                 if field_key in self._defaults:
                     del self._defaults[field_key]
                     debug_print('DEFAULTS', f"Cleared default for '{field_key}'")
                     self.save()
                 return # Don't store None

            if self._defaults.get(field_key) != value:
                self._defaults[field_key] = value
                debug_print('DEFAULTS', f"Set default '{field_key}' to '{value}'")
                self.save()
        else:
            debug_print('DEFAULTS', f"Warning: Attempted to set default for unknown field '{field_key}'")

    def get_all(self):
        """Return a copy of the current defaults dictionary."""
        return self._defaults.copy()

    def apply_to_form(self, widgets):
        """Apply stored default values to the form widgets."""
        debug_print('DEFAULTS', f"Applying defaults to form widgets...")
        for field_key, widget in widgets.items():
            default_value = self.get_value(field_key)
            if default_value is None:
                continue

            try:
                if isinstance(widget, QLineEdit):
                    # Handle Decimal conversion for value field
                    if field_key == 'value_in':
                        try:
                            val_decimal = Decimal(str(default_value))
                            widget.setText(str(val_decimal.quantize(Decimal("0.00"))))
                        except (InvalidOperation, TypeError, ValueError):
                            widget.setText("0.00") # Fallback
                    else:
                        widget.setText(str(default_value))
                    debug_print('DEFAULTS', f"  Applied '{default_value}' to QLineEdit '{field_key}'")

                elif isinstance(widget, QComboBox):
                    # Handle different combo box types
                    if field_key == 'type_in':
                        # Type is stored as text ('Income'/'Expense')
                        index = widget.findText(str(default_value))
                        if index != -1:
                            widget.setCurrentIndex(index)
                            debug_print('DEFAULTS', f"  Applied '{default_value}' (text) to QComboBox '{field_key}'")
                        else:
                            debug_print('DEFAULTS', f"  Warning: Default text '{default_value}' not found in QComboBox '{field_key}'")
                    else:
                        # Account, Category, SubCategory store ID
                        try:
                            value_id = int(default_value)
                            index = widget.findData(value_id)
                            if index != -1:
                                widget.setCurrentIndex(index)
                                debug_print('DEFAULTS', f"  Applied ID '{value_id}' to QComboBox '{field_key}'")
                            else:
                                debug_print('DEFAULTS', f"  Warning: Default ID '{value_id}' not found in QComboBox '{field_key}'")
                        except (ValueError, TypeError):
                            debug_print('DEFAULTS', f"  Warning: Invalid ID format '{default_value}' for QComboBox '{field_key}'")

                elif isinstance(widget, QDateEdit):
                    # Date is stored as ISO string "yyyy-MM-dd"
                    date = QDate.fromString(str(default_value), "yyyy-MM-dd")
                    if date.isValid():
                        widget.setDate(date)
                        debug_print('DEFAULTS', f"  Applied '{default_value}' (date) to QDateEdit '{field_key}'")
                    else:
                         # Fallback to current date if stored format is invalid
                         widget.setDate(QDate.currentDate())
                         debug_print('DEFAULTS', f"  Warning: Invalid date format '{default_value}' for QDateEdit '{field_key}'. Used current date.")

            except Exception as e:
                debug_print('DEFAULTS', f"  Error applying default for '{field_key}': {e}")
        debug_print('DEFAULTS', "...Finished applying defaults to form.")

    def apply_to_new_row(self, row_data):
        """
        Apply stored default values to a new row data dictionary.
        Modifies the dictionary in place.
        Returns the modified dictionary.
        """
        debug_print('DEFAULTS', f"Applying defaults to new row data...")
        for form_key, data_key in self.FORM_TO_DATA_MAP.items():
            default_value = self.get_value(form_key)
            if default_value is not None:
                try:
                    # Apply type conversion as needed for the data dictionary
                    if data_key == 'transaction_value':
                        row_data[data_key] = Decimal(str(default_value))
                    elif data_key.endswith('_id'): # account_id, category_id, sub_category_id
                        row_data[data_key] = int(default_value)
                    elif data_key == 'transaction_date':
                        # Ensure it's a valid ISO date string, otherwise use current date
                        try:
                            datetime.strptime(str(default_value), '%Y-%m-%d')
                            row_data[data_key] = str(default_value)
                        except ValueError:
                            row_data[data_key] = datetime.now().strftime('%Y-%m-%d')
                    else: # transaction_name, transaction_type, transaction_description
                        row_data[data_key] = str(default_value)
                    debug_print('DEFAULTS', f"  Applied default '{default_value}' to new row key '{data_key}'")
                except (ValueError, TypeError, InvalidOperation) as e:
                     debug_print('DEFAULTS', f"  Warning: Could not apply default for '{form_key}' to data key '{data_key}': {e}")

        debug_print('DEFAULTS', f"...Finished applying defaults to new row. Result: {row_data}")
        return row_data


# Create a global instance for use throughout the application
default_values = DefaultValues()
