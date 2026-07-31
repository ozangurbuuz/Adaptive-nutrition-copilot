from typing import Any

import psycopg
from psycopg import Connection

from app.core.config import get_settings


def create_database_connection() -> Connection[Any]:
    settings = get_settings()
    return psycopg.connect(
        settings.database_url.get_secret_value(),
        connect_timeout=5,
    )


def verify_database_connection() -> bool:
    try:
        with create_database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
                result = cursor.fetchone()
    except psycopg.Error:
        return False

    return result == (1,)