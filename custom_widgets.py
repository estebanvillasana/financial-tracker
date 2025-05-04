# --- START OF FILE custom_widgets.py ---

from PyQt6.QtWidgets import QComboBox

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

        # Calculate arrow position - closer to the edge
        rect = self.rect()
        arrow_x = rect.right() - 8  # 8 pixels from right edge
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
