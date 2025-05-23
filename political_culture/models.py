from django.db import models


class Users(models.Model):
    auth_user_id = models.IntegerField(unique=True)

    def __str__(self) -> str:
        return str(self.auth_user_id)


class Texts(models.Model):
    title = models.CharField(max_length=100, null=True, blank=True)
    author = models.CharField(max_length=30, null=True, blank=True)
    text = models.TextField()
    content_description = models.TextField()
    user_submitted_text = models.BooleanField(default=False)
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name="texts")

    def __str__(self) -> str:
        return f"Text {self.title} by {self.author}"


class TextWordCount(models.Model):
    text = models.OneToOneField(
        Texts, on_delete=models.CASCADE, related_name="analysis"
    )
    total_word_count = models.IntegerField()
    word_frequencies = models.JSONField()

    def __str__(self) -> str:
        return f"Word count for Text ID {self.text.id} - {self.total_word_count} words"


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
    memory = models.JSONField()
