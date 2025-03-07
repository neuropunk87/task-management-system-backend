from django.urls import path
from notifications.views import NotificationListView, MarkAsReadView


urlpatterns = [
    path('', NotificationListView.as_view(), name='notification-list'),
    path('<int:notification_id>/read/', MarkAsReadView.as_view(), name='mark-as-read'),
]
