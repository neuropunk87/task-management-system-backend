"""Shared authorization helpers.

Keeping role checks in one place prevents the API, Django admin, middleware,
and analytics endpoints from drifting into different privilege models.
"""

from rest_framework.permissions import BasePermission


SYSTEM_ADMIN_ROLES = frozenset({"superadmin", "admin"})


def is_system_admin(user) -> bool:
    """Return whether an active, authenticated user is a system administrator."""

    return bool(
        user
        and user.is_authenticated
        and user.is_active
        and (user.is_superuser or getattr(user, "role", None) in SYSTEM_ADMIN_ROLES)
    )


class IsSystemAdmin(BasePermission):
    def has_permission(self, request, view):
        return is_system_admin(request.user)
