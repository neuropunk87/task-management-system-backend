from django.contrib import admin
from django.db import models
from users.permissions import RoleRestrictedModelAdmin
from tasks.models import Task, TaskHistory, Comment


@admin.register(Task)
class TaskAdmin(RoleRestrictedModelAdmin):
# class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'created_by', 'get_assigned_to', 'status', 'priority', 'deadline', 'created_at')
    list_filter = ('status', 'priority', 'project', 'assigned_to', 'deadline', 'created_at')
    filter_horizontal = ('assigned_to',)  # Працює тільки в формі редагування
    search_fields = ('title', 'project__name', 'assigned_to__username')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'modified_at')

    fieldsets = (
        ('Task Details', {'fields': ('title', 'description', 'project', 'assigned_to', 'created_by', 'modified_by')}),
        ('Status and Priority', {'fields': ('status', 'priority', 'deadline')}),
        ('Timestamps', {'fields': ('created_at', 'modified_at')}),
    )

    actions = ['mark_as_completed']

    @admin.display(description="Assigned To")  # Назва колонки в адмінці
    def get_assigned_to(self, obj):
        return ", ".join([user.username for user in obj.assigned_to.all()])

    @admin.action(description="Mark selected tasks as completed")
    def mark_as_completed(self, request, queryset):
        queryset.update(status=Task.Status.COMPLETED, modified_at=models.functions.Now(), modified_by=request.user)
        # queryset.update(status='Completed')


@admin.register(TaskHistory)
class TaskHistoryAdmin(admin.ModelAdmin):
    readonly_fields = [field.name for field in TaskHistory._meta.fields]

    list_display = ('task', 'modified_by', 'modified_at', 'field_changed', 'old_value', 'new_value')
    search_fields = ('task__title', 'modified_by__username', 'field_changed')
    ordering = ('-modified_at',)

    def has_add_permission(self, request):
        return False  # Видалення кнопки "Add task history"

    def has_change_permission(self, request, obj=None):
        return False  # Видалення кнопок "Save", "Save and continue editing", "Save and add another"

    def has_delete_permission(self, request, obj=None):
        return False  # Видалення кнопки "Delete"


@admin.register(Comment)
class CommentAdmin(RoleRestrictedModelAdmin):
# class CommentAdmin(admin.ModelAdmin):
    list_display = ('task', 'author', 'created_at', 'modified_at')
    search_fields = ('task__title', 'author__username', 'content')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'modified_at')

    fieldsets = (
        ('Comment Details', {'fields': ('task', 'author', 'content')}),
        ('Timestamps', {'fields': ('created_at', 'modified_at')}),
    )
