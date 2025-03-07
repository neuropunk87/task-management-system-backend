from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from django.shortcuts import get_object_or_404
from projects.models import Project
from analytics.models import ProjectAnalytics
from analytics.serializers import ProjectAnalyticsSerializer


class AnalyticsView(APIView):
    permission_classes = [IsAdminUser]
    serializer_class = ProjectAnalyticsSerializer

    def get(self, request, project_id):
        try:
            project = get_object_or_404(Project, id=project_id)
            analytics, _ = ProjectAnalytics.objects.get_or_create(project=project)
            analytics.update_analytics()
            serializer = ProjectAnalyticsSerializer(analytics)
            return Response(serializer.data)
        except Project.DoesNotExist:
            return Response({"error": "Project not found."}, status=404)


class ProjectAnalyticsChartView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        projects = ProjectAnalytics.objects.all()

        if not projects.exists():
            return Response({"message": "No data available for analytics."}, status=404)

        data = {
            "labels": [analytics.project.name for analytics in projects],
            "total_tasks": [analytics.total_tasks for analytics in projects],
            "completed_tasks": [analytics.completed_tasks for analytics in projects],
            "in_progress_tasks": [analytics.in_progress_tasks for analytics in projects],
            "pending_tasks": [analytics.pending_tasks for analytics in projects],
        }
        return Response(data)
