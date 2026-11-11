from django.contrib.auth import get_user_model

from plants.models import Esp32Device, hash_device_key


def device_for_key(key: str) -> Esp32Device | None:
    """The active device with this key, while its owner can still use plants: their
    plants row and their auth user both active, the same rule as their tokens (see
    backend/api_auth.py). None otherwise, and for an empty key."""
    if not key:
        return None
    device = (
        Esp32Device.objects.select_related("user")
        .filter(key_hash=hash_device_key(key), active=True, user__active=True)
        .first()
    )
    if device is None:
        return None
    owner_is_active = (
        get_user_model()
        ._default_manager.filter(pk=device.user.auth_user_id, is_active=True)
        .exists()
    )
    return device if owner_is_active else None
