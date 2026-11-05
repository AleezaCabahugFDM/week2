# 2.4.2 Database Access Components

Week 2 | Exercise 2.4.2

Python code that gets customer, account and complaint data from the 2.1.1 PostgreSQL database in one safe, reusable way.

```
src/data/database_manager.py      opens/closes the connection, commits or rolls back each query
src/data/customer_repository.py   CustomerRepository.get_by_id
src/data/account_repository.py    AccountRepository.get_for_customer
src/data/complaint_repository.py  ComplaintRepository.get_by_id / get_for_customer / create
tests/test_repositories.py        valid, missing and failure tests
```

## Setup

1. Python 3.9 or newer, plus the PostgreSQL library:

   ```bash
   python3 -m pip install psycopg2-binary
   ```

2. A PostgreSQL database with the 2.1.1 schema and seed data (`2_1_1_schema/database_schema.sql`).

3. These settings, with the names from `environment_example.txt`:

   | Setting | Example |
   |---|---|
   | `DB_HOST` | `localhost` |
   | `DB_PORT` | `5432` |
   | `DB_NAME` | `complaints_training` |
   | `DB_USER` | `training_user` |
   | `DB_PASSWORD` | your password |

   Put the real values in a `.env` file in the repo folder. `.gitignore` keeps `.env` off GitHub, so the password is never committed. Load it into your terminal before running anything:

   ```bash
   set -a; source ../.env; set +a
   ```

   `MODEL_API_KEY` is not used in this exercise.

## How to use it

Run from the `2_4_2_Repositories` folder with `PYTHONPATH=src`, for example `PYTHONPATH=src python3 my_script.py`.

```python
from data.database_manager import DatabaseManager
from data.customer_repository import CustomerRepository
from data.account_repository import AccountRepository
from data.complaint_repository import ComplaintRepository

db = DatabaseManager()          # reads the DB_* settings
try:
    customer = CustomerRepository(db).get_by_id("CUS001")             # a Customer, or None
    accounts = AccountRepository(db).get_for_customer("CUS001")       # a list of Accounts, or []
    complaints = ComplaintRepository(db).get_for_customer("CUS001")   # a list of Complaints, or []
    new = ComplaintRepository(db).create(
        "CMP031", "CUS001", "Web", "Fee Dispute", "Charged twice", "Medium",
        account_id="ACC001",
    )                                                                 # saved as OPEN, created_at = now
    print(customer.first_name, len(accounts), len(complaints), new.status)
finally:
    db.close()                  # always close, even if something failed
```

On the seed data, `CUS001` has account `ACC001` and complaints `CMP001`, `CMP011`, `CMP012` and `CMP013`.

## Who does what

| Part | Does | Does not |
|---|---|---|
| `DatabaseManager` | Reads the settings, opens and closes the connection. `run()` commits if a query worked, rolls back if it failed, and always closes the cursor. | Print or log the password |
| Repositories | Run SQL with `%s` placeholders and give back `Customer`, `Account` or `Complaint` objects (`None` or `[]` when nothing is found) | Make business decisions (priority, routing, approval) |
| Database | Enforces the rules: allowed priorities and statuses, unique IDs, an account must belong to the customer | |
| Later code (Week 3 services, agents) | Business logic, then calls a repository | Write SQL |

**When something goes wrong:**

- **Missing setting:** a `ConfigError` names the missing setting, but never shows any values.
- **Database not reachable:** a `psycopg2.OperationalError`, without the password in the message.
- **Bad data:** the database error is passed on, not hidden. Examples are `CheckViolation` for priority `Urgent`, `UniqueViolation` for a duplicate ID, and `ForeignKeyViolation` for another customer's account. The change is rolled back first, so nothing half-done is saved and the connection keeps working.

## Where SQL is allowed

- **Allowed:** only in `src/data/*_repository.py`, written out in full, with `%s` placeholders and the values passed separately.
- **Not allowed:** SQL anywhere else (services, agent tools, notebooks), or SQL built by pasting values into the text with f-strings, `+` or `.format()`. Text like `x' OR '1'='1` is then treated as a plain value, never as SQL.
- **Exception:** the tests may write SQL to add and remove their own test rows.

## Tests

```bash
set -a; source ../.env; set +a
python3 -m unittest discover -s tests -v
```

- **Without the DB settings:** the 4 settings tests run and the 16 database tests are skipped.
- **With the DB settings:** all 20 tests run. They add their own `TST_` rows and delete them at the end, so the real data is not changed.

**Last run (2026-11-05):** 20 of 20 passed on a local PostgreSQL 18 copy of the 2.1.1 schema and seed data. Afterwards the database still had 10 customers, 10 accounts and 30 complaints, with no `TST_` rows left.

| Group | What is tested |
|---|---|
| Valid | Get a customer, get accounts, get a complaint, list complaints, create a complaint and read it back, create a complaint without an account |
| Missing | An unknown customer or complaint gives `None`. A customer with no accounts or complaints gives `[]`. Injection text is treated as a plain value. |
| Failure | Invalid priority, duplicate ID and another customer's account are rejected and not saved. The connection still works after an error. The connection is closed after an error. An unreachable database gives an error without the password. A missing setting is named without showing values. |

## Known limitations

- One connection per `DatabaseManager`. No pooling, and not safe to share between threads.
- Each repository call is its own transaction, so several calls can't yet be saved or undone together.
- `create` always starts a complaint as `OPEN` with nobody assigned. Changing the status is for a later exercise.
- The database tests need a real PostgreSQL database with the 2.1.1 schema.

**Handover:** 2.5.1 reuses the connection and error-handling pattern. Week 3 services call these repositories instead of writing their own SQL.
