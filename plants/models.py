from django.db import models
from django.contrib.auth.models import User

class ChatHistory(models.Model):
    ROLE_CHOICES = [
        ('ai', 'AI'),
        ('human', 'Human'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_histories')
    message = models.TextField()
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)

    def __str__(self):
        return f"{self.user.username} - {self.role}: {self.message[:20]}"

class UserMemory(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='memory')
    memory = models.TextField()

    def __str__(self):
        return f"Memory for {self.user.username}"
