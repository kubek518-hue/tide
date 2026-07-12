"""Central config. Everything comes from environment variables so the same
code runs locally and inside GitHub Actions with zero changes."""
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Optional sources — the Scout skips anything without credentials, gracefully.
META_AD_LIBRARY_TOKEN = os.environ.get("META_AD_LIBRARY_TOKEN", "")

# Tuning knobs (safe defaults; change via repo variables, not code edits).
MAX_CANDIDATES_PER_RUN = int(os.environ.get("MAX_CANDIDATES_PER_RUN", "40"))
TRENDS_TIMEFRAME = os.environ.get("TRENDS_TIMEFRAME", "today 3-m")
REQUEST_PAUSE_SECONDS = float(os.environ.get("REQUEST_PAUSE_SECONDS", "2.0"))
USER_AGENT = os.environ.get(
    "SCOUT_USER_AGENT", "tide-scout/0.1 (research; contact: set-your-email)"
)

def require_db() -> str:
    if not DATABASE_URL:
        raise SystemExit(
            "DATABASE_URL is not set. Copy .env.example to .env or add the "
            "GitHub Actions secret. See README step 3."
        )
    return DATABASE_URL
