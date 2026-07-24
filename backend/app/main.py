import psycopg
from fastapi import FastAPI, HTTPException, status

from app.core.database import verify_database_connection


app = FastAPI(
    title="Adaptive Nutrition Copilot API",
    version="0.1.0",
)


@app.get("/health")
def health_check() -> dict[str, str]:
    try:
        database_connected = verify_database_connection()
    except psycopg.Error as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        ) from exc

    if not database_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database health check failed",
        )

    return {
        "status": "healthy",
        "database": "connected",
    }