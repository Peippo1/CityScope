from pathlib import Path
import logging
import os
from urllib.parse import urlsplit

from fastapi import Request

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = PROJECT_ROOT / ".env.local"

# Keep local credentials out of source control while making API startup
# independent of the directory from which uvicorn is launched.
load_dotenv(ENV_FILE, override=False)

LOGGER = logging.getLogger("cityscope.config")


def _positive_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


MAX_REQUEST_BYTES = _positive_int("CITYSCOPE_MAX_REQUEST_BYTES", 16_384)
INVESTIGATION_RATE_LIMIT = _positive_int("CITYSCOPE_INVESTIGATION_RATE_LIMIT", 12)
INVESTIGATION_RATE_WINDOW_SECONDS = _positive_int("CITYSCOPE_INVESTIGATION_RATE_WINDOW_SECONDS", 300)
INVESTIGATION_CONCURRENCY_LIMIT = _positive_int("CITYSCOPE_INVESTIGATION_CONCURRENCY_LIMIT", 8)
INVESTIGATION_TIMEOUT_SECONDS = _positive_int("CITYSCOPE_INVESTIGATION_TIMEOUT_SECONDS", 60)
MODEL_TIMEOUT_SECONDS = _positive_int("CITYSCOPE_MODEL_TIMEOUT_SECONDS", 30)


def is_production() -> bool:
    return os.getenv("CITYSCOPE_ENV", "development").lower() == "production"


def missing_server_credentials() -> list[str]:
    """Return names only; never include credential values in diagnostics."""
    configured = {
        "GEMINI_API_KEY": bool(os.getenv("GEMINI_API_KEY")),
        "GOOGLE_MAPS_GROUNDING_API_KEY or GOOGLE_MAPS_API_KEY": bool(os.getenv("GOOGLE_MAPS_GROUNDING_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")),
        "GOOGLE_ROUTES_API_KEY or GOOGLE_MAPS_API_KEY": bool(os.getenv("GOOGLE_ROUTES_API_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")),
    }
    return [name for name, present in configured.items() if not present]


def log_configuration_status() -> None:
    missing = missing_server_credentials()
    if missing:
        LOGGER.warning("CityScope server integrations unavailable; missing configuration: %s", ", ".join(missing))
    else:
        LOGGER.info("CityScope server integration credentials are configured")


def configured_origins() -> list[str]:
    return [origin.strip() for origin in os.getenv("CITYSCOPE_WEB_ORIGIN", "http://localhost:3000").split(",") if origin.strip()]


def configured_origin_regex() -> str | None:
    """Allow Next.js fallback ports only when the configured web origin is local."""
    local_hosts = {"localhost", "127.0.0.1"}
    if any(urlsplit(origin).hostname in local_hosts for origin in configured_origins()):
        return r"^https?://(?:localhost|127\.0\.0\.1)(?::\d+)?$"
    return None


def trusted_hosts() -> list[str]:
    return [host.strip() for host in os.getenv("CITYSCOPE_TRUSTED_HOSTS", "localhost,127.0.0.1,testserver").split(",") if host.strip()]


def request_client_key(request: Request) -> str:
    """Trust forwarding headers only when the deployment explicitly opts in."""
    if os.getenv("CITYSCOPE_TRUST_PROXY_HEADERS", "false").lower() == "true":
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if forwarded:
            return forwarded
    return request.client.host if request.client else "unknown"
