"""
ASGI config for backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
# Sets Django up before the imports below, whose consumers reach a model through
# backend/api_auth.py (the order the Channels docs recommend).
django_asgi_app = get_asgi_application()

from cfflch.api.admission_status import routing as cfflch_routing  # noqa: E402
from political_culture.api.messages import routing as pc_routing  # noqa: E402
from political_culture.api.texts import routing as pc_texts_routing  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": URLRouter(
            pc_routing.websocket_urlpatterns
            + pc_texts_routing.websocket_urlpatterns
            + cfflch_routing.websocket_urlpatterns
        ),
    }
)
