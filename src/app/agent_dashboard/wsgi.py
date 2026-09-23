"""WSGI entrypoint for the agent dashboard."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "agent_dashboard.settings")

application = get_wsgi_application()
