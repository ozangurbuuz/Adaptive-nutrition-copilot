from typing import Any

import psycopg
from psycopg import Connection

from app.core.config import settings


def create_database_connection() -> Connection[Any]:
    return psycopg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        dbname=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password,
        connect_timeout=5,
    )


def verify_database_connection() -> bool:
    with create_database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            result = cursor.fetchone()

    return result == (1,)