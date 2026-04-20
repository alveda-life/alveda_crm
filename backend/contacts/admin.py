from django.contrib import admin
from .models import Contact


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ['partner', 'date', 'created_by', 'created_at']
    list_filter = ['created_by', 'date']
    search_fields = ['partner__name', 'transcription']
    readonly_fields = ['created_at', 'updated_at']
