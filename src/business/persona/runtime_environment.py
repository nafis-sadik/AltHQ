"""Runtime environment details derived by the backend, never edited from the UI."""

from datetime import datetime
from typing import Any, Dict

from business.persona.repository_protocols import IRuntimeConfig

# Language is reserved for the AI model layer: it will be chosen from the
# user's input language at inference time, not selected in the dashboard.
LANGUAGE_SOURCE = "auto-detected by the AI model from user input"


def get_runtime_environment(config: IRuntimeConfig) -> Dict[str, Any]:
    """Return the read-only runtime settings shown on the dashboard."""
    local_now = datetime.now().astimezone()

    return {
        "log_level": config.get("log_level", "INFO"),
        "timezone": str(local_now.tzinfo) if local_now.tzinfo else "UTC",
        "utc_offset": local_now.strftime("%z"),
        "language": LANGUAGE_SOURCE,
    }
