# account_repository.py
# Gets accounts from the database. All SQL uses %s placeholders,
# so a value is never pasted into the SQL text.


class Account:
    def __init__(self, row):
        self.account_id = row[0]
        self.customer_id = row[1]
        self.account_number = row[2]
        self.account_type = row[3]
        self.status = row[4]
        self.balance = row[5]           # a Decimal, so money is exact
        self.open_date = row[6]


class AccountRepository:
    def __init__(self, db):
        self.db = db

    def get_for_customer(self, customer_id):
        """Gives back a list of Accounts. The list is empty if the customer has none."""
        rows = self.db.run(
            "SELECT account_id, customer_id, account_number, account_type, status, balance, open_date "
            "FROM account WHERE customer_id = %s ORDER BY account_id",
            (customer_id,),
            fetch="all",
        )
        accounts = []
        for row in rows:
            accounts.append(Account(row))
        return accounts
