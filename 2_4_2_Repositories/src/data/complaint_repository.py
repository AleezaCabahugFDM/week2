# complaint_repository.py
# Gets and creates complaints in the database. All SQL uses %s placeholders,
# so a value is never pasted into the SQL text.


class Complaint:
    def __init__(self, row):
        self.complaint_id = row[0]
        self.customer_id = row[1]
        self.account_id = row[2]                # can be None
        self.channel = row[3]
        self.category = row[4]
        self.customer_narrative = row[5]
        self.priority = row[6]
        self.status = row[7]
        self.created_at = row[8]
        self.assigned_employee_id = row[9]      # can be None


class ComplaintRepository:
    def __init__(self, db):
        self.db = db

    def get_by_id(self, complaint_id):
        """Gives back a Complaint, or None if there is no complaint with that ID."""
        row = self.db.run(
            "SELECT complaint_id, customer_id, account_id, channel, category, customer_narrative, "
            "priority, status, created_at, assigned_employee_id "
            "FROM complaint WHERE complaint_id = %s",
            (complaint_id,),
            fetch="one",
        )
        if row is None:
            return None
        return Complaint(row)

    def get_for_customer(self, customer_id):
        """Gives back a list of Complaints, oldest first. The list is empty if the customer has none."""
        rows = self.db.run(
            "SELECT complaint_id, customer_id, account_id, channel, category, customer_narrative, "
            "priority, status, created_at, assigned_employee_id "
            "FROM complaint WHERE customer_id = %s ORDER BY created_at, complaint_id",
            (customer_id,),
            fetch="all",
        )
        complaints = []
        for row in rows:
            complaints.append(Complaint(row))
        return complaints

    def create(self, complaint_id, customer_id, channel, category, customer_narrative, priority,
               account_id=None):
        """Saves a new complaint and gives it back.

        A new complaint always starts as OPEN, with created_at set to now and nobody assigned.
        The database rejects bad data (for example priority 'Urgent' or a duplicate ID).
        """
        row = self.db.run(
            "INSERT INTO complaint (complaint_id, customer_id, account_id, channel, category, "
            "customer_narrative, priority, status, created_at, assigned_employee_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, 'OPEN', CURRENT_TIMESTAMP, NULL) "
            "RETURNING complaint_id, customer_id, account_id, channel, category, customer_narrative, "
            "priority, status, created_at, assigned_employee_id",
            (complaint_id, customer_id, account_id, channel, category, customer_narrative, priority),
            fetch="one",
        )
        return Complaint(row)
