from django.contrib.admin import ModelAdmin
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied


User = get_user_model()


class RoleRestrictedModelAdmin(ModelAdmin):
    def has_permission(self, request):
        return request.user.is_authenticated and request.user.role in ['superadmin', 'admin']

    def has_view_permission(self, request, obj=None):
        return self.has_permission(request)

    def has_add_permission(self, request, obj=None):
        return self.has_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_permission(request)

    def has_delete_permission(self, request, obj=None):
        return self.has_permission(request)

    def has_module_permission(self, request):
        return self.has_permission(request)

    def save_model(self, request, obj, form, change):
        if not self.has_change_permission(request, obj):
            raise PermissionDenied("You don't have permission to change this object.")
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        if not self.has_delete_permission(request, obj):
            raise PermissionDenied("You don't have permission to delete this object.")
        super().delete_model(request, obj)
