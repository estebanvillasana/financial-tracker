# --- START OF FILE custom_widgets.py ---

from PyQt6.QtWidgets import QComboBox
from PyQt6.QtCore import QRect, QPoint
from PyQt6.QtGui import QPainter, QColor, QPolygon

class ArrowComboBox(QComboBox):
    """Custom QComboBox that draws its own arrow"""
    def __init__(self, parent=None):
        super().__init__(parent)
        
    def paintEvent(self, event):
        # Call the base class paintEvent to draw the basic combobox
        super().paintEvent(event)
        
        # Draw our own arrow
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Define the arrow area
        rect = self.rect()
        arrow_rect = QRect(rect.right() - 20, rect.top(), 20, rect.height())
        
        # Draw the arrow
        painter.setPen(QColor("white"))
        painter.setBrush(QColor("white"))
        
        # Create a triangle pointing down
        points = [
            QPoint(arrow_rect.center().x(), arrow_rect.center().y() + 3),
            QPoint(arrow_rect.center().x() - 5, arrow_rect.center().y() - 3),
            QPoint(arrow_rect.center().x() + 5, arrow_rect.center().y() - 3)
        ]
        
        # Draw the triangle
        painter.drawPolygon(QPolygon(points))
