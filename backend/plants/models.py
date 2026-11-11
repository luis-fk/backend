import hashlib
import secrets

from django.db import models

DEVICE_KEY_START = "dk_"
DEVICE_PREFIX_LENGTH = len(DEVICE_KEY_START) + 8


def hash_device_key(key: str) -> str:
    # A plain SHA-256 is enough: the key is long and random, not a password a person
    # chose, so nobody can find it by hashing guesses.
    return hashlib.sha256(key.encode()).hexdigest()


class Users(models.Model):
    auth_user_id = models.IntegerField(unique=True)
    # db_default keeps the default in the database, so the code still running
    # between the migration and the deploy can add rows without this column.
    active = models.BooleanField(
        default=True,
        db_default=True,
        help_text="Unticked, the person can't use this app, at once; their data in "
        "it stays.",
    )
    latitude = models.CharField(max_length=10, null=True, blank=True)
    longitude = models.CharField(max_length=10, null=True, blank=True)

    def __str__(self) -> str:
        return str(self.auth_user_id)


class ChatHistory(models.Model):
    ROLE_CHOICES = [
        ("ai", "AI"),
        ("human", "Human"),
    ]

    user = models.ForeignKey(
        Users,
        on_delete=models.CASCADE,
        related_name="chat_histories",
    )
    message = models.TextField()
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)


class UserMemory(models.Model):
    user = models.OneToOneField(Users, on_delete=models.CASCADE, related_name="memory")
    memory = models.TextField()


class Esp32Device(models.Model):
    """An ESP32 in a plant's pot. It posts its soil sensor with its own key, which
    says which device it is and, through it, whose plant it is."""

    nickname = models.CharField(
        max_length=60,
        help_text="The plant's name, shown in the Sensores tab and used by the chat.",
    )
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name="devices")
    prefix = models.CharField(max_length=DEVICE_PREFIX_LENGTH, editable=False)
    key_hash = models.CharField(max_length=64, unique=True, editable=False)
    dry_value = models.IntegerField(
        default=4095, help_text="The sensor's raw reading in dry soil: 0%."
    )
    wet_value = models.IntegerField(
        default=0, help_text="The sensor's raw reading in soaked soil: 100%."
    )
    active = models.BooleanField(
        default=True, help_text="Unticked, the device's key stops working."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "nickname"], name="unique_nickname_per_person"
            )
        ]

    def __str__(self) -> str:
        return self.nickname

    def generate_key(self) -> str:
        """Gives the device a new random key and returns it, keeping only its
        prefix and hash."""
        key = DEVICE_KEY_START + secrets.token_urlsafe(32)
        self.prefix = key[:DEVICE_PREFIX_LENGTH]
        self.key_hash = hash_device_key(key)
        return key

    def soil_percent(self, raw: int) -> int | None:
        """The soil moisture of a raw reading, from 0 at dry_value to 100 at
        wet_value; None when the two are equal. Swapping them inverts the scale,
        so it fits sensors that read higher when dry or when wet."""
        if self.dry_value == self.wet_value:
            return None
        share = (self.dry_value - raw) / (self.dry_value - self.wet_value)
        return max(0, min(100, round(share * 100)))


class Esp32Data(models.Model):
    analog_value = models.IntegerField()
    digital_value = models.IntegerField()
    temperature = models.IntegerField(null=True)
    humidity = models.IntegerField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        Users,
        on_delete=models.CASCADE,
        related_name="esp32_data",
        null=True,
    )
    device = models.ForeignKey(
        Esp32Device,
        on_delete=models.CASCADE,
        related_name="readings",
        null=True,
        blank=True,
    )

    def __str__(self) -> str:
        return f"Analog value: {self.analog_value}, Digital value: {self.digital_value}"
