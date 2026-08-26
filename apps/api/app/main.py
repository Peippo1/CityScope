import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .routes.cities import router as cities_router
from .routes.investigations import router as investigations_router
from .routes.history import router as history_router
from . import config
from .artifacts import verify_deployment_artifact

app = FastAPI(title="CityScope API", version="0.1.0")
config.log_configuration_status()
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.configured_origins(),
    allow_origin_regex=config.configured_origin_regex(),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.trusted_hosts())
app.include_router(cities_router)
app.include_router(investigations_router)
app.include_router(history_router)


@app.get("/health")
def health() -> dict[str, str]:
    missing = config.missing_server_credentials()
    return {"status": "ok" if not missing else "degraded", "missing_configuration": ", ".join(missing) if missing else "none"}


@app.get("/ready")
def ready() -> dict[str, str]:
    artifact = verify_deployment_artifact(config.PROJECT_ROOT)
    if artifact["status"] != "ready":
        raise HTTPException(status_code=503, detail="Dataset artifact is not ready")
    return artifact
