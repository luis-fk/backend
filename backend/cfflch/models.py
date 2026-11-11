from django.db import models


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

    def __str__(self) -> str:
        return str(self.auth_user_id)


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
    search_title = models.CharField(max_length=512, blank=True, default="")
