from fastapi import FastAPI

from app.api.router import router as api_router
from app.core.exception_handlers import register_exception_handlers


app = FastAPI(
    title="Adaptive Nutrition Copilot API",
    version="0.1.0",
)

register_exception_handlers(app)
app.include_router(api_router)
