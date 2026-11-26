from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from analytics.models import ProjectAnalytics
from analytics.serializers import ProjectAnalyticsSerializer
from projects.models import Project
from users.access import IsSystemAdmin


class AnalyticsView(APIView):
    permission_classes = [IsSystemAdmin]
    serializer_class = ProjectAnalyticsSerializer

    def get(self, request, project_id):
        project = get_object_or_404(Project, id=project_id)
        analytics, _ = ProjectAnalytics.objects.get_or_create(project=project)
        analytics.update_analytics()
        return Response(ProjectAnalyticsSerializer(analytics).data)


class ProjectAnalyticsChartView(APIView):
    permission_classes = [IsSystemAdmin]

    def get(self, request):
        projects = ProjectAnalytics.objects.select_related("project")
        if not projects.exists():
            return Response({"message": "No data available for analytics."}, status=404)
        return Response(
            {
                "labels": [item.project.name for item in projects],
                "total_tasks": [item.total_tasks for item in projects],
                "completed_tasks": [item.completed_tasks for item in projects],
                "in_progress_tasks": [item.in_progress_tasks for item in projects],
                "pending_tasks": [item.pending_tasks for item in projects],
            }
        )
