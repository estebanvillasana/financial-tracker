# --- START OF FILE database.py ---

import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional, Any, Union
from decimal import Decimal # Import Decimal for potential type hints or internal use
from financial_tracker_app.logic.category_manager import CategoryManager

# --- Updated Imports ---
# Import debug configuration using the new path
try:
    from financial_tracker_app.utils.debug_config import debug_config, debug_print
except ImportError:
    # Fallback if debug_config.py doesn't exist yet
    class DummyDebugConfig:
        def is_enabled(self, category):
            return False
    debug_config = DummyDebugConfig()
    def debug_print(category, message):
        pass
# --- End Updated Imports ---

# Define a consistent date format string
DB_DATE_FORMAT = "%Y-%m-%d" # Using only date part based on GUI usage

class Database:
    def __init__(self, db_path=None):
        # Set the database path
        if db_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(current_dir, 'financial_tracker.db')
        
        # Store the path for potential backup operations
        self.db_path = db_path
        
        # Connect to the database
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON") # Enable foreign key constraints
        
        # Initialize database if tables don't exist
        self.create_tables()
        
        # Create category manager instance
        self.category_manager = CategoryManager(self.conn)
        
        # Ensure special categories exist
        self.category_manager.ensure_special_categories()

    def create_tables(self):
        """Create necessary tables if they don't exist."""
        if not self.conn:
            debug_print('FOREIGN_KEYS', "Error: No database connection available for creating tables.")
            return

        cursor = self.conn.cursor()
        try:
            # --- Currencies Table ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS currencies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    currency TEXT NOT NULL,             -- e.g., US Dollar
                    currency_code TEXT UNIQUE NOT NULL, -- e.g., USD
                    currency_symbol TEXT                -- e.g., $
                )
            """)

            # --- Bank Accounts Table ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bank_accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account TEXT NOT NULL UNIQUE,     -- Added UNIQUE constraint for account name
                    account_type TEXT NOT NULL,       -- e.g., Bank account, Credit Card
                    account_details TEXT,             -- e.g., Last 4 digits ****1234
                    currency_id INTEGER NOT NULL,
                    FOREIGN KEY (currency_id) REFERENCES currencies (id) ON DELETE RESTRICT -- Prevent deleting used currency
                )
            """)

            # --- Categories Table ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    type TEXT NOT NULL CHECK(type IN ('Income', 'Expense')), -- Type constraint
                    UNIQUE(category, type) -- Ensure category name is unique per type
                )
            """)

            # --- Sub Categories Table ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sub_categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sub_category TEXT NOT NULL,
                    category_id INTEGER NOT NULL,
                    FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE CASCADE, -- Cascade delete if category is removed
                    UNIQUE(category_id, sub_category) -- Ensure subcategory is unique within its parent category
                )
            """)

            # --- Transactions Table ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_name TEXT,             -- Optional name/title
                    transaction_description TEXT,
                    account_id INTEGER NOT NULL,
                    transaction_value REAL NOT NULL,   -- Amount (REAL is suitable for SQLite floats)
                    transaction_type TEXT NOT NULL CHECK(transaction_type IN ('Income', 'Expense')),
                    transaction_category INTEGER NOT NULL, -- Reverted name
                    transaction_sub_category INTEGER NOT NULL, -- Reverted name
                    transaction_date TEXT NOT NULL,    -- Store as ISO format string 'YYYY-MM-DD'
                    FOREIGN KEY (account_id) REFERENCES bank_accounts (id) ON DELETE RESTRICT,
                    FOREIGN KEY (transaction_category) REFERENCES categories (id) ON DELETE RESTRICT, -- Reverted name
                    FOREIGN KEY (transaction_sub_category) REFERENCES sub_categories (id) ON DELETE RESTRICT, -- Reverted name
                    -- Add check constraint for date format to enforce ISO format 'YYYY-MM-DD'
                    CHECK(transaction_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]')
                )
            """)
            # Create indexes for faster lookups on foreign keys and dates
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_account ON transactions (account_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions (transaction_category);") # Reverted name
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_subcategory ON transactions (transaction_sub_category);") # Reverted name
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions (transaction_date);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_subcat_category ON sub_categories (category_id);")


            # --- Budgets Table (Keep schema as is for now) ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS budgets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_id INTEGER,
                    sub_category_id INTEGER, -- Maybe budget by subcategory?
                    amount REAL NOT NULL,
                    month TEXT NOT NULL,     -- e.g., 'YYYY-MM'
                    FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE CASCADE,
                    FOREIGN KEY (sub_category_id) REFERENCES sub_categories(id) ON DELETE CASCADE
                )
            """)

            self.conn.commit()
        except sqlite3.Error as e:
            debug_print('FOREIGN_KEYS', f"Error creating/ensuring tables: {e}")
            if self.conn:
                 self.conn.rollback() # Rollback any partial changes if error occurs

    def ensure_category(self, category_name: str, transaction_type: str = 'Expense') -> Optional[int]:
        """
        Ensure a category exists in the database.
        
        Args:
            category_name: Name of the category to ensure exists
            transaction_type: 'Expense' or 'Income'
            
        Returns:
            The category ID if found or created, None on error
        """
        # If this is UNCATEGORIZED, delegate to category manager
        if category_name == 'UNCATEGORIZED':
            cat_id = self.category_manager.get_uncategorized_id(transaction_type)
            if cat_id:
                return cat_id
            # If not found, let category manager create it
            self.category_manager.ensure_special_categories()
            return self.category_manager.get_uncategorized_id(transaction_type)
        
        # For regular categories, use the existing logic
        try:
            cursor = self.conn.cursor()
            
            # Check if the category already exists for this type
            cursor.execute(
                "SELECT id FROM categories WHERE category = ? AND type = ?", 
                (category_name, transaction_type)
            )
            result = cursor.fetchone()
            if result:
                return result[0]
            
            # Create the category if it doesn't exist
            cursor.execute(
                "INSERT INTO categories (category, type) VALUES (?, ?)",
                (category_name, transaction_type)
            )
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Error ensuring category {category_name}: {e}")
            if self.conn.in_transaction:
                self.conn.rollback()
            return None

    def ensure_subcategory(self, subcategory_name: str, category_id: int) -> Optional[int]:
        """
        Ensure a subcategory exists in the database.
        
        Args:
            subcategory_name: Name of the subcategory to ensure exists
            category_id: Parent category ID
            
        Returns:
            The subcategory ID if found or created, None on error
        """
        # If this is UNCATEGORIZED, delegate to category manager
        if subcategory_name == 'UNCATEGORIZED':
            return self.category_manager.ensure_special_subcategory(subcategory_name, category_id)
        
        # For regular subcategories, use the existing logic
        try:
            cursor = self.conn.cursor()
            
            # Check if the subcategory already exists
            cursor.execute(
                "SELECT id FROM sub_categories WHERE sub_category = ? AND category_id = ?",
                (subcategory_name, category_id)
            )
            result = cursor.fetchone()
            if result:
                return result[0]
            
            # Create the subcategory if it doesn't exist
            cursor.execute(
                "INSERT INTO sub_categories (sub_category, category_id) VALUES (?, ?)",
                (subcategory_name, category_id)
            )
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Error ensuring subcategory {subcategory_name}: {e}")
            if self.conn.in_transaction:
                self.conn.rollback()
            return None

    def get_default_category_id(self, transaction_type: str) -> Optional[int]:
        """Get the default category ID for a transaction type (UNCATEGORIZED)."""
        cat_id, _ = self.category_manager.get_default_category(transaction_type)
        return cat_id
    
    def get_default_subcategory_id(self, category_id: int) -> Optional[int]:
        """Get the default subcategory ID for a category (UNCATEGORIZED)."""
        subcat_id, _ = self.category_manager.get_default_subcategory(category_id)
        return subcat_id

    def get_account_currency(self, account_id):
        """
        Get the currency information for a specific bank account.
        
        Args:
            account_id: The ID of the bank account
            
        Returns:
            Dictionary with currency information including 'currency', 'currency_code', and 'currency_symbol'
            or None if the account or its currency does not exist
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT c.currency, c.currency_code, c.currency_symbol
                FROM bank_accounts ba
                JOIN currencies c ON ba.currency_id = c.id
                WHERE ba.id = ?
            """, (account_id,))
            result = cursor.fetchone()
            
            if result:
                return {
                    'currency': result[0],
                    'currency_code': result[1],
                    'currency_symbol': result[2] or '$'  # Default to $ if no symbol is stored
                }
            return None
        except sqlite3.Error as e:
            debug_print('DB_ERROR', f"Error getting currency for account {account_id}: {e}")
            return {'currency': 'US Dollar', 'currency_code': 'USD', 'currency_symbol': '$'}  # Default fallback

    def close(self):
        """Close the database connection."""
        if self.conn:
            try:
                self.conn.close()
                debug_print('FOREIGN_KEYS', "Database connection closed successfully.")
                self.conn = None
            except sqlite3.Error as e:
                debug_print('FOREIGN_KEYS', f"Error closing database connection: {e}")

# --- END OF FILE database.py ---