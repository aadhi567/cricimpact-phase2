"""Main FastAPI application entry point for CricImpact Phase 2."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from pathlib import Path
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.core.config import settings
from backend.services.bowling_data_service import BowlingDataService
from backend.services.pcs_data_service import PCSDataService
from backend.services.batting_data_service import BattingDataService
from backend.services.pri_data_service import PRIDataService
from backend.api.bowling.router import bowling_router
from backend.api.pcs.router import pcs_router
from backend.api.batting.router import batting_router
from backend.api.pri.router import pri_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan event handler for application startup and shutdown."""
    # Startup: Load datasets, verify manifest and initialize in-memory indexes
    bowling_service = BowlingDataService.get_instance()
    bowling_service.initialize()

    # Initialize independent PCS data service
    pcs_service = PCSDataService.get_instance()
    pcs_service.initialize()

    # Initialize read-only Batting HPP/HPC data service
    batting_service = BattingDataService.get_instance()
    batting_service.initialize()

    # Initialize read-only Pressure Reliability Index (PRI-2) data service
    pri_service = PRIDataService.get_instance()
    pri_service.initialize()

    yield
    # Shutdown: Clean resources if needed


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=settings.DESCRIPTION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routers under /api
    app.include_router(bowling_router, prefix=settings.API_V1_PREFIX)
    app.include_router(pcs_router, prefix=settings.API_V1_PREFIX)
    app.include_router(batting_router, prefix=settings.API_V1_PREFIX)
    app.include_router(pri_router, prefix=settings.API_V1_PREFIX)

    # Global Exception Handlers
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "status": "error",
                "error": "HTTP Exception",
                "detail": exc.detail,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "status": "error",
                "error": "Validation Error",
                "detail": str(exc),
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "error": "Internal Server Error",
                "detail": str(exc),
            },
        )

    # Root & Health check endpoints
    @app.get("/", tags=["System"])
    async def root(request: Request):
        accept = request.headers.get("accept", "")
        # If requested from a web browser navigation bar, serve the frontend SPA
        if "text/html" in accept and "application/json" not in accept:
            index_path = settings.BASE_DIR / "frontend" / "index.html"
            if index_path.exists():
                return FileResponse(str(index_path))
        return {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "status": "active",
            "documentation": "/docs",
            "bowling_api_base": f"{settings.BOWLING_PREFIX}",
            "frontend_app": "/app",
            "batting_app": "/batting/hpp_dashboard.html",
        }

    @app.get("/app", tags=["System"])
    @app.get("/index.html", tags=["System"])
    async def app_entrypoint():
        index_path = settings.BASE_DIR / "frontend" / "index.html"
        return FileResponse(str(index_path))

    @app.get("/health", tags=["System"])
    @app.get("/api/health", tags=["System"])
    async def health_check():
        service = BowlingDataService.get_instance()
        pcs_svc = PCSDataService.get_instance()
        batting_svc = BattingDataService.get_instance()
        pri_svc = PRIDataService.get_instance()
        return {
            "status": "healthy",
            "service_initialized": service.is_initialized,
            "pcs_service_initialized": pcs_svc.is_initialized,
            "batting_service_initialized": batting_svc.is_initialized,
            "pri_service_initialized": pri_svc.is_initialized,
            "corpus_matches": len(service.matches_list_cache),
            "career_bowlers": len(service.career_df),
            "match_spells": len(service.spells_df),
            "deliveries": len(service.deliv_df),
            "pcs_deliveries": len(pcs_svc.deliv_df),
            "batting_batted_stints": sum(1 for s in batting_svc.all_stints if not s["is_dnb"]),
            "batting_dnb_stints": sum(1 for s in batting_svc.all_stints if s["is_dnb"]),
            "pri_batting_pressure_innings": len(pri_svc.batting_innings_df),
            "pri_bowling_pressure_spells": len(pri_svc.bowling_spells_df),
        }

    # Static files mounting: Batting dashboards & Frontend SPA assets
    batting_dir = settings.BASE_DIR / "docs" / "worm_graph"
    if batting_dir.exists():
        app.mount("/batting", StaticFiles(directory=str(batting_dir), html=True), name="batting")

    frontend_dir = settings.BASE_DIR / "frontend"
    if frontend_dir.exists():
        src_dir = frontend_dir / "src"
        if src_dir.exists():
            app.mount("/src", StaticFiles(directory=str(src_dir)), name="src")
        app.mount("/app", StaticFiles(directory=str(frontend_dir), html=True), name="app_static")

    return app


app = create_app()
