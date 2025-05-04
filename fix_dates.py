#!/usr/bin/env python3

import sqlite3
import os
from datetime import datetime
import re

# Define the database path
DB_PATH = "financial_tracker.db"

# Define the expected date format
DB_DATE_FORMAT = "%Y-%m-%d"

def fix_dates():
    """Fix invalid date formats in the transactions table."""
    print("Starting date format correction...")
    
    # Connect to the database
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all transactions
    cursor.execute("SELECT id, transaction_date FROM transactions")
    transactions = cursor.fetchall()
    
    # Count of fixed records
    fixed_count = 0
    
    # Default date to use for completely invalid dates
    default_date = datetime.now().strftime(DB_DATE_FORMAT)
    
    for transaction in transactions:
        transaction_id = transaction['id']
        date_value = transaction['transaction_date']
        new_date = None
        
        # Skip if already in correct format
        if is_valid_iso_date(date_value):
            continue
            
        # Try to parse different date formats
        if date_value:
            # Try "DD MMM YYYY" format (e.g., "20 May 2025")
            match = re.match(r'(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})', date_value)
            if match:
                day, month_str, year = match.groups()
                month_map = {
                    'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
                    'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
                }
                month = month_map.get(month_str, 1)  # Default to January if not found
                try:
                    new_date = f"{year}-{month:02d}-{int(day):02d}"
                    if is_valid_iso_date(new_date):
                        print(f"Converting '{date_value}' to '{new_date}'")
                    else:
                        new_date = default_date
                        print(f"Invalid date '{date_value}' replaced with default '{new_date}'")
                except ValueError:
                    new_date = default_date
                    print(f"Invalid date '{date_value}' replaced with default '{new_date}'")
            else:
                # For completely invalid values (like "Expense")
                new_date = default_date
                print(f"Invalid date '{date_value}' replaced with default '{new_date}'")
        else:
            # For empty values
            new_date = default_date
            print(f"Empty date replaced with default '{new_date}'")
        
        # Update the record
        if new_date:
            cursor.execute(
                "UPDATE transactions SET transaction_date = ? WHERE id = ?",
                (new_date, transaction_id)
            )
            fixed_count += 1
    
    # Commit changes
    conn.commit()
    
    # Add CHECK constraint to prevent future invalid dates
    try:
        cursor.execute("""
            CREATE TABLE transactions_temp (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_name TEXT,
                transaction_description TEXT,
                account_id INTEGER NOT NULL,
                transaction_value REAL NOT NULL,
                transaction_type TEXT NOT NULL CHECK(transaction_type IN ('Income', 'Expense')),
                transaction_category INTEGER NOT NULL,
                transaction_sub_category INTEGER NOT NULL,
                transaction_date TEXT NOT NULL CHECK(transaction_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
                FOREIGN KEY (account_id) REFERENCES bank_accounts (id) ON DELETE RESTRICT,
                FOREIGN KEY (transaction_category) REFERENCES categories (id) ON DELETE RESTRICT,
                FOREIGN KEY (transaction_sub_category) REFERENCES sub_categories (id) ON DELETE RESTRICT
            )
        """)
        
        # Copy data to new table
        cursor.execute("""
            INSERT INTO transactions_temp
            SELECT * FROM transactions
        """)
        
        # Drop old table and rename new one
        cursor.execute("DROP TABLE transactions")
        cursor.execute("ALTER TABLE transactions_temp RENAME TO transactions")
        
        print("Added CHECK constraint to enforce date format")
    except sqlite3.Error as e:
        print(f"Error adding CHECK constraint: {e}")
        conn.rollback()
    
    # Close connection
    conn.close()
    
    print(f"Fixed {fixed_count} records with invalid date formats.")
    print("Date correction completed.")

def is_valid_iso_date(date_str):
    """Check if a string is a valid ISO date (YYYY-MM-DD)."""
    if not date_str or not isinstance(date_str, str):
        return False
    
    # Check basic format
    if len(date_str) != 10 or date_str.count('-') != 2:
        return False
    
    # Try to parse
    try:
        datetime.strptime(date_str, DB_DATE_FORMAT)
        return True
    except ValueError:
        return False

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print(f"Error: Database file '{DB_PATH}' not found.")
    else:
        fix_dates()
