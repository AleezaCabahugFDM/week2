# 2.4.2 Database Access Components

Repositories for customer, account and complaint data on the 2.1.1 PostgreSQL schema.

```
src/data/database_manager.py      connection + transaction lifecycle
src/data/customer_repository.py   CustomerRepository.get_by_id
src/data/account_repository.py    AccountRepository.get_for_customer
src/data/complaint_repository.py  ComplaintRepository.get_by_id / get_for_customer / create
tests/test_repositories.py        valid, missing and failure tests
```

## Setup

Requires Python 3.9+.

```bash
python3 -m pip install --user psycopg2-binary
```

Set these environment variables:

| Variable | Example |
|---|---|
| `DB_HOST` | `localhost` |
| `DB_PORT` | `5432` |
| `DB_NAME` | `complaints_training` |
| `DB_USER` | `training_user` |
| `DB_PASSWORD` | your password |

`MODEL_API_KEY` is not used here. Never commit real values: keep them in your shell or an untracked `.env` file.

## Usage

```python
from data.database_manager import DatabaseManager
from data.customer_repository import CustomerRepository
from data.account_repository import AccountRepository
from data.complaint_repository import ComplaintRepository

with DatabaseManager.from_env() as db:
    customer = CustomerRepository(db).get_by_id("CUS001")             # Customer, or None
    accounts = AccountRepository(db).get_for_customer("CUS001")       # [Account], or []
    complaints = ComplaintRepository(db).get_for_customer("CUS001")   # [Complaint], or []
    new = ComplaintRepository(db).create(
        complaint_id="CMP031", customer_id="CUS001", account_id="ACC001",
        channel="Web", category="Fee Dispute",
        customer_narrative="Charged twice", priority="Medium",
    )                                                                 # status OPEN, created_at now
```

Run from a folder where `src` is on the path, for example `PYTHONPATH=src python3 your_script.py`.

## Responsibilities

| Component | Does | Does not |
|---|---|---|
| `DatabaseManager` | Reads settings, opens and closes the connection, commits on success, rolls back on error, always closes the cursor | Run queries for callers, print or log the password |
| Repositories | Run parameterised SQL and return dataclass records (`None` or `[]` when nothing is found) | Make business decisions (priority, routing, approval, eligibility) |
| Database | Enforces data rules (allowed priorities and statuses, keys, account belongs to customer) | — |
| Callers (services, agents) | Business logic, then call the repositories | Write SQL |

Database errors are not hidden. For example, `CheckViolation` for priority `Urgent`, `UniqueViolation` for a duplicate ID, or `ForeignKeyViolation` for another customer's account. The transaction is rolled back first, so nothing partial is saved and the connection stays usable.

## Where SQL is allowed

- **Allowed:** only inside `src/data/*_repository.py`, and only with `%s` placeholders and a values tuple.
- **Prohibited:** SQL in services, agent tools or notebooks. Building SQL from user input with f-strings, `+` or `.format()`. The repositories write every query out in full, with no f-strings.
- Tests may write SQL to set up and remove their own test data.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

- **Without database variables:** the 4 config and connection tests run, and the 16 database tests are skipped.
- **With database variables:** all 20 tests run against the 2.1.1 schema. They insert their own `TST_` rows and delete them afterwards, so real data is not changed.

Last run: 20/20 passed on a local PostgreSQL 18 copy of the 2.1.1 schema and seed data, and no `TST_` rows were left behind.

| Group | Tests |
|---|---|
| Valid | Get customer, get accounts, get complaint, list complaints, create and read back, create without an account |
| Missing | Unknown customer or complaint returns `None`. A customer with no accounts or complaints returns `[]`. Injection text such as `x' OR '1'='1` is treated as a plain value. |
| Failure | Invalid priority, duplicate ID, and another customer's account are all rejected and rolled back. The cursor closes after an error and the connection recovers. The connection closes when a `with` block fails. An unreachable database raises an error without exposing the password. Missing settings are named without showing their values. |

## Limitations

- One connection per `DatabaseManager`, with no pooling and not thread-safe.
- Every repository call is its own transaction. Several calls cannot yet be grouped into one transaction.
- The tests need a real PostgreSQL database with the 2.1.1 schema.

**Handover:** 2.5.1 reuses the connection and validation pattern. Week 3 services call these repositories instead of writing SQL.
