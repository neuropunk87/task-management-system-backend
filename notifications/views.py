from rest_framework.generics import GenericAPIView, ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from notifications.models import Notification
from notifications.serializers import NotificationSerializer


class NotificationListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.get_unread_for_user(self.request.user).select_related("task")


class MarkAsReadView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def post(self, request, notification_id):
        notification = self.get_queryset().filter(pk=notification_id).first()
        if not notification:
            return Response({"detail": "Notification not found."}, status=404)
        notification.mark_as_read()
        return Response({"detail": "Notification marked as read."})

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)
