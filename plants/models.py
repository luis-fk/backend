from django.contrib.auth.models import AbstractUser
from django.db import models


class Users(AbstractUser):
    latitude = models.CharField(max_length=10, null=True, blank=True)
    longitude = models.CharField(max_length=10, null=True, blank=True)

    def __str__(self) -> str:
        return self.username


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

    def __str__(self) -> str:
        return f"{self.user.username} - {self.role}: {self.message[:20]}"


class UserMemory(models.Model):
    user = models.OneToOneField(Users, on_delete=models.CASCADE, related_name="memory")
    memory = models.TextField()

    def __str__(self) -> str:
        return f"Memory for {self.user.username}"


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

    def __str__(self) -> str:
        return f"Analog value: {self.analog_value}, Digital value: {self.digital_value}"
