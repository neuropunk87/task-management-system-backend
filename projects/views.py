from django.db import IntegrityError, transaction
from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from rest_framework.viewsets import ModelViewSet

from projects.models import Project
from projects.permissions import IsProjectMemberOrOwner
from projects.serializers import ProjectCreateUpdateSerializer, ProjectSerializer
from users.access import is_system_admin


class ProjectViewSet(ModelViewSet):
    queryset = Project.objects.none()
    permission_classes = [IsAuthenticated, IsProjectMemberOrOwner]

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return ProjectCreateUpdateSerializer
        return ProjectSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset
        queryset = Project.objects.select_related("owner").prefetch_related(
            "participants"
        )
        user = self.request.user
        if is_system_admin(user):
            return queryset
        return queryset.filter(Q(owner=user) | Q(participants=user)).distinct()

    @transaction.atomic
    def perform_create(self, serializer):
        try:
            project = serializer.save(owner=self.request.user)
            project.participants.add(self.request.user)
        except IntegrityError as exc:
            raise ValidationError({"name": "Project conflicts with an existing record."}) from exc

    @transaction.atomic
    def perform_update(self, serializer):
        try:
            serializer.save()
        except IntegrityError as exc:
            raise ValidationError({"name": "Project conflicts with an existing record."}) from exc
