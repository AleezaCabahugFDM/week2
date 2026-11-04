import os
from contextlib import contextmanager

import psycopg2

REQUIRED_SETTINGS = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]


class ConfigError(Exception):
    pass


class DatabaseManager:
    def __init__(self, host, port, dbname, user, password):
        self._settings = {"host": host, "port": int(port), "dbname": dbname, "user": user, "password": password}
        self._connection = None

    @classmethod
    def from_env(cls):
        missing = [name for name in REQUIRED_SETTINGS if not os.environ.get(name)]
        if missing:
            raise ConfigError(f"Missing environment variable(s): {', '.join(missing)}")
        return cls(os.environ["DB_HOST"], os.environ["DB_PORT"], os.environ["DB_NAME"],
                   os.environ["DB_USER"], os.environ["DB_PASSWORD"])

    def __repr__(self):
        s = self._settings
        return f"DatabaseManager({s['user']}@{s['host']}:{s['port']}/{s['dbname']}, password=***)"

    @property
    def is_open(self):
        return self._connection is not None and not self._connection.closed

    def connect(self):
        if not self.is_open:
            self._connection = psycopg2.connect(**self._settings, connect_timeout=5)
        return self._connection

    def close(self):
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    @contextmanager
    def transaction(self):
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

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
