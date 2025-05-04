"""
Default Values UI Module for Financial Tracker

This module provides a UI for managing default values for transaction fields.
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, 
                            QLabel, QPushButton, QCheckBox, QGridLayout)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from default_values import default_values
from debug_config import debug_config, debug_print

class DefaultValuesDialog(QDialog):
    """Dialog for managing default values"""
    
    def __init__(self, parent=None, form_widgets=None):
        super().__init__(parent)
        self.parent = parent
        self.form_widgets = form_widgets
        self.setWindowTitle("Default Values")
        self.setMinimumWidth(500)
        self.setStyleSheet("""
            QDialog { background-color: #23272e; color: #f3f3f3; }
            QGroupBox { border: 1px solid #444; border-radius: 6px; margin-top: 10px; padding: 10px; }
            QGroupBox:title { subcontrol-origin: margin; left: 10px; padding: 0 4px 0 4px; color: #81d4fa; font-size: 14px; font-weight: bold; }
            QLabel { color: #f3f3f3; }
            QPushButton { background:#3a3f4b; color:#f3f3f3;
                          border-radius:6px; padding:8px 15px;
                          font-weight:bold; }
            QPushButton:hover { background:#4a4f5b; }
            QCheckBox { color: #f3f3f3; }
            QCheckBox::indicator { width: 16px; height: 16px; }
            QCheckBox::indicator:unchecked { background-color: #2d323b; border: 1px solid #444; }
            QCheckBox::indicator:checked { background-color: #4fc3f7; border: 1px solid #444; }
        """)
        
        self._build_ui()
    
    def _build_ui(self):
        """Build the dialog UI"""
        layout = QVBoxLayout(self)
        
        # Enable/disable checkbox
        self.enable_checkbox = QCheckBox("Enable Default Values")
        self.enable_checkbox.setChecked(default_values.is_enabled())
        self.enable_checkbox.toggled.connect(self._toggle_enabled)
        layout.addWidget(self.enable_checkbox)
        
        # Current default values group
        values_group = QGroupBox("Current Default Values")
        values_layout = QGridLayout()
        values_group.setLayout(values_layout)
        
        # Display current default values
        row = 0
        for field, label_text in [
            ('transaction_name', 'Name:'),
            ('transaction_value', 'Value:'),
            ('transaction_type', 'Type:'),
            ('account', 'Account:'),
            ('category', 'Category:'),
            ('sub_category', 'Sub Category:'),
            ('transaction_description', 'Description:'),
            ('transaction_date', 'Date:')
        ]:
            label = QLabel(label_text)
            value = QLabel(str(default_values.get_value(field) or ""))
            value.setStyleSheet("font-weight: bold; color: #4fc3f7;")
            values_layout.addWidget(label, row, 0)
            values_layout.addWidget(value, row, 1)
            row += 1
        
        layout.addWidget(values_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.update_btn = QPushButton("Update from Form")
        self.update_btn.setIcon(QIcon.fromTheme("document-save", QIcon(":/icons/save.png")))
        self.update_btn.clicked.connect(self._update_from_form)
        
        self.clear_btn = QPushButton("Clear Values")
        self.clear_btn.setIcon(QIcon.fromTheme("edit-clear", QIcon(":/icons/clear.png")))
        self.clear_btn.clicked.connect(self._clear_values)
        
        self.close_btn = QPushButton("Close")
        self.close_btn.setIcon(QIcon.fromTheme("window-close", QIcon(":/icons/close.png")))
        self.close_btn.clicked.connect(self.accept)
        
        button_layout.addWidget(self.update_btn)
        button_layout.addWidget(self.clear_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
    
    def _toggle_enabled(self, enabled):
        """Toggle default values enabled/disabled"""
        debug_print('DEFAULT_VALUES', f"Default values {'enabled' if enabled else 'disabled'}")
        if enabled:
            default_values.enable()
        else:
            default_values.disable()
        default_values.save_values()
    
    def _update_from_form(self):
        """Update default values from the current form values"""
        if not self.form_widgets:
            debug_print('DEFAULT_VALUES', "No form widgets provided, cannot update default values")
            return
        
        default_values.update_from_form(self.form_widgets)
        self.accept()  # Close dialog after updating
    
    def _clear_values(self):
        """Clear all default values"""
        default_values.clear_values()
        default_values.save_values()
        self.accept()  # Close dialog after clearing

def show_default_values_dialog(parent=None, form_widgets=None):
    """Show the default values dialog"""
    dialog = DefaultValuesDialog(parent, form_widgets)
    dialog.exec()
