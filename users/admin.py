from django.contrib import admin
from users.models import CustomUser
from users.permissions import RoleRestrictedModelAdmin


@admin.register(CustomUser)
class CustomUserAdmin(RoleRestrictedModelAdmin):
# class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'first_name', 'last_name', 'role', 'email', 'telegram_id',
                    'telegram_notifications_enabled', 'is_active', 'is_staff', 'date_joined')
    list_filter = ('role', 'is_staff', 'is_active', 'date_joined')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'telegram_id', 'role')
    ordering = ('-date_joined',)

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {
            'fields': ('first_name', 'last_name', 'email', 'telegram_id', 'telegram_notifications_enabled',
                       'phone_number', 'date_of_birth', 'avatar')
        }),
        ('Roles and Permissions', {
            'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Important Dates', {
            'fields': ('last_login', 'date_joined')
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'role', 'is_active', 'is_staff', 'is_superuser',
                       'telegram_id', 'telegram_notifications_enabled', 'phone_number', 'date_of_birth', 'avatar')
        }),
    )

    actions = ['activate_users', 'deactivate_users']

    @admin.action(description="Activate selected users")
    def activate_users(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description="Deactivate selected users")
    def deactivate_users(self, request, queryset):
        queryset.update(is_active=False)
