from django.contrib import admin
from notifications.models import Notification, NotificationDelivery
from users.permissions import RoleRestrictedAdminMixin


@admin.register(Notification)
class NotificationAdmin(RoleRestrictedAdminMixin, admin.ModelAdmin):
    readonly_fields = [field.name for field in Notification._meta.fields]

    list_display = ('user', 'task', 'message', 'is_read', 'created_at')
    list_filter = ('user', 'task', 'is_read', 'created_at')
    search_fields = ('user__username', 'message', 'task__title')
    ordering = ('-created_at',)

    fieldsets = (
        ('Notification Details', {'fields': ('user', 'task', 'message', 'is_read')}),
        ('Timestamps', {'fields': ('created_at',)}),
    )

    actions = ['mark_as_read', 'mark_as_unread']

    @admin.action(description="Mark selected notifications as read")
    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)

    @admin.action(description="Mark selected notifications as unread")
    def mark_as_unread(self, request, queryset):
        queryset.update(is_read=False)

    def has_add_permission(self, request):
        return False  # Видалення кнопки "Add notification"

    def has_change_permission(self, request, obj=None):
        return False  # Видалення кнопок "Save", "Save and continue editing", "Save and add another"

    def has_delete_permission(self, request, obj=None):
        return False  # Видалення кнопки "Delete"


@admin.register(NotificationDelivery)
class NotificationDeliveryAdmin(RoleRestrictedAdminMixin, admin.ModelAdmin):
    readonly_fields = [field.name for field in NotificationDelivery._meta.fields]
    list_display = ("id", "channel", "status", "attempts", "available_at", "sent_at")
    list_filter = ("status", "channel")
    fields = ("user", "notification", "channel", "status", "attempts", "available_at", "sent_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
