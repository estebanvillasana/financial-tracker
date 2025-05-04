"""
Default Values Module for Financial Tracker

This module provides functionality to store and manage default values for transaction fields.
"""

import os
import json
from datetime import datetime
from decimal import Decimal
from PyQt6.QtCore import QDate

from debug_config import debug_config, debug_print

# Configuration file path
DEFAULT_VALUES_FILE = "default_values.json"

class DefaultValues:
    """Class for managing default values for transaction fields"""
    
    def __init__(self):
        # Initialize with empty default values
        self.values = {
            'transaction_name': '',
            'transaction_value': '',
            'transaction_type': '',
            'account_id': None,
            'account': '',
            'category_id': None,
            'category': '',
            'sub_category_id': None,
            'sub_category': '',
            'transaction_description': '',
            'transaction_date': ''
        }
        
        # Flag to indicate if default values are enabled
        self.enabled = False
        
        # Load saved default values
        self.load_values()
    
    def set_value(self, field, value):
        """Set a default value for a specific field"""
        debug_print('DEFAULT_VALUES', f"Setting default value for {field}: {value}")
        if field in self.values:
            self.values[field] = value
            return True
        return False
    
    def get_value(self, field):
        """Get the default value for a specific field"""
        return self.values.get(field)
    
    def clear_values(self):
        """Clear all default values"""
        debug_print('DEFAULT_VALUES', "Clearing all default values")
        self.values = {
            'transaction_name': '',
            'transaction_value': '',
            'transaction_type': '',
            'account_id': None,
            'account': '',
            'category_id': None,
            'category': '',
            'sub_category_id': None,
            'sub_category': '',
            'transaction_description': '',
            'transaction_date': ''
        }
        self.enabled = False
    
    def enable(self):
        """Enable the use of default values"""
        debug_print('DEFAULT_VALUES', "Enabling default values")
        self.enabled = True
    
    def disable(self):
        """Disable the use of default values"""
        debug_print('DEFAULT_VALUES', "Disabling default values")
        self.enabled = False
    
    def is_enabled(self):
        """Check if default values are enabled"""
        return self.enabled
    
    def save_values(self):
        """Save default values to a JSON file"""
        try:
            # Convert values to serializable format
            serializable_values = self.values.copy()
            
            # Handle special types
            if isinstance(serializable_values['transaction_value'], Decimal):
                serializable_values['transaction_value'] = str(serializable_values['transaction_value'])
            
            # Create a dictionary with values and enabled state
            data_to_save = {
                'values': serializable_values,
                'enabled': self.enabled
            }
            
            with open(DEFAULT_VALUES_FILE, 'w') as f:
                json.dump(data_to_save, f, indent=4)
            debug_print('DEFAULT_VALUES', "Default values saved to file")
        except Exception as e:
            print(f"Error saving default values: {e}")
    
    def load_values(self):
        """Load default values from a JSON file"""
        try:
            if os.path.exists(DEFAULT_VALUES_FILE):
                with open(DEFAULT_VALUES_FILE, 'r') as f:
                    data = json.load(f)
                
                # Load values
                if 'values' in data:
                    loaded_values = data['values']
                    
                    # Handle special types
                    if 'transaction_value' in loaded_values and loaded_values['transaction_value']:
                        try:
                            loaded_values['transaction_value'] = Decimal(loaded_values['transaction_value'])
                        except:
                            loaded_values['transaction_value'] = ''
                    
                    # Update values
                    for field, value in loaded_values.items():
                        if field in self.values:
                            self.values[field] = value
                
                # Load enabled state
                if 'enabled' in data:
                    self.enabled = data['enabled']
                
                debug_print('DEFAULT_VALUES', "Default values loaded from file")
        except Exception as e:
            print(f"Error loading default values: {e}")
    
    def apply_to_form(self, form_widgets):
        """Apply default values to form widgets"""
        if not self.enabled:
            return
        
        debug_print('DEFAULT_VALUES', "Applying default values to form")
        
        # Apply name
        if self.values['transaction_name'] and 'name_in' in form_widgets:
            form_widgets['name_in'].setText(self.values['transaction_name'])
        
        # Apply value
        if self.values['transaction_value'] and 'value_in' in form_widgets:
            if isinstance(self.values['transaction_value'], Decimal):
                form_widgets['value_in'].setText(str(self.values['transaction_value']))
            else:
                form_widgets['value_in'].setText(self.values['transaction_value'])
        
        # Apply type
        if self.values['transaction_type'] and 'type_in' in form_widgets:
            index = form_widgets['type_in'].findText(self.values['transaction_type'])
            if index >= 0:
                form_widgets['type_in'].setCurrentIndex(index)
        
        # Apply account
        if self.values['account'] and 'account_in' in form_widgets:
            index = form_widgets['account_in'].findText(self.values['account'])
            if index >= 0:
                form_widgets['account_in'].setCurrentIndex(index)
        
        # Apply category
        if self.values['category'] and 'cat_in' in form_widgets:
            index = form_widgets['cat_in'].findText(self.values['category'])
            if index >= 0:
                form_widgets['cat_in'].setCurrentIndex(index)
        
        # Apply subcategory
        if self.values['sub_category'] and 'subcat_in' in form_widgets:
            index = form_widgets['subcat_in'].findText(self.values['sub_category'])
            if index >= 0:
                form_widgets['subcat_in'].setCurrentIndex(index)
        
        # Apply description
        if self.values['transaction_description'] and 'desc_in' in form_widgets:
            form_widgets['desc_in'].setText(self.values['transaction_description'])
        
        # Apply date
        if self.values['transaction_date'] and 'date_in' in form_widgets:
            try:
                date = QDate.fromString(self.values['transaction_date'], 'yyyy-MM-dd')
                if date.isValid():
                    form_widgets['date_in'].setDate(date)
            except:
                pass
    
    def apply_to_new_row(self, row_data):
        """Apply default values to a new row data dictionary"""
        if not self.enabled:
            return row_data
        
        debug_print('DEFAULT_VALUES', "Applying default values to new row")
        
        # Create a copy of the row data
        new_row = row_data.copy()
        
        # Apply name
        if self.values['transaction_name']:
            new_row['transaction_name'] = self.values['transaction_name']
        
        # Apply value
        if self.values['transaction_value']:
            if isinstance(self.values['transaction_value'], Decimal):
                new_row['transaction_value'] = self.values['transaction_value']
            else:
                try:
                    new_row['transaction_value'] = Decimal(self.values['transaction_value'])
                except:
                    pass
        
        # Apply type
        if self.values['transaction_type']:
            new_row['transaction_type'] = self.values['transaction_type']
        
        # Apply account
        if self.values['account_id'] is not None:
            new_row['account_id'] = self.values['account_id']
            new_row['account'] = self.values['account']
        
        # Apply category
        if self.values['category_id'] is not None:
            new_row['category_id'] = self.values['category_id']
            new_row['category'] = self.values['category']
        
        # Apply subcategory
        if self.values['sub_category_id'] is not None:
            new_row['sub_category_id'] = self.values['sub_category_id']
            new_row['sub_category'] = self.values['sub_category']
        
        # Apply description
        if self.values['transaction_description']:
            new_row['transaction_description'] = self.values['transaction_description']
        
        # Apply date
        if self.values['transaction_date']:
            new_row['transaction_date'] = self.values['transaction_date']
        
        return new_row
    
    def update_from_form(self, form_widgets):
        """Update default values from form widgets"""
        debug_print('DEFAULT_VALUES', "Updating default values from form")
        
        # Update name
        if 'name_in' in form_widgets:
            self.values['transaction_name'] = form_widgets['name_in'].text()
        
        # Update value
        if 'value_in' in form_widgets:
            value_text = form_widgets['value_in'].text()
            if value_text:
                try:
                    self.values['transaction_value'] = Decimal(value_text)
                except:
                    self.values['transaction_value'] = value_text
            else:
                self.values['transaction_value'] = ''
        
        # Update type
        if 'type_in' in form_widgets:
            self.values['transaction_type'] = form_widgets['type_in'].currentText()
        
        # Update account
        if 'account_in' in form_widgets:
            self.values['account'] = form_widgets['account_in'].currentText()
            self.values['account_id'] = form_widgets['account_in'].currentData()
        
        # Update category
        if 'cat_in' in form_widgets:
            self.values['category'] = form_widgets['cat_in'].currentText()
            self.values['category_id'] = form_widgets['cat_in'].currentData()
        
        # Update subcategory
        if 'subcat_in' in form_widgets:
            self.values['sub_category'] = form_widgets['subcat_in'].currentText()
            self.values['sub_category_id'] = form_widgets['subcat_in'].currentData()
        
        # Update description
        if 'desc_in' in form_widgets:
            self.values['transaction_description'] = form_widgets['desc_in'].text()
        
        # Update date
        if 'date_in' in form_widgets:
            self.values['transaction_date'] = form_widgets['date_in'].date().toString('yyyy-MM-dd')
        
        # Save the updated values
        self.save_values()

# Create a global instance for use throughout the application
default_values = DefaultValues()
