"""
Field Mapping Utilities

This module provides utility functions for mapping between display fields and ID fields,
and for looking up values in data sources.
"""

from typing import Any, Dict, List, Optional, Union
from financial_tracker_app.data.column_config import get_id_field, get_display_field, get_column_config

def get_id_for_name(name: str, data_source: List[Dict[str, Any]], 
                   name_field: str = "name", id_field: str = "id") -> Optional[int]:
    """
    Look up an ID for a given name in a data source.
    
    Args:
        name: The name to look up
        data_source: The list of dictionaries to search in
        name_field: The field containing names (default: "name")
        id_field: The field containing IDs (default: "id")
        
    Returns:
        The ID if found, None otherwise
    """
    if name is None:
        return None
        
    for item in data_source:
        if item.get(name_field) == name:
            return item.get(id_field)
    return None

def get_name_for_id(id_value: Union[int, str], data_source: List[Dict[str, Any]],
                   name_field: str = "name", id_field: str = "id") -> Optional[str]:
    """
    Look up a name for a given ID in a data source.
    
    Args:
        id_value: The ID to look up
        data_source: The list of dictionaries to search in
        name_field: The field containing names (default: "name")
        id_field: The field containing IDs (default: "id")
        
    Returns:
        The name if found, None otherwise
    """
    if id_value is None:
        return None
        
    try:
        # Convert to int if it's a string containing a number
        if isinstance(id_value, str) and id_value.isdigit():
            id_value = int(id_value)
    except (ValueError, TypeError):
        pass
        
    for item in data_source:
        if item.get(id_field) == id_value:
            return item.get(name_field)
    return None

def ensure_id_field(row_data: Dict[str, Any], display_field: str, 
                   data_source: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Ensure the ID field is populated based on the display field.
    
    Args:
        row_data: The row data to update
        display_field: The display field name (e.g., "account")
        data_source: The data source to use for lookup
        
    Returns:
        The updated row data
    """
    id_field = get_id_field(display_field)
    if not id_field:
        return row_data  # No mapping exists
    
    # If ID field is missing but we have the display value
    if id_field not in row_data or row_data[id_field] is None:
        if display_field in row_data and row_data[display_field]:
            row_data[id_field] = get_id_for_name(
                row_data[display_field], 
                data_source
            )
    
    return row_data

def ensure_display_field(row_data: Dict[str, Any], id_field: str, 
                        data_source: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Ensure the display field is populated based on the ID field.
    
    Args:
        row_data: The row data to update
        id_field: The ID field name (e.g., "account_id")
        data_source: The data source to use for lookup
        
    Returns:
        The updated row data
    """
    display_field = get_display_field(id_field)
    if not display_field:
        return row_data  # No mapping exists
    
    # If display field is missing but we have the ID value
    if display_field not in row_data or not row_data[display_field]:
        if id_field in row_data and row_data[id_field] is not None:
            row_data[display_field] = get_name_for_id(
                row_data[id_field], 
                data_source
            )
    
    return row_data

def get_data_source_for_field(app_instance, field_name: str) -> List[Dict[str, Any]]:
    """
    Get the appropriate data source for a field.
    
    Args:
        app_instance: The application instance containing the data sources
        field_name: The field name to get the data source for
        
    Returns:
        The data source list
    """
    col_config = get_column_config(field_name)
    if not col_config or not col_config.lookup_source:
        return []
        
    data_source = getattr(app_instance, col_config.lookup_source, [])
    return data_source

def ensure_related_fields(app_instance, row_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure all related fields (display <-> ID) are populated.
    
    Args:
        app_instance: The application instance containing the data sources
        row_data: The row data to update
        
    Returns:
        The updated row data
    """
    # Fields that have ID relationships
    related_fields = ["account", "category", "sub_category"]
    
    for field in related_fields:
        data_source = get_data_source_for_field(app_instance, field)
        
        # Ensure ID is populated from display name
        row_data = ensure_id_field(row_data, field, data_source)
        
        # Ensure display name is populated from ID
        id_field = get_id_field(field)
        if id_field:
            row_data = ensure_display_field(row_data, id_field, data_source)
    
    return row_data
