from django.contrib import admin
from .models import Partner


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ['name', 'type', 'category', 'stage', 'phone', 'paid_orders_sum', 'assigned_to']
    list_filter = ['stage', 'type', 'category', 'assigned_to']
    search_fields = ['name', 'phone', 'user_id']
    readonly_fields = ['created_at', 'updated_at']
