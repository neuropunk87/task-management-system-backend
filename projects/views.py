from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from projects.models import Project
from projects.serializers import ProjectSerializer, ProjectCreateUpdateSerializer
from projects.permissions import IsOwnerOrParticipant
from django.db.models import Q


class ProjectViewSet(ModelViewSet):
    queryset = Project.objects.all()
    permission_classes = [IsAuthenticated, IsOwnerOrParticipant]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ProjectCreateUpdateSerializer
        return ProjectSerializer

    def get_queryset(self):
        user = self.request.user
        return Project.objects.filter(Q(owner=user) | Q(participants=user)).distinct()

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def destroy(self, request, *args, **kwargs):
        project = self.get_object()
        if not project.is_owner(request.user):
            return Response({"error": "Only the owner can delete the project."}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)
