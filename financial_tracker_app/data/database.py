# --- START OF FILE database.py ---

import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional
from decimal import Decimal # Import Decimal for potential type hints or internal use

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

# Get the absolute path of the directory containing this file (database.py)
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# Define the database file path relative to the current directory
_DB_NAME = 'financial_tracker.db'
_DB_PATH = os.path.join(_CURRENT_DIR, _DB_NAME) # <<< CORRECTED PATH (Points to data directory)

class Database:
    def __init__(self):
        """Initialize the database connection and ensure tables exist."""
        try:
            print(f"Attempting to connect to database at: {_DB_PATH}") # Debug print
            self.conn = sqlite3.connect(_DB_PATH)
            self.conn.row_factory = sqlite3.Row
            # Enable foreign key support
            self.conn.execute("PRAGMA foreign_keys = ON;")
            self.conn.commit() # <<< ADD THIS LINE TO COMMIT PRAGMA
            print("Database connection successful. Foreign keys enabled. Row factory set.") # Debug print
            self.create_tables()
        except sqlite3.Error as e:
            print(f"Database connection error to {_DB_PATH}: {e}")
            self.conn = None # Ensure conn is None if connection fails

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

    def ensure_category(self, category_name: str, category_type: str) -> Optional[int]:
        """Ensure a category exists and return its ID. Returns None on error."""
        if not self.conn: return None
        category_name = category_name.strip()
        if not category_name or category_type not in ['Income', 'Expense']:
            debug_print('FOREIGN_KEYS', f"Invalid input for ensure_category: name='{category_name}', type='{category_type}'")
            return None

        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT id FROM categories WHERE category=? AND type=?", (category_name, category_type))
            result = cursor.fetchone()
            if result:
                return result[0] # Category exists
            else:
                # Category does not exist, insert it
                cursor.execute("INSERT INTO categories (category, type) VALUES (?, ?)", (category_name, category_type))
                self.conn.commit()
                new_id = cursor.lastrowid
                debug_print('FOREIGN_KEYS', f"Category '{category_name}' ({category_type}) added with ID: {new_id}")
                return new_id
        except sqlite3.IntegrityError:
            # Handle integrity error (e.g., constraint violation)
            debug_print('FOREIGN_KEYS', f"Integrity error when ensuring category '{category_name}' ({category_type})")
            self.conn.rollback()
            return None
        except sqlite3.Error as e:
            # Handle other database errors
            debug_print('FOREIGN_KEYS', f"Database error in ensure_category: {e}")
            self.conn.rollback()
            return None

    def ensure_subcategory(self, sub_category_name: str, category_id: int) -> Optional[int]:
        """Ensure a subcategory exists for a given category and return its ID. Returns None on error."""
        if not self.conn: return None
        sub_category_name = sub_category_name.strip()
        if not sub_category_name or category_id is None:
            debug_print('FOREIGN_KEYS', f"Invalid input for ensure_subcategory: name='{sub_category_name}', category_id='{category_id}'")
            return None

        cursor = self.conn.cursor()
        try:
            # Check if the subcategory already exists for this category
            cursor.execute("SELECT id FROM sub_categories WHERE sub_category=? AND category_id=?", (sub_category_name, category_id))
            result = cursor.fetchone()
            if result:
                return result[0] # Subcategory exists
            else:
                # Subcategory does not exist, insert it
                cursor.execute("INSERT INTO sub_categories (sub_category, category_id) VALUES (?, ?)", (sub_category_name, category_id))
                self.conn.commit()
                new_id = cursor.lastrowid
                debug_print('FOREIGN_KEYS', f"Subcategory '{sub_category_name}' added for category ID {category_id} with ID: {new_id}")
                return new_id
        except sqlite3.IntegrityError as e:
            # Could be due to non-existent category_id or UNIQUE constraint violation (though we checked)
            debug_print('FOREIGN_KEYS', f"Integrity error when ensuring subcategory '{sub_category_name}' for category {category_id}: {e}")
            self.conn.rollback()
            # Attempt to fetch again in case of race condition (unlikely in typical use)
            cursor.execute("SELECT id FROM sub_categories WHERE sub_category=? AND category_id=?", (sub_category_name, category_id))
            result = cursor.fetchone()
            return result[0] if result else None
        except sqlite3.Error as e:
            debug_print('FOREIGN_KEYS', f"Database error in ensure_subcategory: {e}")
            self.conn.rollback()
            return None

    def get_accounts(self) -> List[Dict]:
        """Fetch all bank accounts (id, name)."""
        if not self.conn: return []
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id, account FROM bank_accounts ORDER BY account")
            fetched_rows = cursor.fetchall() # <<< Get raw rows
            print(f"DEBUG DB: Fetched {len(fetched_rows)} raw account rows.") # <<< Debug Print
            # Convert Row objects to dictionaries
            accounts = [{'id': row['id'], 'name': row['account']} for row in fetched_rows]
            debug_print('DROPDOWN', f"Fetched {len(accounts)} accounts.")
            return accounts
        except sqlite3.Error as e:
            debug_print('DROPDOWN', f"Error fetching accounts: {e}")
            return []

    def get_categories(self) -> List[Dict]:
        """Fetch all categories (id, name, type)."""
        if not self.conn: return []
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id, category, type FROM categories ORDER BY type, category")
            fetched_rows = cursor.fetchall() # <<< Get raw rows
            print(f"DEBUG DB: Fetched {len(fetched_rows)} raw category rows.") # <<< Debug Print
            # Convert Row objects to dictionaries
            categories = [{'id': row['id'], 'name': row['category'], 'type': row['type']} for row in fetched_rows]
            debug_print('DROPDOWN', f"Fetched {len(categories)} categories.")
            return categories
        except sqlite3.Error as e:
            debug_print('DROPDOWN', f"Error fetching categories: {e}")
            return []

    def get_subcategories(self) -> List[Dict]:
        """Fetch all subcategories (id, name, category_id)."""
        if not self.conn: return []
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id, sub_category, category_id FROM sub_categories ORDER BY category_id, sub_category")
            fetched_rows = cursor.fetchall() # <<< Get raw rows
            print(f"DEBUG DB: Fetched {len(fetched_rows)} raw subcategory rows.") # <<< Debug Print
            # Convert Row objects to dictionaries
            subcategories = [{'id': row['id'], 'name': row['sub_category'], 'category_id': row['category_id']} for row in fetched_rows]
            debug_print('DROPDOWN', f"Fetched {len(subcategories)} subcategories.")
            return subcategories
        except sqlite3.Error as e:
            debug_print('DROPDOWN', f"Error fetching subcategories: {e}")
            return []

    def get_account_currency(self, account_id: int) -> Optional[str]:
        """Fetch the currency code for a given account ID."""
        if not self.conn or account_id is None: return None
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT c.currency_code
                FROM bank_accounts ba
                JOIN currencies c ON ba.currency_id = c.id
                WHERE ba.id = ?
            """, (account_id,))
            result = cursor.fetchone()
            currency_code = result['currency_code'] if result else None
            debug_print('CURRENCY', f"Fetched currency code '{currency_code}' for account ID {account_id}")
            return currency_code
        except sqlite3.Error as e:
            debug_print('CURRENCY', f"Error fetching currency for account ID {account_id}: {e}")
            return None

    def get_all_data_for_gui(self) -> List[Dict]:
        """Fetch all transactions with joined names for GUI display."""
        if not self.conn: return []
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT
                    t.id AS rowid, t.transaction_name, t.transaction_value, -- Use id AS rowid
                    t.account_id, ba.account AS account,
                    t.transaction_type,
                    t.transaction_category AS category_id, c.category AS category, -- Use category_id alias
                    t.transaction_sub_category AS sub_category_id, sc.sub_category AS sub_category, -- Use sub_category_id alias
                    t.transaction_description, t.transaction_date
                FROM transactions t
                LEFT JOIN bank_accounts ba ON t.account_id = ba.id
                LEFT JOIN categories c ON t.transaction_category = c.id
                LEFT JOIN sub_categories sc ON t.transaction_sub_category = sc.id
                ORDER BY t.transaction_date DESC, t.id DESC
            """)
            fetched_rows = cursor.fetchall() # <<< Get raw rows
            print(f"DEBUG DB: Fetched {len(fetched_rows)} raw transaction rows for GUI.") # <<< Debug Print
            # Fetchall returns list of Row objects, convert them to dicts
            data = [dict(row) for row in fetched_rows]
            debug_print('DATA_FETCH', f"Fetched {len(data)} rows for GUI.")
            return data
        except sqlite3.Error as e:
            debug_print('DATA_FETCH', f"Error fetching data for GUI: {e}")
            return []

    def add_transaction(self, name: str, description: str, account_id: int, value: float,
                        type: str, category_id: int, sub_category_id: int, date_str: str) -> Optional[int]:
        """Add a new transaction to the database. Returns the new rowid or None on error."""
        if not self.conn: return None
        # Basic validation (more comprehensive validation should happen in GUI)
        if not all([account_id, value is not None, type, category_id, sub_category_id, date_str]):
             debug_print('FOREIGN_KEYS', f"Missing required fields for add_transaction: account={account_id}, value={value}, type={type}, cat={category_id}, subcat={sub_category_id}, date={date_str}")
             return None

        cursor = self.conn.cursor()
        try:
            # Map category_id/sub_category_id parameters to the correct columns
            cursor.execute('''
                INSERT INTO transactions (
                    transaction_name, transaction_description, account_id,
                    transaction_value, transaction_type, transaction_category,
                    transaction_sub_category, transaction_date
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, description, account_id, value, type, category_id, sub_category_id, date_str))
            self.conn.commit()
            new_rowid = cursor.lastrowid
            debug_print('FOREIGN_KEYS', f"Transaction added with rowid: {new_rowid}")
            return new_rowid
        except sqlite3.IntegrityError as e:
            # Likely due to foreign key constraint violation (invalid account_id, category_id, etc.)
            debug_print('FOREIGN_KEYS', f"Integrity error adding transaction: {e}. Data: name='{name}', acc={account_id}, val={value}, type={type}, cat={category_id}, subcat={sub_category_id}, date={date_str}")
            self.conn.rollback()
            return None
        except sqlite3.Error as e:
            debug_print('FOREIGN_KEYS', f"Database error adding transaction: {e}")
            self.conn.rollback()
            return None

    def update_transaction(self, rowid: int, data: Dict) -> bool:
        """Updates an existing transaction using its rowid."""
        if not self.conn: return False

        set_parts = []
        values = []
        # Map internal keys (like category_id) to DB columns (like transaction_category)
        column_map = {
            'transaction_name': 'transaction_name',
            'transaction_description': 'transaction_description',
            'account_id': 'account_id',
            'transaction_value': 'transaction_value',
            'transaction_type': 'transaction_type',
            'category_id': 'transaction_category', # Map internal key to DB column
            'sub_category_id': 'transaction_sub_category', # Map internal key to DB column
            'transaction_date': 'transaction_date'
        }

        for key, db_col in column_map.items():
            if key in data:
                set_parts.append(f"{db_col} = ?")
                value = data[key]
                # Convert Decimal to float for database
                if isinstance(value, Decimal):
                    values.append(float(value))
                else:
                    values.append(value)

        if not set_parts:
            debug_print('FOREIGN_KEYS', "Warning: No valid columns provided for update_transaction.")
            return False

        values.append(rowid) # Add the rowid for the WHERE clause
        sql = f"UPDATE transactions SET {', '.join(set_parts)} WHERE rowid = ?"

        cursor = self.conn.cursor()
        try:
            cursor.execute(sql, tuple(values))
            self.conn.commit()
            debug_print('FOREIGN_KEYS', f"Updated transaction rowid {rowid}. Rows affected: {cursor.rowcount}")
            return cursor.rowcount > 0 # Return True if at least one row was updated
        except sqlite3.IntegrityError as e:
             debug_print('FOREIGN_KEYS', f"Database Integrity Error updating transaction rowid {rowid}: {e}")
             debug_print('FOREIGN_KEYS', f"  > Data attempted: {data}")
             self.conn.rollback()
             return False
        except sqlite3.Error as e:
            debug_print('FOREIGN_KEYS', f"Database Error updating transaction rowid {rowid}: {e}")
            self.conn.rollback()
            return False

    def delete_transactions(self, rowids: List[int]) -> int:
        """Deletes multiple transactions by their rowids. Returns number of rows deleted."""
        if not self.conn or not rowids:
             return 0

        cursor = self.conn.cursor()
        try:
            placeholders = ','.join('?' * len(rowids))
            # Use rowid for deletion as it's the primary key alias used internally
            sql = f"DELETE FROM transactions WHERE rowid IN ({placeholders})"
            cursor.execute(sql, tuple(rowids))
            deleted_count = cursor.rowcount
            self.conn.commit()
            debug_print('FOREIGN_KEYS', f"Deleted {deleted_count} transaction(s) with rowids: {rowids}")
            return deleted_count
        except sqlite3.Error as e:
            debug_print('FOREIGN_KEYS', f"Database Error deleting transactions: {e}")
            self.conn.rollback()
            return 0

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