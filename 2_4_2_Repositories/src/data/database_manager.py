"""Opens and closes the database connection, and commits or rolls back each transaction."""

import os
from contextlib import contextmanager

import psycopg2

REQUIRED_SETTINGS = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]


class ConfigError(Exception):
    """A database setting is missing."""


class DatabaseManager:
    def __init__(self, host, port, dbname, user, password):
        self.host = host
        self.port = int(port)
        self.dbname = dbname
        self.user = user
        self._password = password      # never printed or logged
        self._connection = None

    @classmethod
    def from_env(cls):
        """Read the DB_* settings from environment variables."""
        missing = [name for name in REQUIRED_SETTINGS if not os.environ.get(name)]
        if missing:
            # Name the missing variables, but never show any values.
            raise ConfigError(f"Missing environment variable(s): {', '.join(missing)}")
        return cls(os.environ["DB_HOST"], os.environ["DB_PORT"], os.environ["DB_NAME"],
                   os.environ["DB_USER"], os.environ["DB_PASSWORD"])

    def __repr__(self):
        return f"DatabaseManager({self.user}@{self.host}:{self.port}/{self.dbname}, password=***)"

    @property
    def is_open(self):
        return self._connection is not None and not self._connection.closed

    def connect(self):
        if not self.is_open:
            self._connection = psycopg2.connect(host=self.host, port=self.port, dbname=self.dbname,
                                                user=self.user, password=self._password, connect_timeout=5)
        return self._connection

    def close(self):
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    @contextmanager
    def transaction(self):
        """Use with 'with'. Commits if everything worked, rolls back if there was an error.

            with db.transaction() as cur:
                cur.execute("SELECT ...", (value,))
        """
        connection = self.connect()
        cursor = connection.cursor()
        try:
            yield cursor
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()

    # Lets you write: with DatabaseManager.from_env() as db: ...  (closes the connection at the end)
    def __enter__(self):
        return self

    def __exit__(self, *error):
        self.close()
