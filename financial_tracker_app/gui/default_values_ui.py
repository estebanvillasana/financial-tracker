"""
UI Module for Setting Default Transaction Values
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit,
                             QComboBox, QDateEdit, QPushButton, QDialogButtonBox,
                             QLabel, QWidget)
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QIcon

from financial_tracker_app.logic.default_values import default_values
from financial_tracker_app.gui.custom_widgets import ArrowComboBox, ArrowDateEdit # Use custom widgets
from financial_tracker_app.utils.debug_config import debug_config, debug_print
from decimal import Decimal, InvalidOperation

class DefaultValuesDialog(QDialog):
    """Dialog for setting default transaction values."""

    def __init__(self, parent, form_widgets_ref):
        super().__init__(parent)
        self.setWindowTitle("Set Default Transaction Values")
        self.setWindowIcon(QIcon.fromTheme("preferences-system", QIcon(":/icons/settings.png"))) # Example icon
        self.setMinimumWidth(400)

        self.form_widgets_ref = form_widgets_ref # Reference to main GUI's form widgets
        self.input_widgets = {} # To store widgets created in this dialog

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # Dynamically create input fields based on the main form's widgets
        for field_key, ref_widget in self.form_widgets_ref.items():
            label_text = field_key.replace('_in', '').replace('_', ' ').capitalize() + ":"
            current_default = default_values.get_value(field_key)
            widget = None

            if isinstance(ref_widget, QLineEdit):
                widget = QLineEdit()
                if current_default is not None:
                    # Handle Decimal display
                    if field_key == 'value_in':
                         try: widget.setText(str(Decimal(str(current_default)).quantize(Decimal("0.00"))))
                         except (InvalidOperation, TypeError, ValueError): pass # Leave blank on error
                    else: widget.setText(str(current_default))
                widget.setPlaceholderText(f"Default {label_text.replace(':', '')} (optional)")

            elif isinstance(ref_widget, ArrowComboBox): # Use ArrowComboBox
                widget = ArrowComboBox() # Create a new instance for the dialog
                # Copy items and data from the reference widget
                for i in range(ref_widget.count()):
                    widget.addItem(ref_widget.itemText(i), ref_widget.itemData(i))

                # Add a "None" option at the beginning to allow clearing the default
                widget.insertItem(0, "(No Default)", userData=None)

                # Set current selection based on stored default
                selected_index = 0 # Default to "(No Default)"
                if current_default is not None:
                    if field_key == 'type_in': # Type stored as text
                        found_idx = widget.findText(str(current_default))
                        if found_idx != -1: selected_index = found_idx
                    else: # Account/Cat/Subcat stored as ID
                        try:
                            value_id = int(current_default)
                            found_idx = widget.findData(value_id)
                            if found_idx != -1: selected_index = found_idx
                        except (ValueError, TypeError): pass # Ignore invalid stored ID format
                widget.setCurrentIndex(selected_index)

            elif isinstance(ref_widget, ArrowDateEdit): # Use ArrowDateEdit
                widget = ArrowDateEdit() # Create a new instance
                widget.setDisplayFormat("dd MMM yyyy")
                widget.setCalendarPopup(True)
                # Add a way to clear the date default? Maybe a checkbox?
                # For simplicity, let's assume setting a date is always desired if the dialog is used.
                # We can add a "Clear Date Default" button later if needed.
                if current_default is not None:
                    date = QDate.fromString(str(current_default), "yyyy-MM-dd")
                    if date.isValid():
                        widget.setDate(date)
                    else:
                        widget.setDate(QDate.currentDate()) # Fallback
                else:
                    widget.setDate(QDate.currentDate()) # Default to today if no default set

            if widget:
                self.input_widgets[field_key] = widget
                form_layout.addRow(QLabel(label_text), widget)

        layout.addLayout(form_layout)

        # Standard buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def accept(self):
        """Save the defaults when OK is clicked."""
        debug_print('DEFAULTS', "Saving defaults from dialog...")
        for field_key, widget in self.input_widgets.items():
            value = None
            if isinstance(widget, QLineEdit):
                value = widget.text().strip()
                if not value: # Treat empty string as clearing the default
                    value = None
                # Ensure value is stored correctly (string for Decimal)
                elif field_key == 'value_in':
                     try:
                         # Validate it's a number, but store as string
                         Decimal(value)
                     except InvalidOperation:
                         debug_print('DEFAULTS', f"Invalid decimal format '{value}' for '{field_key}', not saving default.")
                         value = default_values.get_value(field_key) # Keep old value on error

            elif isinstance(widget, QComboBox):
                index = widget.currentIndex()
                if index > 0: # Index 0 is "(No Default)"
                    if field_key == 'type_in':
                        value = widget.currentText() # Store text
                    else:
                        value = widget.currentData() # Store ID (already int or None)
                else:
                    value = None # Clear default

            elif isinstance(widget, QDateEdit):
                value = widget.date().toString("yyyy-MM-dd") # Store ISO string

            # Only set if the value is determined (could be None to clear)
            if value is not None or isinstance(widget, QLineEdit) or isinstance(widget, QComboBox):
                 default_values.set_value(field_key, value)

        super().accept() # Close the dialog

def show_default_values_dialog(parent, form_widgets_ref):
    """Create and show the Default Values dialog."""
    dialog = DefaultValuesDialog(parent, form_widgets_ref)
    return dialog.exec()
