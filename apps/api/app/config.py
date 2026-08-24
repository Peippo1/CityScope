from pathlib import Path
import logging
import os

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = PROJECT_ROOT / ".env.local"

# Keep local credentials out of source control while making API startup
# independent of the directory from which uvicorn is launched.
load_dotenv(ENV_FILE, override=False)

LOGGER = logging.getLogger("cityscope.config")


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
