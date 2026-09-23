#!/usr/bin/env python
"""Django management entrypoint for the agent dashboard (Layer 1)."""

import os
import sys
from pathlib import Path

# Layer 1 (this file) plus the src root so Layer 2/3 packages are importable.
BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR.parent
for path in (str(BASE_DIR), str(SRC_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)


def main() -> None:
    """Run Django administrative tasks for the dashboard project."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "agent_dashboard.settings")

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Ensure it is installed and available on "
            "PYTHONPATH, and that the virtual environment is activated."
        ) from exc

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
