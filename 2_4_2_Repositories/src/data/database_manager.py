# database_manager.py
# Week 2 | Exercise 2.4.2 - Opens and closes the database connection.
#
# Every query goes through run(). It commits if the query worked,
# rolls back if it failed, and always closes the cursor.

import os

import psycopg2

SETTING_NAMES = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]


class ConfigError(Exception):
    """A database setting is missing."""


def load_settings(source=os.environ):
    """Read the DB_* settings. Stops with a ConfigError if any are missing."""
    missing = []
    for name in SETTING_NAMES:
        if not source.get(name):
            missing.append(name)
    if len(missing) > 0:
        # Name the missing settings, but never show any values.
        raise ConfigError("Missing environment variable(s): " + ", ".join(missing))

    settings = {}
    for name in SETTING_NAMES:
        settings[name] = source[name]
    return settings


class DatabaseManager:
    def __init__(self, settings=None):
        if settings is None:
            settings = load_settings()
        self.settings = settings        # holds the password, so never print this
        self.connection = None

    def is_open(self):
        return self.connection is not None and self.connection.closed == 0

    def connect(self):
        if not self.is_open():
            self.connection = psycopg2.connect(
                host=self.settings["DB_HOST"],
                port=int(self.settings["DB_PORT"]),
                dbname=self.settings["DB_NAME"],
                user=self.settings["DB_USER"],
                password=self.settings["DB_PASSWORD"],
                connect_timeout=5,
            )

    def close(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def run(self, sql, values, fetch=None):
        """Run one SQL statement with %s placeholders.

        fetch="one" gives back one row (or None), fetch="all" gives back a list of rows,
        and no fetch gives back nothing (for INSERT or DELETE).
        """
        self.connect()
        cursor = self.connection.cursor()
        try:
            cursor.execute(sql, values)
            result = None
            if fetch == "one":
                result = cursor.fetchone()
            if fetch == "all":
                result = cursor.fetchall()
            self.connection.commit()        # it worked, so save it
            return result
        except Exception:
            self.connection.rollback()      # it failed, so undo everything from this statement
            raise                           # and still tell the caller about the error
        finally:
            cursor.close()                  # runs whether it worked or not
