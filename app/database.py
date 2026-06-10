import os
from collections.abc import Iterator
from contextlib import contextmanager

import mariadb

database_host = os.getenv("MARIADB_HOST")
database_port = int(os.getenv("MARIADB_PORT", "3306"))
database_name = os.getenv("MARIADB_DATABASE")
database_user = os.getenv("MARIADB_USER")
database_password = os.getenv("MARIADB_PASSWORD")
database_timeout = int(os.getenv("MARIADB_CONNECT_TIMEOUT", "10"))
query_timeout = float(os.getenv("MARIADB_QUERY_TIMEOUT", "10"))

required_settings = {
    "MARIADB_HOST": database_host,
    "MARIADB_DATABASE": database_name,
    "MARIADB_USER": database_user,
    "MARIADB_PASSWORD": database_password,
}

missing_settings = [name for name, value in required_settings.items() if not value]

if missing_settings:
    missing_names = ", ".join(missing_settings)

    raise ValueError(f"Variáveis obrigatórias não definidas: {missing_names}")


@contextmanager
def database_connection() -> Iterator[mariadb.Connection]:
    connection = mariadb.connect(
        host=database_host,
        port=database_port,
        database=database_name,
        user=database_user,
        password=database_password,
        connect_timeout=database_timeout,
    )

    try:
        yield connection
    finally:
        connection.close()
