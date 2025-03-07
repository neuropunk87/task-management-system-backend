from rest_framework.permissions import BasePermission


class IsOwnerOrParticipant(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.is_owner(request.user) or obj.is_participant(request.user)
