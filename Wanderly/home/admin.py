from django.contrib import admin

from .models import timeResponce


@admin.register(timeResponce)
class TimeResponseAdmin(admin.ModelAdmin):
    list_display = ("id", "user")
    search_fields = ("user__username", "user__email")
