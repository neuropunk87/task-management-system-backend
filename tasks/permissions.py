from rest_framework.permissions import BasePermission


class IsAssignedToOrReadOnly(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return obj.assigned_to == request.user or request.user.role == 'superadmin' or request.user.role == 'admin'
