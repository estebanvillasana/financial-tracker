import sys
from datetime import datetime
from tabulate import tabulate
from colorama import init, Fore, Style
from database import Database

init()  # Initialize colorama

class ExpenseTracker:
    def __init__(self):
        self.db = Database()
        
    def display_menu(self):
        """Display the main menu."""
        print("\n" + "="*50)
        print(Fore.CYAN + "Expense Tracker" + Style.RESET_ALL)
        print("="*50)
        print("1. Add Expense")
        print("2. View Expenses")
        print("3. Set Budget")
        print("4. View Monthly Summary")
        print("5. Exit")
        print("="*50)

    def add_expense(self):
        """Add a new expense."""
        try:
            amount = float(input("Enter amount: $"))
            category = input("Enter category: ").strip()
            description = input("Enter description (optional): ").strip()
            
            if self.db.add_expense(amount, category, description):
                print(Fore.GREEN + "Expense added successfully!" + Style.RESET_ALL)
            else:
                print(Fore.RED + "Failed to add expense." + Style.RESET_ALL)
        except ValueError:
            print(Fore.RED + "Invalid amount. Please enter a number." + Style.RESET_ALL)

    def view_expenses(self):
        """View all expenses."""
        expenses = self.db.get_expenses()
        
        if not expenses:
            print(Fore.YELLOW + "No expenses found." + Style.RESET_ALL)
            return
        
        # Prepare data for tabulate
        table_data = []
        for expense in expenses:
            table_data.append([
                expense['id'],
                f"${expense['amount']:.2f}",
                expense['category'],
                expense['description'],
                expense['date']
            ])
        
        headers = ["ID", "Amount", "Category", "Description", "Date"]
        print(tabulate(table_data, headers=headers, tablefmt="grid"))

    def set_budget(self):
        """Set monthly budget for a category."""
        try:
            category = input("Enter category: ").strip()
            amount = float(input("Enter budget amount: $"))
            month = input("Enter month (YYYY-MM): ").strip()
            
            if self.db.set_budget(category, amount, month):
                print(Fore.GREEN + "Budget set successfully!" + Style.RESET_ALL)
            else:
                print(Fore.RED + "Failed to set budget. Category might not exist." + Style.RESET_ALL)
        except ValueError:
            print(Fore.RED + "Invalid amount. Please enter a number." + Style.RESET_ALL)

    def view_monthly_summary(self):
        """View monthly expense summary."""
        month = input("Enter month (YYYY-MM): ").strip()
        summary = self.db.get_monthly_summary(month)
        
        if not summary['category_totals']:
            print(Fore.YELLOW + f"No expenses found for {month}." + Style.RESET_ALL)
            return
        
        # Prepare data for tabulate
        table_data = []
        total_expenses = 0
        
        for category, amount in summary['category_totals'].items():
            budget = summary['budgets'].get(category, 0)
            remaining = budget - amount if budget else 0
            table_data.append([
                category,
                f"${amount:.2f}",
                f"${budget:.2f}",
                f"${remaining:.2f}" if budget else "N/A"
            ])
            total_expenses += amount
        
        headers = ["Category", "Spent", "Budget", "Remaining"]
        print(f"\nMonthly Summary for {month}")
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
        print(f"\nTotal Expenses: ${total_expenses:.2f}")

    def run(self):
        """Run the expense tracker application."""
        while True:
            self.display_menu()
            choice = input("Enter your choice (1-5): ")
            
            if choice == "1":
                self.add_expense()
            elif choice == "2":
                self.view_expenses()
            elif choice == "3":
                self.set_budget()
            elif choice == "4":
                self.view_monthly_summary()
            elif choice == "5":
                print(Fore.CYAN + "Goodbye! Thanks for using Expense Tracker!" + Style.RESET_ALL)
                self.db.close()
                sys.exit(0)
            else:
                print(Fore.RED + "Invalid choice. Please try again." + Style.RESET_ALL)

if __name__ == "__main__":
    tracker = ExpenseTracker()
    tracker.run()