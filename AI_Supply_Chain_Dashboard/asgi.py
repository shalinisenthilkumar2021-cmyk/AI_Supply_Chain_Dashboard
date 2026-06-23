"""
ASGI config for AI_Supply_Chain_Dashboard project.
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AI_Supply_Chain_Dashboard.settings')

application = get_asgi_application()
