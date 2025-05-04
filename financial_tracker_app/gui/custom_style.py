# --- START OF FILE custom_style.py ---

from PyQt6.QtWidgets import QProxyStyle

class CustomProxyStyle(QProxyStyle):
    """
    A custom proxy style that doesn't override any drawing behavior.
    We're using CSS styling instead for consistent appearance.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

# --- END OF FILE custom_style.py ---