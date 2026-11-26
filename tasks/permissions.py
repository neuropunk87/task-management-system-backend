from rest_framework.permissions import SAFE_METHODS, BasePermission

from users.access import is_system_admin


def can_view_task(user, task):
    if is_system_admin(user):
        return True
    return (
        task.project.owner_id == user.pk
        or task.project.participants.filter(pk=user.pk).exists()
        or task.assigned_to.filter(pk=user.pk).exists()
    )


class IsTaskMember(BasePermission):
    """Restrict task access to its project members and assignees."""

    def has_object_permission(self, request, view, obj):
        if is_system_admin(request.user):
            return True
        if request.method in SAFE_METHODS:
            return can_view_task(request.user, obj)
        if request.method == "DELETE":
            return obj.project.owner_id == request.user.pk
        return (
            obj.project.owner_id == request.user.pk
            or obj.assigned_to.filter(pk=request.user.pk).exists()
        )


class IsCommentMember(BasePermission):
    def has_object_permission(self, request, view, obj):
        if is_system_admin(request.user):
            return True
        if request.method in SAFE_METHODS:
            return can_view_task(request.user, obj.task)
        if getattr(view, "action", None) == "reply" and request.method == "POST":
            return can_view_task(request.user, obj.task)
        return (
            obj.author_id == request.user.pk
            or obj.task.project.owner_id == request.user.pk
        )
