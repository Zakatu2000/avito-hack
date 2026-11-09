"""Provision a new database per test run without touching any existing database."""
import os
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row

from server.app import create_app
from server.store import migrate, reset_demo, seed


@pytest.fixture(scope="session")
def database_url():
    admin_url = os.environ.get("TEST_ADMIN_DATABASE_URL")
    if not admin_url:
        pytest.fail("Set TEST_ADMIN_DATABASE_URL to a local test cluster with CREATEDB permission.")

    name = "avito_buddy_test_" + uuid4().hex
    identifier = sql.Identifier(name)
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(identifier))
        try:
            url = make_conninfo(admin_url, dbname=name)
            with psycopg.connect(url, row_factory=dict_row) as conn:
                migrate(conn)
                seed(conn)
            yield url
        finally:
            admin.execute(sql.SQL("DROP DATABASE {}").format(identifier))


@pytest.fixture
def db(database_url):
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        reset_demo(conn)
        conn.commit()
        yield conn


@pytest.fixture
def app(db, database_url):
    return create_app({"TESTING": True, "DATABASE_URL": database_url})


@pytest.fixture
def unapproved_database(database_url):
    """Fresh empty DB whose name intentionally falls outside the demo allowlist."""
    name = "guard_check_" + uuid4().hex
    identifier = sql.Identifier(name)
    with psycopg.connect(database_url, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(identifier))
        try:
            with psycopg.connect(make_conninfo(database_url, dbname=name)) as conn:
                yield conn
        finally:
            admin.execute(sql.SQL("DROP DATABASE {}").format(identifier))
