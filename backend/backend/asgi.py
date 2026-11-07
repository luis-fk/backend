"""
ASGI config for backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

from cfflch.api.admission_status import routing as cfflch_routing
from political_culture.api.messages import routing as pc_routing

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")


application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": URLRouter(
            pc_routing.websocket_urlpatterns + cfflch_routing.websocket_urlpatterns
        ),
    }
)
