"""
Transaction controller for the financial tracker application.
This module contains the TransactionController class which handles the business logic
for transactions.
"""

from financial_tracker_app.models.transaction import Transaction
from financial_tracker_app.data.transaction_repository import TransactionRepository
from financial_tracker_app.utils.debug_config import debug_print

class TransactionController:
    """
    A controller class for transaction operations.

    This class handles the business logic for transactions, including validation,
    data transformation, and coordinating between the UI and data layers.
    """

    def __init__(self, database):
        """
        Initialize the controller with a database connection.

        Args:
            database: A Database object with a connection to the SQLite database.
        """
        self.db = database
        self.transaction_repository = TransactionRepository(database.conn)

        # Cache for transactions
        self.transactions = []
        self.pending = []
        self.dirty = set()
        self.dirty_fields = {}
        self.errors = {}
        self._original_data_cache = {}

    def load_transactions(self):
        """
        Load all transactions from the database.

        Returns:
            list: A list of transactions as dictionaries.
        """
        # Get transactions from the repository
        transaction_objects = self.transaction_repository.get_all()

        # Convert to dictionaries for the UI
        self.transactions = [t.to_dict() for t in transaction_objects]

        # Clear other state
        self.pending = []
        self.dirty = set()
        self.dirty_fields = {}
        self.errors = {}

        # Cache original data for dirty checking
        self._original_data_cache = {t['rowid']: t.copy() for t in self.transactions}

        return self.transactions

    def add_transaction(self, transaction_data):
        """
        Add a new transaction.

        Args:
            transaction_data (dict): The transaction data.

        Returns:
            tuple: (bool, dict) - Success flag and errors dictionary.
        """
        # Create a Transaction object
        transaction = Transaction.from_dict(transaction_data)

        # Validate the transaction
        is_valid, errors = transaction.is_valid()
        if not is_valid:
            return False, errors

        # Save to the database
        rowid, errors = self.transaction_repository.save(transaction)
        if rowid is None:
            return False, errors

        # Update the transaction with the new ID
        transaction.rowid = rowid

        # Reload transactions to get the updated list
        self.load_transactions()

        return True, {}

    def update_transaction(self, transaction_data):
        """
        Update an existing transaction.

        Args:
            transaction_data (dict): The transaction data with rowid.

        Returns:
            tuple: (bool, dict) - Success flag and errors dictionary.
        """
        # Ensure rowid is present
        if 'rowid' not in transaction_data:
            return False, {'general': 'Transaction ID is missing'}

        # Create a Transaction object
        transaction = Transaction.from_dict(transaction_data)

        # Validate the transaction
        is_valid, errors = transaction.is_valid()
        if not is_valid:
            return False, errors

        # Update in the database
        success, errors = self.transaction_repository.update(transaction)
        if not success:
            return False, errors

        # Reload transactions to get the updated list
        self.load_transactions()

        return True, {}

    def delete_transaction(self, rowid):
        """
        Delete a transaction.

        Args:
            rowid (int): The ID of the transaction to delete.

        Returns:
            bool: True if the deletion was successful, False otherwise.
        """
        # Delete from the database
        success = self.transaction_repository.delete(rowid)
        if not success:
            return False

        # Reload transactions to get the updated list
        self.load_transactions()

        return True

    def add_pending_transaction(self, transaction_data):
        """
        Add a transaction to the pending list.

        Args:
            transaction_data (dict): The transaction data.

        Returns:
            bool: True if the transaction was added to pending, False otherwise.
        """
        # Create a Transaction object for validation
        transaction = Transaction.from_dict(transaction_data)

        # Validate the transaction
        is_valid, errors = transaction.is_valid()
        if not is_valid:
            # Store errors for the UI
            pending_index = len(self.pending)
            visual_index = len(self.transactions) + pending_index
            self.errors[visual_index] = errors
            return False

        # Add to pending list
        self.pending.append(transaction_data)
        return True

    def save_all_changes(self):
        """
        Save all pending and dirty transactions.

        Returns:
            tuple: (bool, dict) - Success flag and errors dictionary.
        """
        all_success = True
        all_errors = {}

        # Save pending transactions
        for i, transaction_data in enumerate(self.pending):
            # Create a Transaction object
            transaction = Transaction.from_dict(transaction_data)

            # Save to the database
            rowid, errors = self.transaction_repository.save(transaction)
            if rowid is None:
                all_success = False
                visual_index = len(self.transactions) + i
                all_errors[visual_index] = errors

        # Update dirty transactions
        for rowid in self.dirty:
            # Find the transaction in the list
            transaction_data = None
            for t in self.transactions:
                if t['rowid'] == rowid:
                    transaction_data = t
                    break

            if transaction_data:
                # Create a Transaction object
                transaction = Transaction.from_dict(transaction_data)

                # Update in the database
                success, errors = self.transaction_repository.update(transaction)
                if not success:
                    all_success = False
                    # Find the visual index
                    for i, t in enumerate(self.transactions):
                        if t['rowid'] == rowid:
                            all_errors[i] = errors
                            break

        # Reload transactions if any changes were made
        if self.pending or self.dirty:
            self.load_transactions()

        return all_success, all_errors

    def mark_dirty(self, rowid, field=None):
        """
        Mark a transaction as dirty.

        Args:
            rowid (int): The ID of the transaction.
            field (str, optional): The specific field that was changed.
        """
        self.dirty.add(rowid)
        if field:
            if rowid not in self.dirty_fields:
                self.dirty_fields[rowid] = set()
            self.dirty_fields[rowid].add(field)

    def is_dirty(self, rowid):
        """
        Check if a transaction is dirty.

        Args:
            rowid (int): The ID of the transaction.

        Returns:
            bool: True if the transaction is dirty, False otherwise.
        """
        return rowid in self.dirty

    def get_dirty_fields(self, rowid):
        """
        Get the dirty fields for a transaction.

        Args:
            rowid (int): The ID of the transaction.

        Returns:
            set: A set of field names that are dirty.
        """
        return self.dirty_fields.get(rowid, set())

    def has_changes(self):
        """
        Check if there are any pending or dirty transactions.

        Returns:
            bool: True if there are changes, False otherwise.
        """
        return bool(self.pending) or bool(self.dirty)

    def discard_changes(self):
        """
        Discard all pending and dirty transactions.
        """
        self.pending = []
        self.dirty = set()
        self.dirty_fields = {}
        self.errors = {}

        # Reload transactions to revert any changes
        self.load_transactions()