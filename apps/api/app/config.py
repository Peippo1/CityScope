from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = PROJECT_ROOT / ".env.local"

# Keep local credentials out of source control while making API startup
# independent of the directory from which uvicorn is launched.
load_dotenv(ENV_FILE, override=False)
