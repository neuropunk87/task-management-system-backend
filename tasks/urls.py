from django.urls import path, include
from rest_framework.routers import DefaultRouter
from tasks.views import TaskViewSet, CommentViewSet


router = DefaultRouter()
router.register('tasks', TaskViewSet, basename='task')
router.register('comments', CommentViewSet, basename='comment')

urlpatterns = [
    path('', include(router.urls)),
]
