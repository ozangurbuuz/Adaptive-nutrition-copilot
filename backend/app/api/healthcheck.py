from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse

from app.core.database import verify_database_connection


router = APIRouter()


@router.get("/healthcheck")
def healthcheck(
    database_reachable: Annotated[bool, Depends(verify_database_connection)],
) -> Response:
    if not database_reachable:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "database": "unreachable",
            },
        )

    return JSONResponse(
        content={
            "status": "healthy",
            "database": "reachable",
        }
    )
