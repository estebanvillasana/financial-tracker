"""
Column Configuration Module for Financial Tracker

This module defines the configuration for table columns in the Financial Tracker application.
It allows for easy customization of column properties such as:
- Display titles
- Database field names
- Column widths
- Formatting options
- Display order

This makes it easier for non-programmers to customize the UI without modifying core code.
"""

from typing import Dict, List, Any, Optional
from enum import Enum

class ColumnAlignment(Enum):
    """Enum for column alignment options"""
    LEFT = "left"
    RIGHT = "right"
    CENTER = "center"

class ColumnConfig:
    """Configuration for a single column in the transaction table"""
    
    def __init__(
        self,
        db_field: str,
        display_title: str,
        width_percent: int = 0,  # 0 means auto/stretch
        alignment: ColumnAlignment = ColumnAlignment.LEFT,
        format_decimals: int = None,
        show_currency: bool = False,
        visible: bool = True,
        editable: bool = True,
        id_field: str = None,  # Reference to associated ID field
        lookup_source: str = None  # Reference to lookup source for this field
    ):
        self.db_field = db_field
        self.display_title = display_title
        self.width_percent = width_percent
        self.alignment = alignment
        self.format_decimals = format_decimals
        self.show_currency = show_currency
        self.visible = visible
        self.editable = editable
        self.id_field = id_field  # New field for ID reference
        self.lookup_source = lookup_source  # New field for lookup source

# Define the columns configuration
TRANSACTION_COLUMNS = [
    ColumnConfig(
        db_field="transaction_name",
        display_title="Transaction",
        width_percent=10,
    ),
    ColumnConfig(
        db_field="transaction_value",
        display_title="Value",
        width_percent=15,
        alignment=ColumnAlignment.RIGHT,
        format_decimals=2,
        show_currency=True,
    ),
    ColumnConfig(
        db_field="account",
        display_title="Account",
        width_percent=12,
        id_field="account_id",
        lookup_source="_accounts_data"
    ),
    ColumnConfig(
        db_field="transaction_type",
        display_title="Type",
        width_percent=8,
    ),
    ColumnConfig(
        db_field="category",
        display_title="Category",
        width_percent=15,
        id_field="category_id",
        lookup_source="_categories_data"
    ),
    ColumnConfig(
        db_field="sub_category",
        display_title="Sub Category",
        width_percent=15,
        id_field="sub_category_id",
        lookup_source="_subcategories_data"
    ),
    ColumnConfig(
        db_field="transaction_description",
        display_title="Description",
        width_percent=12,
    ),
    ColumnConfig(
        db_field="transaction_date",
        display_title="Date",
        width_percent=12,
    ),
]

# Create a lookup dictionary for easy access by field name
COLUMN_LOOKUP = {col.db_field: col for col in TRANSACTION_COLUMNS}

# List of database fields in display order
DB_FIELDS = [col.db_field for col in TRANSACTION_COLUMNS]

# List of display titles in display order
DISPLAY_TITLES = [col.display_title for col in TRANSACTION_COLUMNS]

# Dictionary mapping display fields to their ID fields
DISPLAY_TO_ID_MAPPING = {col.db_field: col.id_field for col in TRANSACTION_COLUMNS if col.id_field}

# Dictionary mapping ID fields to their display fields
ID_TO_DISPLAY_MAPPING = {col.id_field: col.db_field for col in TRANSACTION_COLUMNS if col.id_field}

def get_column_config(db_field: str) -> Optional[ColumnConfig]:
    """Get column configuration by database field name"""
    return COLUMN_LOOKUP.get(db_field)

def get_visible_columns() -> List[ColumnConfig]:
    """Get only visible columns in display order"""
    return [col for col in TRANSACTION_COLUMNS if col.visible]

def get_id_field(display_field: str) -> Optional[str]:
    """Get the ID field associated with a display field"""
    return DISPLAY_TO_ID_MAPPING.get(display_field)

def get_display_field(id_field: str) -> Optional[str]:
    """Get the display field associated with an ID field"""
    return ID_TO_DISPLAY_MAPPING.get(id_field)
