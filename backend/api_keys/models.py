import hashlib
import secrets

from django.db import models

# Every key starts like this, so backend/api_auth.py tells it from a JWT ("eyJ...").
KEY_START = "pk_"
PREFIX_LENGTH = len(KEY_START) + 8


def hash_key(key: str) -> str:
    # A plain SHA-256 is enough: the key is long and random, not a password a person
    # chose, so nobody can find it by hashing guesses.
    return hashlib.sha256(key.encode()).hexdigest()


class ApiKey(models.Model):
    """A key that calls one app's API as one of its users, from Bruno for example.

    Only its hash is stored: the admin shows the key once, when it creates it.
    """

    name = models.CharField(max_length=100, help_text="Who or what the key is for.")
    app = models.CharField(
        max_length=20,
        choices=[
            ("plants", "plants"),
            ("political-culture", "political-culture"),
            ("cfflch", "cfflch"),
        ],
    )
    user_id = models.BigIntegerField(help_text="The id in the app's Users table.")
    prefix = models.CharField(max_length=PREFIX_LENGTH, editable=False)
    key_hash = models.CharField(max_length=64, unique=True, editable=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, editable=False)

    # The full key, set by the admin right after generate_key() for the page that
    # shows it once. Not a field, so it is never saved.
    new_key = ""

    class Meta:
        verbose_name = "API key"

    def __str__(self) -> str:
        return self.name

    def generate_key(self) -> str:
        """Gives the key a new random value and returns it, keeping only its prefix
        and hash."""
        key = KEY_START + secrets.token_urlsafe(32)
        self.prefix = key[:PREFIX_LENGTH]
        self.key_hash = hash_key(key)
        return key
