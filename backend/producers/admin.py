from django.contrib import admin
from .models import Producer, ProducerTask, ProducerComment


class ProducerTaskInline(admin.TabularInline):
    model = ProducerTask
    extra = 0
    fields = ['title', 'assigned_to', 'due_date', 'priority', 'status']
    readonly_fields = ['created_at']


class ProducerCommentInline(admin.TabularInline):
    model = ProducerComment
    extra = 0
    fields = ['author', 'text', 'attachment', 'created_at']
    readonly_fields = ['created_at']


@admin.register(Producer)
class ProducerAdmin(admin.ModelAdmin):
    list_display  = ['name', 'company', 'funnel', 'stage', 'assigned_to', 'created_at']
    list_filter   = ['funnel', 'stage', 'assigned_to']
    search_fields = ['name', 'company', 'email', 'phone']
    inlines       = [ProducerTaskInline, ProducerCommentInline]
    readonly_fields = ['created_at', 'updated_at', 'stage_changed_at']


@admin.register(ProducerTask)
class ProducerTaskAdmin(admin.ModelAdmin):
    list_display  = ['title', 'producer', 'assigned_to', 'due_date', 'priority', 'status']
    list_filter   = ['status', 'priority']
    search_fields = ['title', 'producer__name']
    readonly_fields = ['created_at', 'updated_at', 'completed_at']


@admin.register(ProducerComment)
class ProducerCommentAdmin(admin.ModelAdmin):
    list_display  = ['producer', 'author', 'created_at']
    search_fields = ['producer__name', 'text']
    readonly_fields = ['created_at']
