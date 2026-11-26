from rest_framework.permissions import SAFE_METHODS, BasePermission

from users.access import is_system_admin


class IsProjectMemberOrOwner(BasePermission):
    """Members can read a project; only its owner or system admins can mutate it."""

    def has_object_permission(self, request, view, obj):
        if is_system_admin(request.user):
            return True
        if request.method in SAFE_METHODS:
            return obj.is_owner(request.user) or obj.is_participant(request.user)
        return obj.is_owner(request.user)
