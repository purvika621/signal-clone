from typing import Annotated, Literal
import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.auth import router as auth_router
from app.messaging import router as messaging_router
from app.live_routes import router as live_router
from app.realtime import manager
from app.auth import mutation_origin
from app.groups import router as group_router

@asynccontextmanager
async def lifespan(_app):
    maintenance = asyncio.create_task(manager.maintain())
    try:
        yield
    finally:
        maintenance.cancel()
        with suppress(asyncio.CancelledError):
            await maintenance
        for connection in list(manager.connections):
            await manager.close(connection, 1001)


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(auth_router)
app.include_router(messaging_router)
app.include_router(group_router)
app.include_router(live_router, dependencies=[Depends(mutation_origin)])


@app.exception_handler(StarletteHTTPException)
async def http_error(_request, exc):
    codes = {401: "unauthenticated", 403: "forbidden", 404: "not_found", 409: "conflict", 422: "validation_error", 503: "unavailable"}
    return JSONResponse(status_code=exc.status_code,
        content={"code": codes.get(exc.status_code, "request_error"), "message": str(exc.detail)}, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error(_request, exc):
    fields = {".".join(str(p) for p in error["loc"][1:]): error["msg"] for error in exc.errors()}
    return JSONResponse(status_code=422, content={"code": "validation_error", "message": "Please check the entered values", "field_errors": fields})


@app.exception_handler(SQLAlchemyError)
async def database_error(_request, _exc):
    return JSONResponse(status_code=503, content={"code": "unavailable", "message": "Database temporarily unavailable. Please retry"})
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


class HealthResponse(BaseModel):
    status: Literal["ok"]
    database: Literal["ok"]


@app.get("/health", response_model=HealthResponse)
def health(db: Annotated[Session, Depends(get_db)]) -> HealthResponse:
    try:
        db.execute(text("SELECT 1"))
        # A reachable empty SQLite file is not an initialized application database.
        db.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable or not initialized") from exc
    return HealthResponse(status="ok", database="ok")

