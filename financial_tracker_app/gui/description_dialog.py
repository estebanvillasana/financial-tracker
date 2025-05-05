"""
Dialog for editing multi-line descriptions
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTextEdit, 
                            QDialogButtonBox, QLabel, QHBoxLayout)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

class DescriptionDialog(QDialog):
    """Dialog for editing multi-line descriptions."""

    def __init__(self, parent=None, initial_text=""):
        super().__init__(parent)
        self.setWindowTitle("Edit Description")
        self.setWindowIcon(QIcon.fromTheme("edit-rename", QIcon(":/icons/edit.png")))
        self.setMinimumWidth(400)
        self.setMinimumHeight(250)

        layout = QVBoxLayout(self)
        
        # Add instructions
        instructions = QLabel("Enter your description below. Use Shift+Enter for line breaks.")
        instructions.setStyleSheet("color: #a0a0a0; font-style: italic;")
        layout.addWidget(instructions)
        
        # Text editor
        self.text_edit = QTextEdit()
        self.text_edit.setText(initial_text)
        self.text_edit.setStyleSheet("""
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
        layout.addWidget(self.text_edit)
        
        # Standard buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | 
                                     QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        # Set focus to the text edit
        self.text_edit.setFocus()
    
    def get_text(self):
        """Return the edited text."""
        return self.text_edit.toPlainText()

def show_description_dialog(parent, initial_text=""):
    """Show the description dialog and return the edited text if accepted."""
    dialog = DescriptionDialog(parent, initial_text)
    result = dialog.exec()
    
    if result == QDialog.DialogCode.Accepted:
        return dialog.get_text()
    return None  # Return None if canceled
