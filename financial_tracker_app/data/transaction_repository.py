"""
Transaction repository for the financial tracker application.
This module contains the TransactionRepository class which handles database operations
related to transactions.
"""

import sqlite3
from datetime import datetime

from financial_tracker_app.models.transaction import Transaction
from financial_tracker_app.utils.debug_config import debug_print

class TransactionRepository:
    """
    A repository class for transaction data.

    This class handles all database operations related to transactions,
    including fetching, saving, updating, and deleting transactions.
    """

    def __init__(self, db_connection):
        """
        Initialize the repository with a database connection.

        Args:
            db_connection: A SQLite database connection.
        """
        self.conn = db_connection

    def get_all(self):
        """
        Get all transactions from the database.

        Returns:
            list: A list of Transaction objects.
        """
        try:
            cursor = self.conn.execute('''
                SELECT t.rowid, t.transaction_name, t.transaction_value,
                       t.account_id, a.name as account_name,
                       t.transaction_type,
                       t.transaction_category, c.name as category_name,
                       t.transaction_sub_category, sc.name as subcategory_name,
                       t.transaction_description, t.transaction_date
                FROM transactions t
                LEFT JOIN accounts a ON t.account_id = a.id
                LEFT JOIN categories c ON t.transaction_category = c.id
                LEFT JOIN subcategories sc ON t.transaction_sub_category = sc.id
                ORDER BY t.transaction_date DESC
            ''')

            transactions = []
            for row in cursor:
                # Create a dictionary from the row
                data = {
                    'rowid': row[0],
                    'transaction_name': row[1],
                    'transaction_value': row[2],
                    'account_id': row[3],
                    'account': row[4],
                    'transaction_type': row[5],
                    'transaction_category': row[6],
                    'category': row[7],
                    'transaction_sub_category': row[8],
                    'sub_category': row[9],
                    'transaction_description': row[10],
                    'transaction_date': row[11]
                }

                # Create a Transaction object
                transaction = Transaction.from_dict(data)
                transaction.account_name = data['account']
                transaction.category_name = data['category']
                transaction.subcategory_name = data['sub_category']

                transactions.append(transaction)

            return transactions

        except sqlite3.Error as e:
            debug_print('TRANSACTION_REPO', f"Error fetching transactions: {e}")
            return []

    def get_by_id(self, rowid):
        """
        Get a transaction by its ID.

        Args:
            rowid (int): The transaction ID.

        Returns:
            Transaction: A Transaction object, or None if not found.
        """
        try:
            cursor = self.conn.execute('''
                SELECT t.rowid, t.transaction_name, t.transaction_value,
                       t.account_id, a.name as account_name,
                       t.transaction_type,
                       t.transaction_category, c.name as category_name,
                       t.transaction_sub_category, sc.name as subcategory_name,
                       t.transaction_description, t.transaction_date
                FROM transactions t
                LEFT JOIN accounts a ON t.account_id = a.id
                LEFT JOIN categories c ON t.transaction_category = c.id
                LEFT JOIN subcategories sc ON t.transaction_sub_category = sc.id
                WHERE t.rowid = ?
            ''', (rowid,))

            row = cursor.fetchone()
            if row:
                # Create a dictionary from the row
                data = {
                    'rowid': row[0],
                    'transaction_name': row[1],
                    'transaction_value': row[2],
                    'account_id': row[3],
                    'account': row[4],
                    'transaction_type': row[5],
                    'transaction_category': row[6],
                    'category': row[7],
                    'transaction_sub_category': row[8],
                    'sub_category': row[9],
                    'transaction_description': row[10],
                    'transaction_date': row[11]
                }

                # Create a Transaction object
                transaction = Transaction.from_dict(data)
                transaction.account_name = data['account']
                transaction.category_name = data['category']
                transaction.subcategory_name = data['sub_category']

                return transaction

            return None

        except sqlite3.Error as e:
            debug_print('TRANSACTION_REPO', f"Error fetching transaction {rowid}: {e}")
            return None

    def save(self, transaction):
        """
        Save a transaction to the database.

        Args:
            transaction (Transaction): The transaction to save.

        Returns:
            int: The ID of the saved transaction, or None if there was an error.
        """
        try:
            # Validate the transaction
            is_valid, errors = transaction.is_valid()
            if not is_valid:
                debug_print('TRANSACTION_REPO', f"Invalid transaction: {errors}")
                return None, errors

            # Convert to dictionary for database insertion
            data = transaction.to_dict()

            # Insert the transaction
            cursor = self.conn.execute('''
                INSERT INTO transactions(
                    transaction_name, transaction_value, account_id,
                    transaction_type, transaction_category,
                    transaction_sub_category, transaction_description, transaction_date
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['transaction_name'],
                data['transaction_value'],
                data['account_id'],
                data['transaction_type'],
                data['transaction_category'],
                data['transaction_sub_category'],
                data['transaction_description'],
                data['transaction_date']
            ))

            self.conn.commit()
            return cursor.lastrowid, {}

        except sqlite3.Error as e:
            debug_print('TRANSACTION_REPO', f"Error saving transaction: {e}")
            if self.conn.in_transaction:
                self.conn.rollback()
            return None, {'database': str(e)}

    def update(self, transaction):
        """
        Update a transaction in the database.

        Args:
            transaction (Transaction): The transaction to update.

        Returns:
            bool: True if the update was successful, False otherwise.
        """
        try:
            # Validate the transaction
            is_valid, errors = transaction.is_valid()
            if not is_valid:
                debug_print('TRANSACTION_REPO', f"Invalid transaction: {errors}")
                return False, errors

            # Convert to dictionary for database update
            data = transaction.to_dict()

            # Update the transaction
            self.conn.execute('''
                UPDATE transactions
                SET transaction_name = ?,
                    transaction_value = ?,
                    account_id = ?,
                    transaction_type = ?,
                    transaction_category = ?,
                    transaction_sub_category = ?,
                    transaction_description = ?,
                    transaction_date = ?
                WHERE rowid = ?
            ''', (
                data['transaction_name'],
                data['transaction_value'],
                data['account_id'],
                data['transaction_type'],
                data['transaction_category'],
                data['transaction_sub_category'],
                data['transaction_description'],
                data['transaction_date'],
                data['rowid']
            ))

            self.conn.commit()
            return True, {}

        except sqlite3.Error as e:
            debug_print('TRANSACTION_REPO', f"Error updating transaction: {e}")
            if self.conn.in_transaction:
                self.conn.rollback()
            return False, {'database': str(e)}

    def delete(self, rowid):
        """
        Delete a transaction from the database.

        Args:
            rowid (int): The ID of the transaction to delete.

        Returns:
            bool: True if the deletion was successful, False otherwise.
        """
        try:
            self.conn.execute('DELETE FROM transactions WHERE rowid = ?', (rowid,))
            self.conn.commit()
            return True

        except sqlite3.Error as e:
            debug_print('TRANSACTION_REPO', f"Error deleting transaction {rowid}: {e}")
            if self.conn.in_transaction:
                self.conn.rollback()
            return False