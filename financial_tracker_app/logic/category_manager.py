"""
Category manager to centralize handling of special categories like UNCATEGORIZED.
"""

import sqlite3
from typing import Dict, Optional, List, Tuple


class CategoryManager:
    """
    Manages special categories like UNCATEGORIZED centrally to avoid scattered special-case logic.
    """
    
    def __init__(self, db_connection):
        """
        Initialize the category manager with a database connection.
        
        Args:
            db_connection: SQLite database connection
        """
        self.conn = db_connection
        self.special_categories = {
            'UNCATEGORIZED': {
                'Expense': None,  # Will store ID once loaded/created
                'Income': None    # Will store ID once loaded/created
            }
        }
        
        # Cache for regular categories and subcategories
        self._categories_cache = []
        self._subcategories_cache = []
        
        # Load existing special categories
        self._load_special_categories()
    
    def _load_special_categories(self):
        """Load IDs of special categories from the database."""
        try:
            cursor = self.conn.cursor()
            
            # Load UNCATEGORIZED categories for each transaction type
            for category_name, type_dict in self.special_categories.items():
                for transaction_type in type_dict.keys():
                    cursor.execute(
                        "SELECT id FROM categories WHERE category = ? AND type = ?", 
                        (category_name, transaction_type)
                    )
                    result = cursor.fetchone()
                    if result:
                        self.special_categories[category_name][transaction_type] = result[0]
        except sqlite3.Error as e:
            print(f"Error loading special categories: {e}")
    
    def ensure_special_categories(self):
        """Ensure all special categories exist in the database."""
        for name, types in self.special_categories.items():
            for type_name in types.keys():
                if not self.special_categories[name][type_name]:
                    cat_id = self._create_category(name, type_name)
                    if cat_id:
                        self.special_categories[name][type_name] = cat_id
                
                # Ensure each special category has its corresponding subcategory
                cat_id = self.special_categories[name][type_name]
                if cat_id:
                    self.ensure_special_subcategory(name, cat_id)
    
    def _create_category(self, name: str, transaction_type: str) -> Optional[int]:
        """
        Create a category in the database.
        
        Args:
            name: Category name
            transaction_type: 'Expense' or 'Income'
            
        Returns:
            The new category ID or None if creation failed
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT INTO categories (category, type) VALUES (?, ?)",
                (name, transaction_type)
            )
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Error creating category {name} for {transaction_type}: {e}")
            return None
    
    def ensure_special_subcategory(self, name: str, category_id: int) -> Optional[int]:
        """
        Ensure a special subcategory exists for the given category.
        
        Args:
            name: Subcategory name (typically same as the special category name)
            category_id: Parent category ID
            
        Returns:
            The subcategory ID or None if creation failed
        """
        try:
            cursor = self.conn.cursor()
            
            # Check if it already exists
            cursor.execute(
                "SELECT id FROM sub_categories WHERE sub_category = ? AND category_id = ?",
                (name, category_id)
            )
            result = cursor.fetchone()
            if result:
                return result[0]
            
            # Create it if not found
            cursor.execute(
                "INSERT INTO sub_categories (sub_category, category_id) VALUES (?, ?)",
                (name, category_id)
            )
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Error ensuring subcategory {name} for category {category_id}: {e}")
            return None
    
    def get_uncategorized_id(self, transaction_type: str) -> Optional[int]:
        """
        Get the ID of the UNCATEGORIZED category for the given transaction type.
        
        Args:
            transaction_type: 'Expense' or 'Income'
            
        Returns:
            The category ID or None if not found
        """
        if transaction_type in self.special_categories['UNCATEGORIZED']:
            return self.special_categories['UNCATEGORIZED'][transaction_type]
        return None
    
    def get_uncategorized_subcategory_id(self, category_id: int) -> Optional[int]:
        """
        Get the ID of the UNCATEGORIZED subcategory for the given category.
        
        Args:
            category_id: Parent category ID
            
        Returns:
            The subcategory ID or None if not found
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT id FROM sub_categories WHERE sub_category = ? AND category_id = ?",
                ('UNCATEGORIZED', category_id)
            )
            result = cursor.fetchone()
            return result[0] if result else None
        except sqlite3.Error as e:
            print(f"Error getting UNCATEGORIZED subcategory for category {category_id}: {e}")
            return None
    
    def is_uncategorized_category(self, category_id: int) -> bool:
        """Check if a category ID is an UNCATEGORIZED category."""
        for type_dict in self.special_categories['UNCATEGORIZED'].values():
            if category_id == type_dict:
                return True
        return False
    
    def is_uncategorized_subcategory(self, subcategory_id: int) -> bool:
        """Check if a subcategory ID is an UNCATEGORIZED subcategory."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT sub_category FROM sub_categories WHERE id = ?",
                (subcategory_id,)
            )
            result = cursor.fetchone()
            return result and result[0] == 'UNCATEGORIZED'
        except sqlite3.Error as e:
            print(f"Error checking if subcategory {subcategory_id} is UNCATEGORIZED: {e}")
            return False
    
    def get_all_categories(self, refresh: bool = False) -> List[Dict]:
        """
        Get all categories from the database.
        
        Args:
            refresh: Whether to refresh the cache
            
        Returns:
            List of category dictionaries
        """
        if not self._categories_cache or refresh:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT id, category, type FROM categories ORDER BY type, category")
                
                self._categories_cache = [
                    {'id': row[0], 'name': row[1], 'type': row[2]} 
                    for row in cursor.fetchall()
                ]
            except sqlite3.Error as e:
                print(f"Error loading categories: {e}")
                self._categories_cache = []
        
        return self._categories_cache
    
    def get_all_subcategories(self, refresh: bool = False) -> List[Dict]:
        """
        Get all subcategories from the database.
        
        Args:
            refresh: Whether to refresh the cache
            
        Returns:
            List of subcategory dictionaries
        """
        if not self._subcategories_cache or refresh:
            try:
                cursor = self.conn.cursor()
                cursor.execute(
                    "SELECT id, sub_category, category_id FROM sub_categories ORDER BY category_id, sub_category"
                )
                
                self._subcategories_cache = [
                    {'id': row[0], 'name': row[1], 'category_id': row[2]} 
                    for row in cursor.fetchall()
                ]
            except sqlite3.Error as e:
                print(f"Error loading subcategories: {e}")
                self._subcategories_cache = []
        
        return self._subcategories_cache
    
    def get_default_category(self, transaction_type: str) -> Tuple[Optional[int], str]:
        """
        Get the default category ID and name for a transaction type (which is UNCATEGORIZED).
        
        Args:
            transaction_type: 'Expense' or 'Income'
            
        Returns:
            Tuple of (category_id, category_name)
        """
        cat_id = self.get_uncategorized_id(transaction_type)
        return cat_id, 'UNCATEGORIZED'
    
    def get_default_subcategory(self, category_id: int) -> Tuple[Optional[int], str]:
        """
        Get the default subcategory ID and name for a category (which is UNCATEGORIZED).
        
        Args:
            category_id: Parent category ID
            
        Returns:
            Tuple of (subcategory_id, subcategory_name)
        """
        subcat_id = self.get_uncategorized_subcategory_id(category_id)
        return subcat_id, 'UNCATEGORIZED'