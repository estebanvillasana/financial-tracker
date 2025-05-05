"""
Transaction model for the financial tracker application.
This module contains the Transaction class which represents a financial transaction.
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation

class Transaction:
    """
    A class representing a financial transaction.

    This class encapsulates all the data and behavior related to a financial transaction,
    including validation and formatting.
    """

    def __init__(self, rowid=None, name="", value=0.0, account_id=None, transaction_type="Expense",
                 category_id=None, subcategory_id=None, description="", date=None):
        """
        Initialize a Transaction object.

        Args:
            rowid (int, optional): The database row ID. Defaults to None.
            name (str, optional): The transaction name. Defaults to "".
            value (float, optional): The transaction value. Defaults to 0.0.
            account_id (int, optional): The account ID. Defaults to None.
            transaction_type (str, optional): The transaction type. Defaults to "Expense".
            category_id (int, optional): The category ID. Defaults to None.
            subcategory_id (int, optional): The subcategory ID. Defaults to None.
            description (str, optional): The transaction description. Defaults to "".
            date (str, optional): The transaction date in YYYY-MM-DD format. Defaults to today.
        """
        self.rowid = rowid
        self.name = name
        self.value = Decimal(str(value)) if value is not None else Decimal('0.0')
        self.account_id = account_id
        self.transaction_type = transaction_type
        self.category_id = category_id
        self.subcategory_id = subcategory_id
        self.description = description

        # Set date to today if not provided
        if date is None:
            self.date = datetime.now().strftime("%Y-%m-%d")
        else:
            self.date = date

        # Additional attributes for display purposes
        self.account_name = None
        self.category_name = None
        self.subcategory_name = None
        self.currency_info = None

    @classmethod
    def from_dict(cls, data):
        """
        Create a Transaction object from a dictionary.

        Args:
            data (dict): A dictionary containing transaction data.

        Returns:
            Transaction: A new Transaction object.
        """
        # Map dictionary keys to constructor parameters
        return cls(
            rowid=data.get('rowid'),
            name=data.get('transaction_name', ''),
            value=data.get('transaction_value', 0.0),
            account_id=data.get('account_id'),
            transaction_type=data.get('transaction_type', 'Expense'),
            category_id=data.get('transaction_category'),
            subcategory_id=data.get('transaction_sub_category'),
            description=data.get('transaction_description', ''),
            date=data.get('transaction_date')
        )

    def to_dict(self):
        """
        Convert the Transaction object to a dictionary.

        Returns:
            dict: A dictionary representation of the transaction.
        """
        return {
            'rowid': self.rowid,
            'transaction_name': self.name,
            'transaction_value': float(self.value),
            'account_id': self.account_id,
            'transaction_type': self.transaction_type,
            'transaction_category': self.category_id,
            'transaction_sub_category': self.subcategory_id,
            'transaction_description': self.description,
            'transaction_date': self.date,
            # Include display names if available
            'account': self.account_name,
            'category': self.category_name,
            'sub_category': self.subcategory_name
        }

    def is_valid(self):
        """
        Check if the transaction is valid.

        Returns:
            tuple: (bool, dict) - A tuple containing a boolean indicating if the transaction is valid
                  and a dictionary of validation errors.
        """
        errors = {}

        # Validate name
        if not self.name:
            errors['transaction_name'] = "Name is required"

        # Validate value
        try:
            value = Decimal(str(self.value))
            if value < 0:
                errors['transaction_value'] = "Value must be non-negative"
        except (ValueError, TypeError, InvalidOperation):
            errors['transaction_value'] = "Value must be a valid number"

        # Validate account
        if self.account_id is None:
            errors['account_id'] = "Account is required"

        # Validate type
        if self.transaction_type not in ['Expense', 'Income']:
            errors['transaction_type'] = "Type must be 'Expense' or 'Income'"

        # Validate date
        try:
            datetime.strptime(self.date, "%Y-%m-%d")
        except ValueError:
            errors['transaction_date'] = "Date must be in YYYY-MM-DD format"

        return (len(errors) == 0, errors)

    def __str__(self):
        """
        Return a string representation of the transaction.

        Returns:
            str: A string representation of the transaction.
        """
        return f"{self.name} ({self.transaction_type}): {self.value} on {self.date}"