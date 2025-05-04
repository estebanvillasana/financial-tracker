# --- START OF FILE custom_style.py ---

from PyQt6.QtWidgets import QProxyStyle, QStyle, QStyleOption, QStyleOptionComboBox, QStyleOptionComplex
from PyQt6.QtGui import QPainter, QColor, QPolygon
from PyQt6.QtCore import QPoint, QRect, Qt

class CustomProxyStyle(QProxyStyle):
    def drawPrimitive(self, element, option, painter, widget=None):
        # --- REMOVED ---
        # (Original commented-out code remains commented out)
        # if element == QStyle.PrimitiveElement.PE_IndicatorArrowDown:
        #     # Draw a white down arrow
        #     rect = option.rect
        #     painter.save()
        #     painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        #     painter.setPen(Qt.PenStyle.NoPen)
        #     painter.setBrush(QColor('#ffffff'))
        #     # Draw a triangle pointing down
        #     w, h = rect.width(), rect.height()
        #     cx, cy = rect.center().x(), rect.center().y()
        #     arrow = QPolygon([
        #         QPoint(cx - w//4, cy - h//8),
        #         QPoint(cx + w//4, cy - h//8),
        #         QPoint(cx, cy + h//4)
        #     ])
        #     painter.drawPolygon(arrow)
        #     painter.restore()
        # else:
        #     super().drawPrimitive(element, option, painter, widget)
        # --- END REMOVED ---

        # --- REPLACEMENT ---
        # Simply call the base implementation for all primitive elements.
        # The stylesheet (in expense_tracker_gui.py) handles the arrow styling using CSS-like rules.
        # This proxy style currently doesn't override any drawing behaviour.
        super().drawPrimitive(element, option, painter, widget)

    # You could add other overrides here if needed, e.g., for drawControl or drawComplexControl
    # but for now, it just acts as a standard proxy.

# --- END OF FILE custom_style.py ---