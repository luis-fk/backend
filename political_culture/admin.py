from django.contrib import admin

from political_culture.models import Texts, TextWordCount

admin.site.register(Texts)
admin.site.register(TextWordCount)
