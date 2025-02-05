from django.contrib import admin
from plants.models import Esp32Data, ChatHistory, UserMemory, Users

admin.site.register(Esp32Data)
admin.site.register(ChatHistory)
admin.site.register(UserMemory)
admin.site.register(Users)
