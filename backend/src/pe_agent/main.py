from fastapi import FastAPI

from pe_agent.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    app = FastAPI(title=resolved_settings.app_name)

    @app.get("/health/live")
    async def liveness() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
