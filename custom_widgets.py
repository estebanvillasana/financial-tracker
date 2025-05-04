# --- START OF FILE custom_widgets.py ---

from PyQt6.QtWidgets import QComboBox

class ArrowComboBox(QComboBox):
    """Custom QComboBox with consistent styling that always shows a down arrow"""
    def __init__(self, parent=None):
        super().__init__(parent)

        # Set a property to help with styling
        self.setProperty("hasCustomArrow", True)

        # Basic styling
        self.setStyleSheet("""
            ArrowComboBox {
                background-color: #2d323b;
                color: #f3f3f3;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 6px;
                padding-right: 28px;
                min-height: 20px;
            }

            ArrowComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border-left: 1px solid #555;
                background: transparent;
            }

            ArrowComboBox::down-arrow {
                image: none;
                width: 14px;
                height: 14px;
            }
        """)

    def paintEvent(self, event):
        # First draw the basic combobox
        super().paintEvent(event)

        # Then draw our custom arrow
        from PyQt6.QtGui import QPainter, QColor, QPen, QPolygon
        from PyQt6.QtCore import QPoint

        painter = QPainter(self)
        painter.setPen(QPen(QColor(255, 255, 255)))  # White color

        # Calculate arrow position
        rect = self.rect()
        arrow_x = rect.right() - 15  # 15 pixels from right edge
        arrow_y = rect.center().y()

        # Draw a simple down arrow (triangle)
        arrow_size = 5

        # Create a polygon for the arrow
        arrow = QPolygon([
            QPoint(arrow_x - arrow_size, arrow_y - arrow_size),
            QPoint(arrow_x + arrow_size, arrow_y - arrow_size),
            QPoint(arrow_x, arrow_y + arrow_size)
        ])

        # Fill the arrow
        painter.setBrush(QColor(255, 255, 255))  # White fill
        painter.drawPolygon(arrow)
