# --- START OF FILE database.py ---

import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
from decimal import Decimal # Import Decimal for potential type hints or internal use

# Import debug configuration
try:
    from debug_config import debug_config, debug_print
except ImportError:
    # Fallback if debug_config.py doesn't exist yet
    class DummyDebugConfig:
        def is_enabled(self, category):
            return False
    debug_config = DummyDebugConfig()
    def debug_print(category, message):
        pass

# Define a consistent date format string
DB_DATE_FORMAT = "%Y-%m-%d" # Using only date part based on GUI usage

class Database:
    def __init__(self, db_name: str = "financial_tracker.db"):
        """Initializes the database connection and ensures tables exist."""
        self.db_name = db_name
        self.conn = None # Initialize conn to None
        try:
            self.conn = sqlite3.connect(db_name, detect_types=sqlite3.PARSE_DECLTYPES)
            # Enable foreign key support
            self.conn.execute("PRAGMA foreign_keys = ON;")
            # Set isolation level for better transaction control (optional but good practice)
            # self.conn.isolation_level = None # Autocommit mode (less common for apps)
            # Default: deferred transactions (BEGIN issued automatically)
            self.conn.row_factory = sqlite3.Row # Access columns by name
            debug_print('FOREIGN_KEYS', f"Database connection opened: {db_name}")
            self.create_tables()
            self.insert_default_data()
        except sqlite3.Error as e:
            debug_print('FOREIGN_KEYS', f"FATAL DATABASE ERROR during initialization: {e}")
            # Optionally re-raise or handle more gracefully depending on application needs
            # raise # Re-raise the exception to signal failure

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
            # print("Database tables created/ensured.") # Less verbose output
        except sqlite3.Error as e:
            debug_print('FOREIGN_KEYS', f"Error creating/ensuring tables: {e}")
            if self.conn:
                 self.conn.rollback() # Rollback any partial changes if error occurs

    def insert_default_data(self):
        """Insert essential default data like default currency and categories."""
        if not self.conn:
            debug_print('FOREIGN_KEYS', "Error: No database connection available for inserting default data.")
            return

        cursor = self.conn.cursor()
        try:
            # --- Default Currency ---
            cursor.execute("INSERT OR IGNORE INTO currencies (currency, currency_code, currency_symbol) VALUES (?, ?, ?)",
                           ('US Dollar', 'USD', '$'))

            # --- Default Categories ---
            # Ensure these exist and get their IDs
            uncategorized_expense_id = self.ensure_category('UNCATEGORIZED', 'Expense')
            uncategorized_income_id = self.ensure_category('UNCATEGORIZED', 'Income')

            # --- Default Subcategories ---
            if uncategorized_expense_id:
                self.ensure_subcategory('UNCATEGORIZED', uncategorized_expense_id)
            else:
                 debug_print('SUBCATEGORY', "Warning: Could not find/create 'UNCATEGORIZED' Expense category for default subcategory.")

            if uncategorized_income_id:
                self.ensure_subcategory('UNCATEGORIZED', uncategorized_income_id)
            else:
                 debug_print('SUBCATEGORY', "Warning: Could not find/create 'UNCATEGORIZED' Income category for default subcategory.")


            # --- (Optional) Default 'Cash' Bank Account ---
            # cursor.execute("SELECT id FROM currencies WHERE currency_code = ?", ('USD',))
            # usd_id_row = cursor.fetchone()
            # if usd_id_row:
            #     usd_id = usd_id_row['id'] # Access by name due to row_factory
            #     # Check if 'Cash' account already exists before inserting
            #     cursor.execute("SELECT id FROM bank_accounts WHERE account = ?", ('Cash',))
            #     cash_exists = cursor.fetchone()
            #     if not cash_exists:
            #         cursor.execute("INSERT INTO bank_accounts (account, account_type, currency_id) VALUES (?, ?, ?)",
            #                        ('Cash', 'Cash', usd_id))


            self.conn.commit()
            # print("Default data inserted/ensured.") # Less verbose

        except sqlite3.Error as e:
            debug_print('FOREIGN_KEYS', f"Error inserting default data: {e}")
            self.conn.rollback()

    def add_transaction(
        self,
        name: Optional[str],
        description: Optional[str],
        account_id: int,
        value: float, # Keep as float for REAL column type
        type: str,
        category_id: int, # Keep param name for compatibility with GUI call
        sub_category_id: int, # Keep param name for compatibility with GUI call
        date_str: str # Expects 'YYYY-MM-DD'
    ) -> Optional[int]: # Return new rowid or None
        """Add a new transaction to the database."""
        if not self.conn:
            debug_print('FOREIGN_KEYS', "Error: No database connection available for adding transaction.")
            return None

        # Basic validation of required IDs passed as parameters
        if account_id is None or category_id is None or sub_category_id is None:
            debug_print('FOREIGN_KEYS', f"Error adding transaction: Missing required ID(s) - Account: {account_id}, Category: {category_id}, SubCategory: {sub_category_id}")
            return None

        # Validate date format (basic check)
        try:
            datetime.strptime(date_str, DB_DATE_FORMAT)
        except ValueError:
            debug_print('FOREIGN_KEYS', f"Error adding transaction: Invalid date format '{date_str}'. Expected 'YYYY-MM-DD'.")
            return None

        cursor = self.conn.cursor()

        # Check if category is UNCATEGORIZED, if so, ensure subcategory is also UNCATEGORIZED
        try:
            # Check if this is an UNCATEGORIZED category
            cursor.execute("SELECT category FROM categories WHERE id = ?", (category_id,))
            result = cursor.fetchone()
            if result and result['category'] == 'UNCATEGORIZED':
                # Find UNCATEGORIZED subcategory for this category
                cursor.execute("SELECT id FROM sub_categories WHERE category_id = ? AND sub_category = 'UNCATEGORIZED'", (category_id,))
                subcat_result = cursor.fetchone()
                if subcat_result:
                    # Set subcategory to UNCATEGORIZED
                    sub_category_id = subcat_result['id']
                    debug_print('SUBCATEGORY', f"Category is UNCATEGORIZED, setting subcategory to UNCATEGORIZED (ID: {sub_category_id})")
                else:
                    # Create UNCATEGORIZED subcategory if it doesn't exist
                    uncat_subcat_id = self.ensure_subcategory('UNCATEGORIZED', category_id)
                    if uncat_subcat_id:
                        sub_category_id = uncat_subcat_id
                        debug_print('SUBCATEGORY', f"Created and set UNCATEGORIZED subcategory (ID: {uncat_subcat_id}) for UNCATEGORIZED category")
        except sqlite3.Error as e:
            debug_print('SUBCATEGORY', f"Error checking category for UNCATEGORIZED: {e}")

        try:
             # Use reverted column names in the INSERT statement
            cursor.execute("""
                INSERT INTO transactions (
                    transaction_name, transaction_description, account_id, transaction_value,
                    transaction_type, transaction_category, transaction_sub_category, transaction_date
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                name if name else None, # Store empty strings as NULL
                description if description else None,
                account_id,
                value, # Pass float directly
                type,
                category_id,         # Use the passed category_id value here for the transaction_category column
                sub_category_id,     # Use the passed sub_category_id value here for the transaction_sub_category column
                date_str
            ))
            self.conn.commit()
            new_rowid = cursor.lastrowid
            # print(f"Transaction added with rowid: {new_rowid}") # Less verbose
            return new_rowid
        except sqlite3.IntegrityError as e:
             # This likely means a FOREIGN KEY constraint failed (e.g., invalid account_id, category_id)
             debug_print('FOREIGN_KEYS', f"Database Integrity Error adding transaction: {e}")
             debug_print('FOREIGN_KEYS', f"  > Data attempted: AccID={account_id}, CatID={category_id}, SubCatID={sub_category_id}, Type={type}, Date={date_str}")
             # Check if the referenced IDs actually exist (using the parameter values)
             self.check_foreign_keys(cursor, account_id, category_id, sub_category_id)
             self.conn.rollback() # Rollback on error
             return None
        except sqlite3.Error as e:
            debug_print('FOREIGN_KEYS', f"General Database Error adding transaction: {e}")
            self.conn.rollback() # Rollback on error
            return None

    def check_foreign_keys(self, cursor, account_id, category_id, sub_category_id):
        """Helper to check if foreign key IDs exist (for debugging IntegrityError)."""
        try:
            cursor.execute("SELECT 1 FROM bank_accounts WHERE id = ?", (account_id,))
            if not cursor.fetchone(): debug_print('FOREIGN_KEYS', f"  > Debug FK Check: Account ID {account_id} does NOT exist.")
            # Check against categories table using the category_id parameter
            cursor.execute("SELECT 1 FROM categories WHERE id = ?", (category_id,))
            if not cursor.fetchone(): debug_print('FOREIGN_KEYS', f"  > Debug FK Check: Category ID {category_id} does NOT exist.")
            # Check against sub_categories table using the sub_category_id parameter
            cursor.execute("SELECT 1 FROM sub_categories WHERE id = ?", (sub_category_id,))
            if not cursor.fetchone(): debug_print('FOREIGN_KEYS', f"  > Debug FK Check: SubCategory ID {sub_category_id} does NOT exist.")
            # Check subcategory links to category (using the parameter values)
            cursor.execute("SELECT category_id FROM sub_categories WHERE id = ?", (sub_category_id,))
            result = cursor.fetchone()
            if result and result['category_id'] != category_id:
                debug_print('FOREIGN_KEYS', f"  > Debug FK Check: SubCategory ID {sub_category_id} exists but belongs to Category ID {result['category_id']}, not {category_id}.")

        except sqlite3.Error as e:
            debug_print('FOREIGN_KEYS', f"  > Debug FK Check: Error during check: {e}")


    # --- Category/Subcategory Management ---
    def ensure_category(self, category_name: str, category_type: str) -> Optional[int]:
        """Ensure a category exists for the given type, return its ID."""
        if not self.conn: return None
        category_name = category_name.strip()
        if not category_name or category_type not in ('Income', 'Expense'):
            debug_print('SUBCATEGORY', f"Error: Invalid input for ensure_category - Name: '{category_name}', Type: '{category_type}'")
            return None

        cursor = self.conn.cursor()
        try:
            # Use INSERT OR IGNORE and then SELECT to handle concurrency and existence check efficiently
            cursor.execute("INSERT OR IGNORE INTO categories (category, type) VALUES (?, ?)",
                           (category_name, category_type))
            # Fetch the ID whether it was inserted or already existed
            cursor.execute("SELECT id FROM categories WHERE category = ? AND type = ?",
                           (category_name, category_type))
            result = cursor.fetchone()
            if result:
                self.conn.commit() # Commit the INSERT OR IGNORE if it happened
                return result['id'] # Access by name
            else:
                # This should ideally not happen with INSERT OR IGNORE unless there's a severe issue
                debug_print('SUBCATEGORY', f"Error: Failed to find or create category '{category_name}' ({category_type}) after INSERT OR IGNORE.")
                self.conn.rollback() # Rollback potential failed insert
                return None
        except sqlite3.Error as e:
            debug_print('SUBCATEGORY', f"DB Error ensuring category '{category_name}' ({category_type}): {e}")
            self.conn.rollback()
            return None

    def ensure_subcategory(self, subcategory_name: str, category_id: int) -> Optional[int]:
        """Ensure a subcategory exists for the given category_id, return its ID."""
        if not self.conn: return None
        subcategory_name = subcategory_name.strip()
        if not subcategory_name or category_id is None:
            debug_print('SUBCATEGORY', f"Error: Invalid input for ensure_subcategory - Name: '{subcategory_name}', CategoryID: {category_id}")
            return None

        cursor = self.conn.cursor()
        try:
             # First check if the parent category exists
            cursor.execute("SELECT 1 FROM categories WHERE id = ?", (category_id,))
            if not cursor.fetchone():
                debug_print('SUBCATEGORY', f"Error: Cannot ensure subcategory '{subcategory_name}' because parent category ID {category_id} does not exist.")
                return None

            # Now ensure the subcategory exists for the valid parent
            cursor.execute("INSERT OR IGNORE INTO sub_categories (sub_category, category_id) VALUES (?, ?)",
                           (subcategory_name, category_id))
            # Fetch the ID
            cursor.execute("SELECT id FROM sub_categories WHERE sub_category = ? AND category_id = ?",
                           (subcategory_name, category_id))
            result = cursor.fetchone()
            if result:
                self.conn.commit()
                return result['id']
            else:
                 debug_print('SUBCATEGORY', f"Error: Failed to find or create subcategory '{subcategory_name}' for category ID {category_id} after INSERT OR IGNORE.")
                 self.conn.rollback()
                 return None
        except sqlite3.Error as e: # Catches IntegrityError (e.g., parent category deleted concurrently) and others
            debug_print('SUBCATEGORY', f"DB Error ensuring subcategory '{subcategory_name}' for category ID {category_id}: {e}")
            self.conn.rollback()
            return None

    # --- Data Retrieval Methods (Example - Adapt for GUI Needs) ---

    def get_all_data_for_gui(self) -> List[Dict]:
        """Fetches all transaction data with joined names for the main GUI table."""
        if not self.conn: return []
        cursor = self.conn.cursor()
        try:
            # Match the columns needed by _load_transactions in the GUI (reverted names)
            cursor.execute("""
                SELECT
                    t.id AS rowid,                 -- Use alias 'rowid' for consistency
                    t.transaction_name,
                    t.transaction_value,
                    ba.account,                    -- Account Name
                    c.category,                    -- Category Name
                    sc.sub_category,               -- Sub Category Name
                    t.transaction_description,
                    t.transaction_date,            -- Date String 'YYYY-MM-DD'
                    t.transaction_type,            -- Type ('Income'/'Expense')
                    t.account_id,                  -- Account ID
                    t.transaction_category,        -- Category ID (Reverted name)
                    t.transaction_sub_category     -- SubCategory ID (Reverted name)
                FROM transactions t
                LEFT JOIN bank_accounts ba ON t.account_id = ba.id
                LEFT JOIN categories c ON t.transaction_category = c.id -- Reverted join condition
                LEFT JOIN sub_categories sc ON t.transaction_sub_category = sc.id -- Reverted join condition
                ORDER BY t.transaction_date DESC, t.id DESC
            """)
            # Fetch all rows as dictionaries (due to row_factory)
            transactions = cursor.fetchall()
            # Convert sqlite3.Row objects to standard dicts
            return [dict(row) for row in transactions]
        except sqlite3.Error as e:
            debug_print('FOREIGN_KEYS', f"Database error loading transactions for GUI: {e}")
            return [] # Return empty list on error

    def get_accounts(self) -> List[Dict]:
        """Fetches all accounts (ID, name) for dropdowns."""
        if not self.conn: return []
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT id, account FROM bank_accounts ORDER BY account")
            accounts = cursor.fetchall()
            # Convert to dict and rename 'account' to 'name' for consistency with GUI expectations
            return [{'id': row['id'], 'name': row['account']} for row in accounts]
        except sqlite3.Error as e:
             debug_print('FOREIGN_KEYS', f"Database error loading accounts: {e}")
             return []

    def get_accounts_with_currency(self) -> List[Dict]:
        """Fetches all accounts with their currency information."""
        if not self.conn: return []
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT
                    ba.id,
                    ba.account,
                    ba.account_type,
                    ba.account_details,
                    ba.currency_id,
                    c.currency,
                    c.currency_code,
                    c.currency_symbol
                FROM bank_accounts ba
                JOIN currencies c ON ba.currency_id = c.id
                ORDER BY ba.account
            """)
            accounts = cursor.fetchall()
            # Convert to dict with all currency information
            return [dict(row) for row in accounts]
        except sqlite3.Error as e:
             debug_print('CURRENCY', f"Database error loading accounts with currency: {e}")
             return []

    def get_account_currency(self, account_id: int) -> Optional[Dict]:
        """Get currency information for a specific account."""
        if not self.conn: return None

        # Ensure account_id is an integer
        try:
            account_id = int(account_id)
        except (ValueError, TypeError):
            debug_print('CURRENCY', f"Warning: Invalid account_id: {account_id}, cannot convert to int")
            return None

        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT
                    c.id AS currency_id,
                    c.currency,
                    c.currency_code,
                    c.currency_symbol
                FROM bank_accounts ba
                JOIN currencies c ON ba.currency_id = c.id
                WHERE ba.id = ?
            """, (account_id,))
            result = cursor.fetchone()

            if result:
                return dict(result)
            else:
                return None

        except sqlite3.Error as e:
             debug_print('CURRENCY', f"Database error getting currency for account {account_id}: {e}")
             return None

    def get_categories(self) -> List[Dict]:
        """Fetches all categories (ID, name, type) for dropdowns."""
        if not self.conn: return []
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT id, category, type FROM categories ORDER BY type, category")
            categories = cursor.fetchall()
            # Convert to dict and rename 'category' to 'name' for consistency with GUI expectations
            return [{'id': row['id'], 'name': row['category'], 'type': row['type']} for row in categories]
        except sqlite3.Error as e:
             debug_print('SUBCATEGORY', f"Database error loading categories: {e}")
             return []

    def get_subcategories(self) -> List[Dict]:
        """Fetches all subcategories (ID, name, category_id) for dropdowns."""
        if not self.conn: return []
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT id, sub_category, category_id FROM sub_categories ORDER BY category_id, sub_category")
            subcategories = cursor.fetchall()
            # Convert to dict and rename 'sub_category' to 'name' for consistency with GUI expectations
            return [{'id': row['id'], 'name': row['sub_category'], 'category_id': row['category_id']} for row in subcategories]
        except sqlite3.Error as e:
             debug_print('SUBCATEGORY', f"Database error loading subcategories: {e}")
             return []

    # --- Update and Delete Methods ---

    def update_transaction(self, transaction_id: int, data: Dict) -> bool:
        """Updates an existing transaction."""
        if not self.conn: return False

        # Check if category is UNCATEGORIZED, if so, ensure subcategory is also UNCATEGORIZED
        if 'transaction_category' in data:
            category_id = data['transaction_category']
            cursor = self.conn.cursor()
            try:
                # Check if this is an UNCATEGORIZED category
                cursor.execute("SELECT category FROM categories WHERE id = ?", (category_id,))
                result = cursor.fetchone()
                if result and result['category'] == 'UNCATEGORIZED':
                    # Find UNCATEGORIZED subcategory for this category
                    cursor.execute("SELECT id FROM sub_categories WHERE category_id = ? AND sub_category = 'UNCATEGORIZED'", (category_id,))
                    subcat_result = cursor.fetchone()
                    if subcat_result:
                        # Set subcategory to UNCATEGORIZED
                        data['transaction_sub_category'] = subcat_result['id']
                        debug_print('SUBCATEGORY', f"Category is UNCATEGORIZED, setting subcategory to UNCATEGORIZED (ID: {subcat_result['id']})")
                    else:
                        # Create UNCATEGORIZED subcategory if it doesn't exist
                        uncat_subcat_id = self.ensure_subcategory('UNCATEGORIZED', category_id)
                        if uncat_subcat_id:
                            data['transaction_sub_category'] = uncat_subcat_id
                            debug_print('SUBCATEGORY', f"Created and set UNCATEGORIZED subcategory (ID: {uncat_subcat_id}) for UNCATEGORIZED category")
            except sqlite3.Error as e:
                debug_print('SUBCATEGORY', f"Error checking category for UNCATEGORIZED: {e}")

        # Construct SET clause dynamically but safely
        set_parts = []
        values = []
        allowed_columns = { # Whitelist columns that can be updated (using reverted names)
             'transaction_name', 'transaction_description', 'account_id',
             'transaction_value', 'transaction_type', 'transaction_category',
             'transaction_sub_category', 'transaction_date'
        }

        for key, value in data.items():
            if key in allowed_columns:
                set_parts.append(f"{key} = ?")
                # Convert Decimal to float for database
                if isinstance(value, Decimal):
                    values.append(float(value))
                # Store empty strings as NULL
                elif value == '':
                    values.append(None)
                else:
                    values.append(value)
            else:
                debug_print('FOREIGN_KEYS', f"Warning: Attempted to update disallowed column: {key}")

        if not set_parts:
            debug_print('FOREIGN_KEYS', "Warning: No valid columns provided for update_transaction.")
            return False

        values.append(transaction_id) # Add the ID for the WHERE clause
        sql = f"UPDATE transactions SET {', '.join(set_parts)} WHERE id = ?"

        cursor = self.conn.cursor()
        try:
            cursor.execute(sql, tuple(values))
            self.conn.commit()
            return cursor.rowcount > 0 # Return True if at least one row was updated
        except sqlite3.IntegrityError as e:
             debug_print('FOREIGN_KEYS', f"Database Integrity Error updating transaction ID {transaction_id}: {e}")
             debug_print('FOREIGN_KEYS', f"  > Data attempted: {data}")
             # Check if the referenced IDs actually exist (using potentially updated values from data dict)
             self.check_foreign_keys(cursor,
                                   data.get('account_id'),
                                   data.get('transaction_category'), # Reverted name
                                   data.get('transaction_sub_category') # Reverted name
                                   )
             self.conn.rollback()
             return False
        except sqlite3.Error as e:
            debug_print('FOREIGN_KEYS', f"Database Error updating transaction ID {transaction_id}: {e}")
            self.conn.rollback()
            return False


    def delete_transactions(self, transaction_ids: List[int]) -> int:
        """Deletes multiple transactions by their IDs. Returns number of rows deleted."""
        if not self.conn or not transaction_ids:
             return 0

        cursor = self.conn.cursor()
        try:
            placeholders = ','.join('?' * len(transaction_ids))
            sql = f"DELETE FROM transactions WHERE id IN ({placeholders})"
            cursor.execute(sql, tuple(transaction_ids))
            deleted_count = cursor.rowcount
            self.conn.commit()
            return deleted_count
        except sqlite3.Error as e:
            debug_print('FOREIGN_KEYS', f"Database Error deleting transactions: {e}")
            self.conn.rollback()
            return 0


    def close(self):
        """Close the database connection."""
        if self.conn:
            try:
                 # Optional: Commit any lingering transaction before closing? Usually handled by explicit commits.
                 # self.conn.commit()
                 self.conn.close()
                 self.conn = None # Set to None after closing
                 debug_print('FOREIGN_KEYS', "Database connection closed.")
            except sqlite3.Error as e:
                 debug_print('FOREIGN_KEYS', f"Error closing database connection: {e}")

    def __del__(self):
        """Ensure connection is closed when object is garbage collected."""
        self.close()


# Example Usage (Optional - keep commented out or remove for final app)
# if __name__ == '__main__':
#     db = Database()
#     # Example: Add a test account if it doesn't exist
#     cursor = db.conn.cursor()
#     cursor.execute("SELECT id FROM currencies WHERE currency_code = ?", ('USD',))
#     usd_id = cursor.fetchone()['id']
#     cursor.execute("INSERT OR IGNORE INTO bank_accounts (account, account_type, currency_id) VALUES (?, ?, ?)",
#                    ('Test Checking', 'Bank account', usd_id))
#     db.conn.commit()
#     accounts = db.get_accounts()
#     print("Accounts:", accounts)
#     categories = db.get_categories()
#     print("Categories:", categories)
#     subcategories = db.get_subcategories()
#     print("Subcategories:", subcategories)
#
#     # Try adding a transaction
#     test_acc_id = next((acc['id'] for acc in accounts if acc['account'] == 'Test Checking'), None)
#     test_cat_id = next((cat['id'] for cat in categories if cat['category'] == 'UNCATEGORIZED' and cat['type'] == 'Expense'), None)
#     test_subcat_id = next((sc['id'] for sc in subcategories if sc['sub_category'] == 'UNCATEGORIZED' and sc['category_id'] == test_cat_id), None)
#     today = datetime.now().strftime(DB_DATE_FORMAT)
#
#     if test_acc_id and test_cat_id and test_subcat_id:
#         print("\nAttempting to add transaction...")
#         new_id = db.add_transaction(
#             name="Test Coffee", description="Morning boost", account_id=test_acc_id,
#             value=3.50, type="Expense", category_id=test_cat_id,
#             sub_category_id=test_subcat_id, date_str=today
#         )
#         if new_id:
#             print(f"Transaction added successfully with ID: {new_id}")
#             all_trans = db.get_all_data_for_gui()
#             print("\nLatest Transaction:", all_trans[0] if all_trans else "None")
#         else:
#             print("Failed to add transaction.")
#     else:
#         print("\nCould not add test transaction - missing default account/category/subcategory IDs.")
#
#     db.close()
# --- END OF FILE database.py ---