from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.core.exceptions import PermissionDenied

from users.access import is_system_admin
from users.models import CustomUser
from users.permissions import RoleRestrictedAdminMixin


@admin.register(CustomUser)
class CustomUserAdmin(RoleRestrictedAdminMixin, DjangoUserAdmin):
    readonly_fields = ("telegram_id", "telegram_verified_at", "avatar")
    list_display = (
        "username",
        "first_name",
        "last_name",
        "role",
        "email",
        "telegram_notifications_enabled",
        "is_active",
        "is_staff",
        "date_joined",
    )
    list_filter = ("role", "is_staff", "is_active", "date_joined")
    search_fields = ("username", "first_name", "last_name", "email", "role")
    ordering = ("-date_joined",)

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (
            "Personal info",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "email",
                    "telegram_id",
                    "telegram_verified_at",
                    "telegram_notifications_enabled",
                    "phone_number",
                    "date_of_birth",
                    "avatar",
                )
            },
        ),
        (
            "Roles and permissions",
            {
                "fields": (
                    "role",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "email",
                    "password1",
                    "password2",
                    "role",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                ),
            },
        ),
    )
    actions = ["activate_users", "deactivate_users"]

    def has_change_permission(self, request, obj=None):
        if not is_system_admin(request.user):
            return False
        if obj and (
            obj.is_superuser
            or obj.role in {CustomUser.Role.ADMIN, CustomUser.Role.SUPERADMIN}
        ):
            return request.user.is_superuser
        return True

    def has_delete_permission(self, request, obj=None):
        if not self.has_change_permission(request, obj):
            return False
        return not obj or obj.pk != request.user.pk

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser:
            fields.extend(
                ["role", "is_staff", "is_superuser", "groups", "user_permissions"]
            )
        return tuple(dict.fromkeys(fields))

    def get_fieldsets(self, request, obj=None):
        if obj is None and not request.user.is_superuser:
            return (
                (
                    None,
                    {
                        "classes": ("wide",),
                        "fields": (
                            "username",
                            "email",
                            "password1",
                            "password2",
                            "is_active",
                        ),
                    },
                ),
            )
        return super().get_fieldsets(request, obj)

    def save_model(self, request, obj, form, change):
        if change and not self.has_change_permission(request, obj):
            raise PermissionDenied("You cannot modify this privileged account.")
        if not request.user.is_superuser:
            obj.is_superuser = False
            if obj.role in {CustomUser.Role.ADMIN, CustomUser.Role.SUPERADMIN}:
                obj.role = CustomUser.Role.EMPLOYEE
        super().save_model(request, obj, form, change)

    def delete_queryset(self, request, queryset):
        protected = queryset.filter(is_superuser=True) | queryset.filter(
            role__in=(CustomUser.Role.ADMIN, CustomUser.Role.SUPERADMIN)
        )
        if protected.exists() or queryset.filter(pk=request.user.pk).exists():
            raise PermissionDenied("Privileged or current accounts cannot be bulk deleted.")
        super().delete_queryset(request, queryset)

    @admin.action(description="Activate selected users")
    def activate_users(self, request, queryset):
        queryset.exclude(is_superuser=True).exclude(
            role__in=(CustomUser.Role.ADMIN, CustomUser.Role.SUPERADMIN)
        ).update(is_active=True)

    @admin.action(description="Deactivate selected users")
    def deactivate_users(self, request, queryset):
        queryset.exclude(pk=request.user.pk).exclude(is_superuser=True).exclude(
            role__in=(CustomUser.Role.ADMIN, CustomUser.Role.SUPERADMIN)
        ).update(is_active=False)
