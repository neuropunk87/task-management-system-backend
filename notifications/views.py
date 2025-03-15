from rest_framework.generics import ListCreateAPIView, GenericAPIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.status import HTTP_200_OK, HTTP_404_NOT_FOUND
from notifications.models import Notification
from notifications.serializers import NotificationSerializer
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
import json


class NotificationListView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.get_unread_for_user(self.request.user)


class MarkAsReadView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def post(self, request, notification_id):
        try:
            notification = Notification.objects.get(id=notification_id, user=request.user)
            notification.mark_as_read()
            return Response({"detail": "Notification marked as read."}, status=HTTP_200_OK)
        except Notification.DoesNotExist:
            return Response({"detail": "Notification not found."}, status=HTTP_404_NOT_FOUND)


@method_decorator(csrf_exempt, name='dispatch')
class TelegramWebhookView(View):
    def post(self, request, token):
        try:
            data = json.loads(request.body)
            print("Incoming Telegram data:", data)
            return JsonResponse({"status": "ok"}, status=200)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)


telegram_webhook_view = TelegramWebhookView.as_view()
