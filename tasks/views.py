from django.db import IntegrityError, transaction
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from django_filters.rest_framework import DjangoFilterBackend

from tasks.filters import TaskFilter
from tasks.models import Comment, Task
from tasks.permissions import IsCommentMember, IsTaskMember
from tasks.serializers import CommentSerializer, TaskSerializer
from users.access import is_system_admin


def visible_tasks_for(user):
    queryset = Task.objects.select_related("project", "created_by", "modified_by").prefetch_related(
        "assigned_to"
    )
    if is_system_admin(user):
        return queryset
    return queryset.filter(
        Q(project__owner=user) | Q(project__participants=user) | Q(assigned_to=user)
    ).distinct()


class TaskViewSet(ModelViewSet):
    queryset = Task.objects.none()
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated, IsTaskMember]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = TaskFilter
    search_fields = ["title", "description"]
    ordering_fields = ["deadline", "created_at", "modified_at", "priority", "status"]
    ordering = ["deadline"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset
        return visible_tasks_for(self.request.user)

    @transaction.atomic
    def perform_create(self, serializer):
        try:
            serializer.save(created_by=self.request.user, modified_by=self.request.user)
        except IntegrityError as exc:
            raise ValidationError({"title": "Task conflicts with an existing record."}) from exc

    @transaction.atomic
    def perform_update(self, serializer):
        try:
            serializer.save(modified_by=self.request.user)
        except IntegrityError as exc:
            raise ValidationError({"title": "Task conflicts with an existing record."}) from exc

    @action(detail=False, methods=["get"], url_path="my-tasks")
    def my_tasks(self, request):
        tasks = self.filter_queryset(self.get_queryset().filter(assigned_to=request.user))
        page = self.paginate_queryset(tasks)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(tasks, many=True).data)

    @action(detail=False, methods=["get"], url_path="project-tasks")
    def project_tasks(self, request):
        tasks = self.filter_queryset(
            self.get_queryset().filter(
                Q(project__owner=request.user) | Q(project__participants=request.user)
            )
        )
        page = self.paginate_queryset(tasks)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(tasks, many=True).data)

    @action(detail=True, methods=["get"], url_path="comments")
    def task_comments(self, request, pk=None):
        task = self.get_object()
        comments = task.comments.select_related("author", "parent")
        page = self.paginate_queryset(comments)
        serializer = CommentSerializer(
            page if page is not None else comments,
            many=True,
            context=self.get_serializer_context(),
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


class CommentViewSet(ModelViewSet):
    queryset = Comment.objects.none()
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated, IsCommentMember]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset
        queryset = Comment.objects.select_related("task__project", "author", "parent")
        user = self.request.user
        if not is_system_admin(user):
            queryset = queryset.filter(
                Q(task__project__owner=user)
                | Q(task__project__participants=user)
                | Q(task__assigned_to=user)
            ).distinct()
        task_id = self.request.query_params.get("task_id")
        if task_id:
            try:
                task_id = int(task_id)
                if not 0 < task_id <= 9_223_372_036_854_775_807:
                    raise ValueError
            except ValueError as exc:
                raise ValidationError({"task_id": "A positive integer is required."}) from exc
            queryset = queryset.filter(task_id=task_id)
        return queryset

    @transaction.atomic
    def perform_create(self, serializer):
        if "task" not in serializer.validated_data:
            raise ValidationError({"task_id": "This field is required."})
        serializer.save(author=self.request.user)

    @action(detail=False, methods=["get"], url_path="my-comments")
    def my_comments(self, request):
        comments = self.get_queryset().filter(author=request.user)
        page = self.paginate_queryset(comments)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(comments, many=True).data)

    @action(detail=True, methods=["post"], url_path="reply")
    def reply(self, request, pk=None):
        parent_comment = self.get_object()
        serializer = self.get_serializer(data={"content": request.data.get("content")})
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            serializer.save(
                author=request.user,
                task=parent_comment.task,
                parent=parent_comment,
            )
        return Response(serializer.data, status=status.HTTP_201_CREATED)
