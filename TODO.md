### UX/UI
- [ ] **Add Transactions Screen**

        
	- [ ] **Grid**
    	- [ ] *Bugs*
    		- [x] Shows bank account when selecting UNCATEGORIZED
    		- [ ] Clicking on dropdowns or dates doesn't open what it should
    		- [ ] When edditing a transaction the description field displays, for example, "$ 0.00", for some reason.
		- [x] Description field
			- [x] Should have smaller font and a different color that makes it look less in hierarchy
			- [x] I want to open it to edit it
		- [ ] Expenses and Income should have colors
		- [ ] Transfers should be hidden, there is a screen for that
		- [ ] Value field should show the currency symbol
	- [ ] Default Values
		- [ ] Clear button for no defaults
		- [ ] Improve Ui (Maybe add a new button for it?)
	- [ ] Filters: So I can see only transactions of certain characteristics, and a default filter should contain transactions up to 3 months
	- [ ] Upload CSV and match columns - Add logic to verify them first
- [ ] **User page / Configuration**
	- [ ] Name of the wallet
	- [ ] Currencies accepted
	- [ ] Main currency of the account (Can be changed)
- [ ] **Transactions Summary Screen**
	- [ ] Show the value in the main currency too
		- [ ] API to have values but to storage them
	- [ ] Show the account balance up to that point
- [ ] **Bank Accounts**
	- [ ] Account, account type, currency, details, etc.
	- [ ] Total balance in the currency of the account
	- [ ] Total balance in the main currency
- [ ] **Summary in main currency**
	- [ ] Total balance
	- [ ] Money available (Only count positive money of accounts that are not savings, so no debts)
	- [ ] Debts (Negative money)
	- [ ] Savings (Sum money of savings accounts)
	- [ ] All money available (Sum all positive money, even savings)
	- [ ] Biggest debt


### Backend and Sharing
- [ ] Change the database to a custom folder in the computer
	- [ ] Change also configuration related to the user such as main currency, name of the wallet, default values, back ups etc.
	- [ ] User should make a specific folder for this data
- [ ] If folder has nothing app should make the necessary folders and prompt the user for information such as currencies to use, main currency, name of wallet, etc.
- [ ] Database is chaotic
	- [ ] Fix data types: Transaction values are stored as Real, for example