from django.db import models


class Texts(models.Model):
    author = models.CharField(max_length=10, null=True, blank=True)
    text = models.TextField(null=True, blank=True)

    def __str__(self) -> str:
        return str(self.author)
