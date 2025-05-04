# --- START OF FILE custom_widgets.py ---

from PyQt6.QtWidgets import QComboBox, QDateEdit, QCalendarWidget
from PyQt6.QtCore import QDate, Qt, pyqtSignal

class ArrowDateEdit(QDateEdit):
    """Custom QDateEdit with consistent styling that always shows a down arrow
    and prevents unintentional date changes"""

    # Custom signal to emit when date is explicitly selected by user
    dateSelected = pyqtSignal(QDate)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Set calendar popup
        self.setCalendarPopup(True)

        # Store original date to prevent unintentional changes
        self._original_date = self.date()

        # Disable keyboard tracking to prevent accidental changes
        self.setKeyboardTracking(False)

        # Set a property to help with styling
        self.setProperty("hasCustomArrow", True)

        # Basic styling - no border for dropdown button
        self.setStyleSheet("""
            ArrowDateEdit {
                background-color: #2d323b;
                color: #f3f3f3;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 6px;
                padding-right: 15px;
                min-height: 20px;
            }

            ArrowDateEdit::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 12px;
                background: transparent;
                border: none;
            }

            ArrowDateEdit::down-arrow {
                image: none;
                width: 0px;
                height: 0px;
            }
        """)

        # Configure the calendar widget
        self._setup_calendar()

    def _setup_calendar(self):
        """Configure the calendar widget to prevent auto-selection"""
        calendar = self.calendarWidget()
        if calendar:
            # Make sure the calendar shows the original date
            calendar.setSelectedDate(self.date())

            # Connect to the calendar's clicked signal
            calendar.clicked.connect(self._on_date_selected)

    def _on_date_selected(self, date):
        """Handle date selection in the calendar"""
        # Update the date and emit our custom signal
        self.setDate(date)
        self.dateSelected.emit(date)

    def setDate(self, date):
        """Override setDate to store the original date"""
        if self._original_date != date:
            self._original_date = date
        super().setDate(date)

    def paintEvent(self, event):
        # First draw the basic date edit
        super().paintEvent(event)

        # Then draw our custom arrow
        from PyQt6.QtGui import QPainter, QColor, QPen, QPolygon
        from PyQt6.QtCore import QPoint

        painter = QPainter(self)

        # Calculate arrow position - centered in clickable area
        rect = self.rect()
        arrow_width = 20  # Match the width in SpreadsheetDelegate
        arrow_x = int(rect.right() - (arrow_width / 2))  # Center in the clickable area
        arrow_y = rect.center().y()

        # Draw a simple down arrow (triangle) with a very minimal style
        arrow_size = 3  # Tiny arrow

        # Create a polygon for the arrow
        arrow = QPolygon([
            QPoint(arrow_x - arrow_size, int(arrow_y - arrow_size/2)),
            QPoint(arrow_x + arrow_size, int(arrow_y - arrow_size/2)),
            QPoint(arrow_x, arrow_y + arrow_size)
        ])

        # Fill the arrow with a more subtle color
        painter.setPen(QPen(QColor(150, 150, 150)))  # Even lighter gray
        painter.setBrush(QColor(150, 150, 150))  # Even lighter gray fill
        painter.drawPolygon(arrow)

class ArrowComboBox(QComboBox):
    """Custom QComboBox with consistent styling that always shows a down arrow"""
    def __init__(self, parent=None):
        super().__init__(parent)

        # Set a property to help with styling
        self.setProperty("hasCustomArrow", True)

        # Basic styling - no border for dropdown button
        self.setStyleSheet("""
            ArrowComboBox {
                background-color: #2d323b;
                color: #f3f3f3;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 6px;
                padding-right: 15px;
                min-height: 20px;
            }

            ArrowComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 12px;
                background: transparent;
                border: none;
            }

            ArrowComboBox::down-arrow {
                image: none;
                width: 0px;
                height: 0px;
            }
        """)

    def paintEvent(self, event):
        # First draw the basic combobox
        super().paintEvent(event)

        # Then draw our custom arrow
        from PyQt6.QtGui import QPainter, QColor, QPen, QPolygon
        from PyQt6.QtCore import QPoint

        painter = QPainter(self)

        # Calculate arrow position - centered in clickable area
        rect = self.rect()
        arrow_width = 20  # Match the width in SpreadsheetDelegate
        arrow_x = int(rect.right() - (arrow_width / 2))  # Center in the clickable area, convert to int
        arrow_y = rect.center().y()

        # Draw a simple down arrow (triangle) with a very minimal style
        arrow_size = 3  # Tiny arrow

        # Create a polygon for the arrow
        arrow = QPolygon([
            QPoint(arrow_x - arrow_size, int(arrow_y - arrow_size/2)),
            QPoint(arrow_x + arrow_size, int(arrow_y - arrow_size/2)),
            QPoint(arrow_x, arrow_y + arrow_size)
        ])

        # Fill the arrow with a more subtle color
        painter.setPen(QPen(QColor(150, 150, 150)))  # Even lighter gray
        painter.setBrush(QColor(150, 150, 150))  # Even lighter gray fill
        painter.drawPolygon(arrow)
