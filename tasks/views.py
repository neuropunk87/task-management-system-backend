from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework import status
from django.db.models import Q
from tasks.models import Task, Comment
from tasks.permissions import IsAssignedToOrReadOnly
from tasks.serializers import TaskSerializer, CommentSerializer


class TaskViewSet(ModelViewSet):
    queryset = Task.objects.select_related('project').prefetch_related('assigned_to', 'comments')
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated, IsAssignedToOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, 'role', None) == 'admin':
            return self.queryset
        return self.queryset.filter(Q(project__participants=user) | Q(assigned_to=user)).distinct()

    # def perform_create(self, serializer):
    #     task = serializer.save()
    #     assigned_users = task.assigned_to.all()
    #     message = f"You have been assigned a new task: {task.title}"
    #     for user in assigned_users:
    #         Notification.objects.create(user=user, task=task, message=message)
    #         if user.email:
    #             send_email_notification.delay(user.email, f"New Task: {task.title}", message)
    #         if user.telegram_notifications_enabled and user.telegram_id:
    #             send_telegram_notification.delay(user.telegram_id, message)

    @action(detail=False, methods=['get'], url_path='my-tasks')
    def my_tasks(self, request):
        tasks = self.queryset.filter(assigned_to=request.user)
        serializer = self.get_serializer(tasks, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='project-tasks')
    def project_tasks(self, request):
        user = request.user
        tasks = self.queryset.filter(project__participants=user)
        serializer = self.get_serializer(tasks, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='comments')
    def task_comments(self, request, pk=None):
        task = self.get_object()
        comments = task.comments.all()
        serializer = CommentSerializer(comments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class TaskUpdateView(APIView):
    def put(self, request, pk):
        task = Task.objects.get(pk=pk)
        serializer = TaskSerializer(task, data=request.data, partial=True)

        if serializer.is_valid():
            task.modified_by = request.user
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CommentViewSet(ModelViewSet):
    queryset = Comment.objects.select_related('task', 'author')
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated, IsAssignedToOrReadOnly]

    def get_queryset(self):
        task_id = self.request.query_params.get('task_id')
        if task_id:
            return self.queryset.filter(task__id=task_id)
        return self.queryset

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(detail=False, methods=['get'], url_path='my-comments')
    def my_comments(self, request):
        comments = self.queryset.filter(author=request.user)
        serializer = self.get_serializer(comments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='reply')
    def reply(self, request, pk=None):
        parent_comment = self.get_object()
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save(author=request.user, task=parent_comment.task, parent=parent_comment)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
