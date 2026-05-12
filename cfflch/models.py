from django.db import models


class ClassRoom(models.Model):
    name = models.CharField(max_length=255)
    name_normalized = models.CharField(max_length=255, unique=True)

    class Meta:
        ordering = ["name"]


class AdmissionResult(models.Model):
    student_name = models.CharField(max_length=255)
    student_name_normalized = models.CharField(max_length=255)
    year = models.IntegerField()
    approved = models.BooleanField(default=False)
    class_room = models.ForeignKey(
        ClassRoom, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("student_name_normalized", "year")]


class AdmissionPDF(models.Model):
    result = models.ForeignKey(
        AdmissionResult, related_name="pdfs", on_delete=models.CASCADE
    )
    url = models.CharField(max_length=2048)
