"""ASGI entrypoint for the agent dashboard."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "agent_dashboard.settings")

application = get_asgi_application()
