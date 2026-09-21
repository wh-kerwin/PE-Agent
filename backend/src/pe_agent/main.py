from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from pe_agent.adapters.persistence.session import create_engine, create_session_factory
from pe_agent.api.routes.analysis import http_error_envelope
from pe_agent.api.routes.analysis import router as analysis_router
from pe_agent.application.task_service import TaskService
from pe_agent.config import Settings, get_settings
from pe_agent.testing import load_scenario


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    engine = create_engine(resolved_settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await engine.dispose()

    app = FastAPI(title=resolved_settings.app_name, lifespan=lifespan)
    app.state.settings = resolved_settings
    app.state.identity_provider = None
    app.state.task_service = TaskService(
        create_session_factory(engine),
        archive_enabled=resolved_settings.archive_enabled,
        sse_replay_limit=resolved_settings.sse_replay_limit,
    )
    app.state.development_authorized_entity_ids = _development_entities(resolved_settings)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        envelope = http_error_envelope(exc.status_code, exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=envelope.model_dump(mode="json", by_alias=True),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _: Request,
        __: RequestValidationError,
    ) -> JSONResponse:
        envelope = http_error_envelope(400, {"code": "INVALID_REQUEST"})
        return JSONResponse(
            status_code=400,
            content=envelope.model_dump(mode="json", by_alias=True),
        )

    @app.get("/health/live")
    async def liveness() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(analysis_router)
    return app


def _development_entities(settings: Settings) -> frozenset[str]:
    if settings.environment == "production" or settings.mock_scenario_path is None:
        return frozenset()
    scenario = load_scenario(settings.mock_scenario_path)
    return frozenset(
        {
            scenario.case.case_id,
            *scenario.case.lot_ids,
            *scenario.case.tool_ids,
            *scenario.case.recipe_ids,
        }
    )


app = create_app()
