# customer_repository.py
# Gets customers from the database. All SQL uses %s placeholders,
# so a value is never pasted into the SQL text.


class Customer:
    def __init__(self, row):
        self.customer_id = row[0]
        self.first_name = row[1]
        self.last_name = row[2]
        self.email = row[3]             # can be None
        self.phone_number = row[4]      # can be None
        self.segment = row[5]


class CustomerRepository:
    def __init__(self, db):
        self.db = db

    def get_by_id(self, customer_id):
        """Gives back a Customer, or None if there is no customer with that ID."""
        row = self.db.run(
            "SELECT customer_id, first_name, last_name, email, phone_number, segment "
            "FROM customer WHERE customer_id = %s",
            (customer_id,),
            fetch="one",
        )
        if row is None:
            return None
        return Customer(row)
